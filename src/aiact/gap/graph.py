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
from datetime import UTC, date, datetime

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from aiact.brain import Brain
from aiact.document import check_size
from aiact.gap import roles as role_questions
from aiact.gap.criteria import aggregate_confidence, aggregate_reasoning, settle
from aiact.gap.judge import LLMJudge
from aiact.gap.rules import ActiveRules, TimingNotice, roles_with_rules, select_rules
from aiact.schemas.classification import ClassificationResult
from aiact.schemas.enums import (
    ActorCategory,
    ActorRole,
    ProviderReallocation,
    RealWorldTesting,
    Verdict,
)
from aiact.schemas.norm import NormKind, TemporalStatus
from aiact.schemas.policy import PolicyRule, PolicyRuleset
from aiact.schemas.question import Answer, Question, narrow
from aiact.schemas.report import ComplianceReport, Finding, ReportSummary, RuleTimingNotice
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
    real_world_testing: Answer | None = None
    active: list[ActiveRules] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    report: ComplianceReport | None = None


def _judgeable(notice: TimingNotice) -> bool:
    """A future duty with a known date that a technical file can evidence."""
    return (
        notice.status is TemporalStatus.UPCOMING
        and notice.application_date is not None
        and notice.rule.status == "active"
        and notice.rule.document_verifiable
    )


def _summarise(findings: list[Finding]) -> ReportSummary:
    """Count verdicts overall and per use case; future obligations go to `upcoming` by date.

    NOT_APPLICABLE is counted in neither `total_applicable` nor any verdict bucket: a rule that
    never activated is not a check that passed.
    """
    in_force = [f for f in findings if f.applies_from is None]
    by_date: dict[date, list[Finding]] = {}
    for finding in findings:
        if finding.applies_from is not None:
            by_date.setdefault(finding.applies_from, []).append(finding)
    summary = _count(in_force)
    return summary.model_copy(
        update={"upcoming": {day: _count(by_date[day]) for day in sorted(by_date)}}
    )


