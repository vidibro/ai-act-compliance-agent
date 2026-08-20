"""The gap-analysis graph: a classified system plus its documentation in, a ComplianceReport out.

Four nodes, and two of them use a model:

    roles             WHO the parties are: has Art. 25 moved the  — up to two LLM calls,
                      provider role, and what kind of organisation      high-risk only
                      deploys the system (gap/roles.py)
    select_rules      which obligations apply, per use case      — pure data (gap/rules.py)
    check_compliance  does the documentation satisfy each one    — one LLM call per rule
    assemble_report   findings, outstanding confirmations, counts — pure data

`roles` runs FIRST because it is about WHO the parties are, and everything after it is about what
each of them owes. Neither answer changes selection: the report lists every role's obligations
either way, and an obligation the Act narrows within a role — Art. 27 to public bodies and private
providers of public services — is still listed, with the answer saying which side of that condition
the document falls on. Withholding it instead would decide on someone's behalf which of their duties
to take seriously.

The split is the same one the classification cascade makes: code owns what applies and what the
verdict means, the model answers one bounded question at a time. Nothing here decides that a rule
is in scope, and nothing here overrides a verdict.

Judgements are independent — one rule against one document, no shared state — so they run
concurrently. `pool.map` preserves input order, so findings come back in rule order regardless of
scheduling: a report whose contents depended on thread timing would not be defensible.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from aiact.brain import Brain
from aiact.gap import roles as role_questions
from aiact.gap.judge import LLMJudge
from aiact.gap.rules import ActiveRules, roles_with_rules, select_rules
from aiact.schemas.classification import ClassificationResult
from aiact.schemas.enums import ActorRole, ProviderReallocation, Verdict
from aiact.schemas.policy import PolicyRule, PolicySpec
from aiact.schemas.question import Answer, Question, narrow
from aiact.schemas.report import ComplianceReport, Finding, ReportSummary
from aiact.tracing import trace_run

DEFAULT_WORKERS = 8


class ComplianceCheckState(BaseModel):
    """What flows through the graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    system_id: str
    document: str
    classification: ClassificationResult
    provider_reallocation: Answer | None = None
    deployer_type: Answer | None = None
    active: list[ActiveRules] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    report: ComplianceReport | None = None


def _summarise(findings: list[Finding]) -> ReportSummary:
    """Count verdicts overall and per use case.

    NOT_APPLICABLE is counted in neither `total_applicable` nor any verdict bucket: a rule that
    never activated is not a check that passed.
    """

    def count_verdicts(subset: list[Finding]) -> ReportSummary:
        counted = [f for f in subset if f.verdict != Verdict.NOT_APPLICABLE]
        return ReportSummary(
            total_applicable=len(counted),
            passed=sum(f.verdict == Verdict.PASS for f in counted),
            gaps=sum(f.verdict == Verdict.GAP for f in counted),
            inadequate=sum(f.verdict == Verdict.INADEQUATE for f in counted),
            needs_review=sum(f.verdict == Verdict.NEEDS_REVIEW for f in counted),
        )

    per_use_case = {
        use_case_id: count_verdicts([f for f in findings if f.use_case_id == use_case_id])
        for use_case_id in dict.fromkeys(f.use_case_id for f in findings)
    }
    # Split by duty-holder too. A provider reading one combined total cannot tell which part is
    # theirs to fix, and the deployer's part is not theirs to fix at all.
    per_role = {
        role: count_verdicts([f for f in findings if f.role == role])
        for role in dict.fromkeys(f.role for f in findings)
    }
    overall = count_verdicts(findings)
    return overall.model_copy(
        update={"per_use_case": per_use_case or None, "per_role": per_role or None}
    )


