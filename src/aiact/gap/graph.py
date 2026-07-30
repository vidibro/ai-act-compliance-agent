"""The gap-analysis graph: a classified system plus its documentation in, a ComplianceReport out.

Three nodes, and only one of them uses a model:

    select_rules      which obligations apply, per use case      — pure data (gap/rules.py)
    check_compliance  does the documentation satisfy each one    — one LLM call per rule
    assemble_report   findings, outstanding confirmations, counts — pure data

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

from aiact.gap.judge import LLMJudge
from aiact.gap.rules import ActiveRules, select
from aiact.schemas.classification import ClassificationResult
from aiact.schemas.enums import ActorRole, Verdict
from aiact.schemas.policy import PolicyRule, PolicySpec
from aiact.schemas.report import ComplianceReport, Finding, ReportSummary
from aiact.tracing import trace_run

DEFAULT_WORKERS = 8


class ComplianceCheckState(BaseModel):
    """What flows through the graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    system_id: str
    document: str
    classification: ClassificationResult
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
    overall = count_verdicts(findings)
    return overall.model_copy(update={"per_use_case": per_use_case or None})


def build_graph(
    spec: PolicySpec,
    judge: LLMJudge,
    role: ActorRole = ActorRole.PROVIDER,
    max_workers: int = DEFAULT_WORKERS,
):
    """Compile the gap-analysis graph for one ruleset and one judge."""

    def node_select_rules(state: ComplianceCheckState) -> dict:
        return {"active": [select(spec, uc, role) for uc in state.classification.use_cases]}

    def node_check_compliance(state: ComplianceCheckState) -> dict:
        # Each job is judged against the whole document. Sound while a classification carries one
        # use case; with several, evidence written about one intended purpose can be credited to
        # another. Scoping it requires knowing which passages belong to which use case — the
        # decomposition problem, tracked in M7.
        jobs: list[tuple[str, PolicyRule]] = [
            (active.use_case_id, rule)
            for active in state.active
            for rule in active.document_verifiable
        ]
        if not jobs:
            return {"findings": []}

        def judge_one(job: tuple[str, PolicyRule]) -> Finding:
            use_case_id, rule = job
            judgement = judge.judge(rule, state.document)
            return Finding(
                rule_id=rule.rule_id,
                use_case_id=use_case_id,
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
        outstanding = sorted(
            {
                rule.rule_id
                for active in state.active
                for rule in active.not_document_verifiable + active.postponed
            }
        )
        return {
            "report": ComplianceReport(
                system_id=state.system_id,
                act_version_date=spec.act_version_date,
                spec_version=spec.spec_version,
                generated_at=datetime.now(UTC),
                classification=state.classification,
                findings=state.findings,
                not_document_verifiable=outstanding,
                summary=_summarise(state.findings),
            )
        }

    g = StateGraph(ComplianceCheckState)
    g.add_node("select_rules", node_select_rules)
    g.add_node("check_compliance", node_check_compliance)
    g.add_node("assemble_report", node_assemble_report)
    g.add_edge(START, "select_rules")
    g.add_edge("select_rules", "check_compliance")
    g.add_edge("check_compliance", "assemble_report")
    g.add_edge("assemble_report", END)
    return g.compile()


def analyse(
    document: str,
    classification: ClassificationResult,
    spec: PolicySpec,
    judge: LLMJudge | None = None,
    system_id: str = "system",
    role: ActorRole = ActorRole.PROVIDER,
    max_workers: int = DEFAULT_WORKERS,
) -> ComplianceReport:
    """Check one system's documentation against every obligation its classification activates."""
    graph = build_graph(spec, judge or LLMJudge(), role, max_workers)
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