def _count(findings: list[Finding]) -> ReportSummary:
    """Verdict tallies for one group of findings, with per-use-case and per-role breakdowns."""

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
    spec: PolicyRuleset,
    judge: LLMJudge,
    brain: Brain,
    max_workers: int = DEFAULT_WORKERS,
    questions: dict[str, Question] | None = None,
    as_of_date: date | None = None,
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
        testing = role_questions.ask_real_world_testing(
            brain, state.document, state.classification.overall_risk_class, asked
        )
        if testing is not None:
            out["real_world_testing"] = testing
        return out

    def node_select_rules(state: ComplianceCheckState) -> dict:
        # Once per (use case, role). Selection is per use case because Art. 6 classifies per
        # intended purpose, and per role because the Regulation attaches duties to the role rather
        # than to the organisation — one party can hold several, and each is assessed separately.
        #
        # The Art. 25 answer comes in HERE, and it is the only thing `roles` supplies that selection
        # acts on. It adds one obligation and never removes any: Art. 25(2)'s cooperation duty has
        # no holder until the provider role has moved, so `AIA-RULE-IP-A25-2` appears exactly when
        # it did. The deployer-type answer is deliberately NOT passed — it resolves a condition on a
        # duty that exists either way, and gating on it would withhold an obligation the Act
        # creates.
        #
        # The Art. 50 duties come from the CLASSIFICATION, not from a question here — the cascade
        # answers them at `assemble`, for every system it classifies. They are the fourth thing that
        # can activate a rule, and the only one that is not a risk class: 50(2) reaches a
        # minimal-risk generator and no high-risk scorer owes any of Art. 50 at all.
        moved = narrow(state.provider_reallocation, ProviderReallocation)
        duties = state.classification.transparency_duties
        testing = narrow(state.real_world_testing, RealWorldTesting)
        # WHICH Art. 5(1) point banned the practice, read off the classification. It activates the
        # rules on the LAWFUL BRANCH of point (h): real-time remote biometric identification for
        # law enforcement is banned "unless and in so far as such use is strictly necessary", and a
        # deployer running it under an Art. 5(5) national authorisation still owes Art. 5(2), (3)
        # and (4). Every other point of Art. 5 bans outright and matches no rule.
        practice = state.classification.prohibited_practice
        return {
            "active": [
                select_rules(
                    spec,
                    uc,
                    role,
                    reallocation=moved,
                    transparency_duties=duties,
                    real_world_testing=testing,
                    prohibited_practice=practice,
                    as_of_date=as_of_date,
                )
                for uc in state.classification.use_cases
                for role in roles
            ]
        }

    def node_check_compliance(state: ComplianceCheckState) -> dict:
        # Each job is judged against the whole document. Sound while a classification carries one
        # use case; with several, evidence written about one intended purpose can be credited to
        # another. Scoping it requires knowing which passages belong to which use case — the
        # decomposition problem, tracked in M7.
        # A future duty is judged too, carrying its date, so the reader learns now whether the
        # document will be ready. A duty whose date waits on an unsettled route is not judged.
        jobs: list[tuple[str, ActorRole, PolicyRule, date | None]] = [
            (active.use_case_id, active.role, rule, None)
            for active in state.active
            for rule in active.document_verifiable
        ] + [
            (active.use_case_id, active.role, notice.rule, notice.application_date)
            for active in state.active
            for notice in active.upcoming
            if _judgeable(notice)
        ]
        if not jobs:
            return {"findings": []}

        def judge_one(job: tuple[str, ActorRole, PolicyRule, date | None]) -> Finding:
            use_case_id, role, rule, applies_from = job
            judgement = judge.judge(rule, state.document)
            # An aggregate rule's verdict is recomputed here from its declared criteria, not taken
            # from the judge: a criterion the judge skipped becomes NEEDS_REVIEW, not a silent pass.
            verdict, criteria = settle(rule, judgement.verdict, judgement.criteria)
            reasoning = judgement.reasoning
            confidence = judgement.confidence
            if criteria:
                reasoning = aggregate_reasoning(rule, criteria)
                confidence = aggregate_confidence(criteria)
            return Finding(
                rule_id=rule.rule_id,
                use_case_id=use_case_id,
                role=role,
                verdict=verdict,
                evidence_quote=judgement.evidence_quote,
                evidence_chunk_id=judgement.evidence_chunk_id,
                reasoning=reasoning,
                citation=rule.source,
                confidence=confidence,
                criteria=criteria,
                # What the judge was SHOWN, taken from the rule rather than from the reply: the
                # model is not asked whether it leaned on the guidance, and a self-report would be
                # the wrong evidence for it anyway. The claim this records is "interpretation was in
                # context for this verdict", which is a fact about the prompt.
                guidance=list(rule.guidance_sources),
                applies_from=applies_from,
            )

        if max_workers <= 1:
            return {"findings": [judge_one(job) for job in jobs]}
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            return {"findings": list(pool.map(judge_one, jobs))}

    def node_assemble_report(state: ComplianceCheckState) -> dict:
        # Reported, never judged: applicable obligations a technical file cannot evidence. Omitting
        # them would read as full coverage of the Chapter III duties, which it is not.
        outstanding: dict[ActorRole, list[str]] = {}
        timing_not_active: list[RuleTimingNotice] = []
        for active in state.active:
            for rule in active.not_document_verifiable + active.postponed:
                if rule.report_as_public_authority_notice:
                    continue
                ids = outstanding.setdefault(active.role, [])
                if rule.rule_id not in ids:
                    ids.append(rule.rule_id)
            for notice in active.upcoming + active.timing_unresolved:
                if notice.status is TemporalStatus.UPCOMING and _judgeable(notice):
                    continue
                timing_not_active.append(
                    RuleTimingNotice(
                        rule_id=notice.rule.rule_id,
                        use_case_id=active.use_case_id,
                        role=active.role,
                        status=(
                            "upcoming"
                            if notice.status.value == "upcoming"
                            else "classification_required"
                        ),
                        application_date=notice.application_date,
                        route=notice.route,
                        legal_basis_segment_ids=list(notice.legal_basis_spans),
                    )
                )
        outstanding = {role: sorted(ids) for role, ids in outstanding.items() if ids}
        permissions: dict[ActorRole, list[str]] = {}
        rights: dict[ActorRole, list[str]] = {}
        legal_consequences: dict[ActorRole, list[str]] = {}
        conditional_applicability: dict[ActorRole, list[str]] = {}
        public_authority_statements: list[str] = []
        for active in state.active:
            active_rule_ids = {rule.rule_id for rule in active.all_rules}
            for report_norm in spec.report_norms:
                if not active_rule_ids.intersection(report_norm.activation_rule_ids):
                    continue
                if ActorCategory.PUBLIC_AUTHORITY in report_norm.actor_categories:
                    if report_norm.norm_id not in public_authority_statements:
                        public_authority_statements.append(report_norm.norm_id)
                    continue
                # Activation tells us WHEN the non-judged statement becomes relevant;
                # its canonical actor tells us WHO receives it in the report.  They usually
                # coincide, but Article 59's prospective-provider permission is conditioned by
                # duties split across a prospective provider, a provider, and a sandbox
                # participant. Rendering it under every activating duty-holder would silently
                # change who is allowed to use the route.
                # Only a SUPPORTED-OPERATOR actor narrows the audience, because only those roles
                # are ever reported for. A statement whose actor is an external party — Art.
                # 25(4)'s open-source carve-out addresses the third-party supplier — qualifies the
                # reader's own activated duty, and filtering on that actor would delete it from
                # every report instead of moving it to another one.
                exact_actor_roles = {
                    covered
                    for actor in report_norm.actors
                    if actor in {role.value for role in ActorRole}
                    and ActorRole.from_value(actor).category is ActorCategory.SUPPORTED_OPERATOR
                    for covered in ActorRole.from_value(actor).covered_roles
                }
                if (
                    not report_norm.applies_to_all_actors
                    and exact_actor_roles
                    and active.role not in exact_actor_roles
                ):
                    continue
                destination = {
                    NormKind.PERMISSION: permissions,
                    NormKind.ENTITLEMENT: rights,
                    NormKind.LEGAL_CONSEQUENCE: legal_consequences,
                }.get(report_norm.kind, conditional_applicability)
                ids = destination.setdefault(active.role, [])
                if report_norm.norm_id not in ids:
                    ids.append(report_norm.norm_id)
        permissions = {role: sorted(ids) for role, ids in permissions.items() if ids}
        rights = {role: sorted(ids) for role, ids in rights.items() if ids}
        legal_consequences = {role: sorted(ids) for role, ids in legal_consequences.items() if ids}
        conditional_applicability = {
            role: sorted(ids) for role, ids in conditional_applicability.items() if ids
        }
        public_authority_statements.sort()
        return {
            "report": ComplianceReport(
                system_id=state.system_id,
                act_version_date=spec.act_version_date,
                spec_version=spec.spec_version,
                generated_at=datetime.now(UTC),
                classification=state.classification,
                findings=state.findings,
                not_document_verifiable=outstanding,
                timing_not_active=timing_not_active,
                permissions=permissions,
                rights=rights,
                legal_consequences=legal_consequences,
                conditional_applicability=conditional_applicability,
                public_authority_statements=public_authority_statements,
                provider_reallocation=state.provider_reallocation,
                deployer_type=state.deployer_type,
                real_world_testing=state.real_world_testing,
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
    spec: PolicyRuleset,
    brain: Brain,
    judge: LLMJudge | None = None,
    system_id: str = "system",
    max_workers: int = DEFAULT_WORKERS,
    questions: dict[str, Question] | None = None,
    as_of_date: date | None = None,
) -> ComplianceReport:
    """Check one system's documentation against every obligation its classification activates.

    `brain` answers the Art. 25 role question, and is REQUIRED with no default — unlike `judge`,
    which this layer owns and can therefore build for itself. A brain is an implementation from the
    other layer, so defaulting to one would mean this module importing it, which is exactly the
    dependency the two layers are built to avoid. The caller composing both supplies it
    (see pipeline.review).

    `questions` defaults to the context-free constant; pass `gap.roles.load_questions()` to anchor
    the question in the verbatim Articles, which any real review should do."""
    check_size(document)
    graph = build_graph(spec, judge or LLMJudge(), brain, max_workers, questions, as_of_date)
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