def build_graph(
    spec: PolicySpec,
    judge: LLMJudge,
    brain: Brain,
    max_workers: int = DEFAULT_WORKERS,
    questions: dict[str, Question] | None = None,
):
    """Compile the gap-analysis graph for one ruleset and one judge.

    EVERY duty-holder the spec covers, with no way to narrow it. Obligations attach to the role,
    and the tool's job is to report all of them: a provider's customers owe Arts. 26-27 on the same
    system, and nothing else will tell them so. The roles come from the spec rather than from a
    constant, so adding a rule for a new role is enough to make it appear."""
    roles = roles_with_rules(spec)
    asked = questions if questions is not None else role_questions.QUESTIONS

    def node_roles(state: ComplianceCheckState) -> dict:
        # Both gates live in gap/roles.py, so that the eval harness which measures these answers
        # applies the same ones. A `None` means the question was NOT PUT — never an answer of "no".
        out: dict = {}
        moved = role_questions.ask(
            brain, state.document, state.classification.overall_risk_class, asked
        )
        if moved is not None:
            out["provider_reallocation"] = moved
        kind = role_questions.ask_deployer_type(brain, state.document, state.classification, asked)
        if kind is not None:
            out["deployer_type"] = kind
        return out

    def node_select_rules(state: ComplianceCheckState) -> dict:
        # Once per (use case, role). Selection is per use case because Art. 6 classifies per
        # intended purpose, and per role because the Regulation attaches duties to the role rather
        # than to the organisation — one party can hold several, and each is assessed separately.
        #
        # The Art. 25 answer comes in HERE, and it is the only thing `roles` supplies that selection
        # acts on. It adds one obligation and never removes any: Art. 25(2)'s cooperation duty has
        # no holder until the provider role has moved, so `AIA-IP-A25-2` appears exactly when it
        # did. The deployer-type answer is deliberately NOT passed — it resolves a condition on a
        # duty that exists either way, and gating on it would withhold an obligation the Act
        # creates.
        moved = narrow(state.provider_reallocation, ProviderReallocation)
        return {
            "active": [
                select_rules(spec, uc, role, reallocation=moved)
                for uc in state.classification.use_cases
                for role in roles
            ]
        }

    def node_check_compliance(state: ComplianceCheckState) -> dict:
        # Each job is judged against the whole document. Sound while a classification carries one
        # use case; with several, evidence written about one intended purpose can be credited to
        # another. Scoping it requires knowing which passages belong to which use case — the
        # decomposition problem, tracked in M7.
        jobs: list[tuple[str, ActorRole, PolicyRule]] = [
            (active.use_case_id, active.role, rule)
            for active in state.active
            for rule in active.document_verifiable
        ]
        if not jobs:
            return {"findings": []}

        def judge_one(job: tuple[str, ActorRole, PolicyRule]) -> Finding:
            use_case_id, role, rule = job
            judgement = judge.judge(rule, state.document)
            return Finding(
                rule_id=rule.rule_id,
                use_case_id=use_case_id,
                role=role,
                verdict=judgement.verdict,
                evidence_quote=judgement.evidence_quote,
                evidence_chunk_id=judgement.evidence_chunk_id,
                reasoning=judgement.reasoning,
                citation=rule.source,
                confidence=judgement.confidence,
            )

        if max_workers <= 1:
            return {"findings": [judge_one(job) for job in jobs]}
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            return {"findings": list(pool.map(judge_one, jobs))}

    def node_assemble_report(state: ComplianceCheckState) -> dict:
        # Reported, never judged: applicable obligations a technical file cannot evidence. Omitting
        # them would read as full coverage of the Chapter III duties, which it is not.
        outstanding: dict[ActorRole, list[str]] = {}
        for active in state.active:
            for rule in active.not_document_verifiable + active.postponed:
                ids = outstanding.setdefault(active.role, [])
                if rule.rule_id not in ids:
                    ids.append(rule.rule_id)
        outstanding = {role: sorted(ids) for role, ids in outstanding.items() if ids}
        return {
            "report": ComplianceReport(
                system_id=state.system_id,
                act_version_date=spec.act_version_date,
                spec_version=spec.spec_version,
                generated_at=datetime.now(UTC),
                classification=state.classification,
                findings=state.findings,
                not_document_verifiable=outstanding,
                provider_reallocation=state.provider_reallocation,
                deployer_type=state.deployer_type,
                summary=_summarise(state.findings),
            )
        }

    g = StateGraph(ComplianceCheckState)
    g.add_node("roles", node_roles)
    g.add_node("select_rules", node_select_rules)
    g.add_node("check_compliance", node_check_compliance)
    g.add_node("assemble_report", node_assemble_report)
    g.add_edge(START, "roles")
    g.add_edge("roles", "select_rules")
    g.add_edge("select_rules", "check_compliance")
    g.add_edge("check_compliance", "assemble_report")
    g.add_edge("assemble_report", END)
    return g.compile()


def analyse(
    document: str,
    classification: ClassificationResult,
    spec: PolicySpec,
    brain: Brain,
    judge: LLMJudge | None = None,
    system_id: str = "system",
    max_workers: int = DEFAULT_WORKERS,
    questions: dict[str, Question] | None = None,
) -> ComplianceReport:
    """Check one system's documentation against every obligation its classification activates.

    `brain` answers the Art. 25 role question, and is REQUIRED with no default — unlike `judge`,
    which this layer owns and can therefore build for itself. A brain is an implementation from the
    other layer, so defaulting to one would mean this module importing it, which is exactly the
    dependency the two layers are built to avoid. The caller composing both supplies it
    (see pipeline.review).

    `questions` defaults to the context-free constant; pass `gap.roles.load_questions()` to anchor
    the question in the verbatim Articles, which any real review should do."""
    graph = build_graph(spec, judge or LLMJudge(), brain, max_workers, questions)
    with trace_run(f"gap:{system_id}", session_id=system_id):
        out = graph.invoke(
            ComplianceCheckState(
                system_id=system_id, document=document, classification=classification
            )
        )
    report = out["report"] if isinstance(out, dict) else out.report
    if report is None:
        raise RuntimeError("gap-analysis graph produced no report")
    return report
