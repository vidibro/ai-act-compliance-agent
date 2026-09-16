"""What the reader actually receives.

Everything else in this suite tests which obligations ACTIVATE. This file tests that the ones which
activate arrive intact, and it covers the half of the ruleset where that is easiest to lose.

A `document_verifiable: false` obligation — an appointment, a filing, a contract, a process — never
reaches the judge, so it never becomes a Finding carrying reasoning of its own. The report holds it
as a rule id and nothing else, and everything that makes it actionable lives on the rule in the
spec:

    activation_condition   WHICH members of the role owe it (Art. 22(1): third-country providers)
    evidence_expected      WHAT would satisfy it, including gaps the rule declares about itself
    effective_date_note    WHY its date is not the one the reader expects

A renderer that prints the id alone therefore drops the obligation rather than abbreviating it.
These tests derive the rules carrying each field from the spec and require the rendered report to
carry it too.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from aiact.policy_loader import load_policy_spec
from aiact.reporting import render_report
from aiact.schemas.classification import (
    ClassificationEvidence,
    ClassificationResult,
    UseCaseClassification,
)
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    DeployerType,
    OpenSourceRelease,
    ProviderReallocation,
    RealWorldTesting,
    RiskClass,
    SystemicRisk,
    Verdict,
)
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Answer
from aiact.schemas.report import (
    DISCLAIMER,
    ComplianceReport,
    Finding,
    ReportSummary,
    _release_note,
)


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


def _answer(report, value) -> Answer:
    """One cascade answer, on the source the fixture already carries."""
    return Answer(
        value=value,
        reasoning="fixture",
        confidence="high",
        source=report.classification.triggered_by[0].source,
    )


def _finding(spec, rule) -> Finding:
    """The Finding a `document_verifiable` rule produces once a judge has looked at it."""
    return Finding(
        rule_id=rule.rule_id,
        use_case_id="uc",
        role=ActorRole.PROVIDER,
        verdict=Verdict.PASS,
        reasoning="fixture",
        citation=rule.source,
        confidence="high",
    )


def _report(
    spec, outstanding: dict[ActorRole, list[str]], findings: list[Finding] | None = None
) -> ComplianceReport:
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689", article=6, act_version_date=spec.act_version_date
    )
    use_case = UseCaseClassification(
        use_case_id="uc",
        description="a system",
        risk_class=RiskClass.HIGH_RISK,
        annex_iii_area=AnnexIIIArea.EMPLOYMENT,
        reasoning="fixture",
        confidence="high",
        triggered_by=[ClassificationEvidence(source=source, reasoning="fixture")],
    )
    return ComplianceReport(
        system_id="sys",
        act_version_date=spec.act_version_date,
        spec_version=spec.spec_version,
        generated_at=datetime.now(UTC),
        classification=ClassificationResult(
            use_cases=[use_case],
            overall_risk_class=RiskClass.HIGH_RISK,
            reasoning="fixture",
            triggered_by=[ClassificationEvidence(source=source, reasoning="fixture")],
            confidence="high",
        ),
        findings=findings or [],
        not_document_verifiable=outstanding,
        summary=ReportSummary(total_applicable=0, passed=0, gaps=0, inadequate=0, needs_review=0),
    )


def test_every_condition_the_spec_writes_reaches_the_reader(spec):
    """A CONDITION THAT IS NOT RENDERED IS A CONDITION THAT WAS DROPPED, and dropping it turns a
    narrow duty into a universal one.

    `PolicyRule.activation_condition` says of itself: "IT NARROWS THE DUTY-HOLDER, NOT THE REPORT.
    Such a rule is still selected, still listed under its role… the obligation is stated WITH its
    condition rather than as an unqualified duty of every deployer." `select_rules` holds up its
    half — the rule is never withheld. This is the other half.

    Every rule carrying a condition is rendered here and the condition must survive. DERIVED from
    the spec, so a rule that gains a condition is covered without anyone remembering to add it."""
    conditioned = [r for r in spec.rules if r.activation_condition]
    assert conditioned, "no rule carries an activation_condition — re-derive this test"

    # EACH RULE THROUGH THE PATH IT WOULD REALLY TAKE. A `document_verifiable` rule becomes a
    # Finding and renders through the finding branch; routing it through the outstanding branch
    # would test a path production never reaches for it, and pass a renderer that drops the
    # condition from the branch it does.
    judged = [r for r in conditioned if r.document_verifiable]
    text = render_report(
        _report(
            spec,
            {ActorRole.PROVIDER: [r.rule_id for r in conditioned if not r.document_verifiable]},
            findings=[_finding(spec, r) for r in judged],
        ),
        spec,
    )
    for rule in conditioned:
        assert rule.rule_id in text, f"{rule.rule_id} is not rendered at all"
        # THE WHOLE CONDITION, not an opening that a truncating renderer would also satisfy.
        # Art. 27's condition opens "Art. 27(1) does not bind every deployer of an Annex III
        # system" and only later says which deployers it DOES bind; a prefix match accepts a
        # report that gives a public body the negative half and stops.
        assert " ".join(rule.activation_condition.split()) in " ".join(text.split()), (
            f"{rule.rule_id} is rendered without its activation_condition. A reader is told to "
            f"confirm an obligation the Act does not put on them."
        )


def test_permissions_and_legal_effects_are_rendered_outside_the_verdict_list(spec):
    report = _report(spec, {}).model_copy(
        update={
            "permissions": {ActorRole.PROVIDER: ["AIA-NORM-A015-P4-REDUNDANCY"]},
            "legal_consequences": {
                ActorRole.PROVIDER: ["AIA-NORM-A017-P4-FINANCIAL-DEEMING"]
            },
            "conditional_applicability": {
                ActorRole.PROVIDER: ["AIA-NORM-A010-P6-TESTING-DATA-ONLY"]
            },
            "public_authority_statements": [
                "AIA-NORM-A005-P2-CONFIRM-TARGETED-IDENTITY"
            ],
        }
    )
    text = render_report(report, spec)
    assert "permitted implementation routes:" in text
    assert "AIA-NORM-A015-P4-REDUNDANCY" in text
    assert "conditional legal effects:" in text
    assert "AIA-NORM-A017-P4-FINANCIAL-DEEMING" in text
    assert "Article 17(1)(g), (h), and (i) remain independently required" in text
    assert "conditional scope limits:" in text
    assert "AIA-NORM-A010-P6-TESTING-DATA-ONLY" in text
    assert (
        "limit the Article 10(2) to (4) and Article 4a(1) requirements to testing datasets"
        in text
    )
    assert "public authority (not a report actor)" in text
    assert "AIA-NORM-A005-P2-CONFIRM-TARGETED-IDENTITY" in text


def test_an_obligation_nobody_judged_still_says_what_would_satisfy_it(spec):
    """`evidence_expected` reaches the judge only for `document_verifiable: true` rules — the judge
    returns NOT_APPLICABLE before building a prompt otherwise. For every process obligation it is
    therefore the renderer or nobody.

    AIA-ALL-A49-4 is the case that makes this load-bearing rather than cosmetic. The spec declares
    that rule deliberately under-inclusive — `AnnexIIIArea` cannot express "Annex III point 1 used
    FOR law enforcement", so a police face-matching system is not selected for it — and says the gap
    "is recorded in `evidence_expected` so a biometrics provider is told to check it themselves".
    That sentence is only true if this holds."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-ALL-A49-4")
    assert not rule.document_verifiable, "re-derive this test: the rule now reaches the judge"
    text = " ".join(
        render_report(_report(spec, {ActorRole.PROVIDER: [rule.rule_id]}), spec).split()
    )
    assert " ".join(rule.evidence_expected.split()) in text


def test_a_timing_note_travels_with_the_obligation_it_qualifies(spec):
    """`effective_date_note` says of itself: "carried to the report, not left in a comment only we
    read." The Section 5 rules apply from 2 August 2026 while the Section 2 requirements they attest
    to wait until December 2027, and a reader meeting that unexplained concludes the tool is broken
    — the damaging response being to disregard the date rather than the note."""
    noted = [r for r in spec.rules if r.effective_date_note and not r.document_verifiable]
    assert noted, "no unjudged rule carries an effective_date_note — re-derive this test"
    text = " ".join(
        render_report(_report(spec, {ActorRole.PROVIDER: [r.rule_id for r in noted]}), spec).split()
    )
    for rule in noted:
        assert " ".join(rule.effective_date_note.split()) in text, rule.rule_id
        assert rule.effective_date is not None and rule.effective_date.isoformat() in text


def test_a_role_change_the_report_found_is_stated_in_the_report(spec):
    """Art. 25 moves the provider role, and the report answers the question — but the answer is an
    enum, and "substantial_modification" beside a column of provider obligations does not tell a
    distributor that the column is now theirs.

    `provider_reallocation_note` is the sentence that does, and it carries the half that is
    invisible from the value: Art. 25(2) takes the original provider OUT and puts a cooperation
    duty on them. A report that computes the note and does not print it has found the reallocation
    and told nobody."""
    report = _report(spec, {})
    report.provider_reallocation = Answer(
        value=ProviderReallocation.SUBSTANTIAL_MODIFICATION,
        reasoning="fixture",
        confidence="high",
        source=report.classification.triggered_by[0].source,
    )
    assert report.provider_reallocation_note, "re-derive this test: the note is no longer composed"
    text = " ".join(render_report(report, spec).split())
    assert " ".join(report.provider_reallocation_note.split()) in text


def test_a_deployer_is_told_which_side_of_the_condition_it_falls_on(spec):
    """Two duties turn on the kind of organisation deploying — Art. 27's impact assessment and
    Art. 49(3)'s registration — and they do not answer alike. `deployer_type_note` is composed
    precisely because a reader told about one would assume the other."""
    report = _report(spec, {})
    report.deployer_type = Answer(
        value=DeployerType.PUBLIC_BODY,
        reasoning="fixture",
        confidence="high",
        source=report.classification.triggered_by[0].source,
    )
    assert report.deployer_type_note, "re-derive this test: the note is no longer composed"
    text = " ".join(render_report(report, spec).split())
    assert " ".join(report.deployer_type_note.split()) in text


def test_a_reader_is_told_when_six_obligations_were_withheld(spec):
    """The Art. 60 answer is the only one in this report that DROPS obligations, so it is the one
    a renderer must not skip.

    Every other note here resolves a condition on a duty that is listed either way — the reader
    loses a sentence if it goes missing. This one decides whether four rules appear at all, and a
    report that withholds them silently is indistinguishable from a report about a system nobody
    asked. Asserted on both answers that matter: the withholding, and the ordinary silence that
    does not withhold, because a reader shown the duties needs to know they are conditional."""
    for value in (RealWorldTesting.NONE, RealWorldTesting.NOT_STATED):
        report = _report(spec, {})
        report.real_world_testing = Answer(
            value=value,
            reasoning="fixture",
            confidence="high",
            source=report.classification.triggered_by[0].source,
        )
        note = report.real_world_testing_note
        assert note, f"no note composed for {value.value}"
        assert " ".join(note.split()) in " ".join(render_report(report, spec).split()), value.value


def test_a_verdict_says_which_use_case_it_is_about_and_how_sure_it_is(spec):
    """One rule is judged once per use case, so a two-purpose system produces two findings with the
    same rule id and role. Unlabelled they are a pass and a gap on adjacent lines about the same
    Article, and a reader resolving the contradiction in the favourable direction concludes the
    obligation is met. The confidence is the other half: a low-confidence PASS that renders exactly
    like a confident one is the false pass this whole ruleset is built to avoid."""
    rule = next(r for r in spec.rules if r.document_verifiable)
    report = _report(spec, {}, findings=[_finding(spec, rule)])
    report.findings[0].confidence = "low"
    text = render_report(report, spec)
    assert "uc" in text and "low confidence" in text


def test_the_report_says_it_is_not_legal_advice(spec):
    """The disclaimer is a field on the report with a default, so a renderer that never reads it
    still produces something that looks complete. Its third paragraph is also the only other place
    Art. 25 is explained — that silence about a role change is not a finding that none happened."""
    text = " ".join(render_report(_report(spec, {}), spec).split())
    for paragraph in DISCLAIMER.split("\n\n"):
        assert " ".join(paragraph.split()) in text


@pytest.mark.parametrize(
    ("risk", "release", "expected"),
    [
        (SystemicRisk.DESIGNATED, OpenSourceRelease.NOT_OPEN, "SYSTEMIC RISK IS ESTABLISHED"),
        (SystemicRisk.HIGH_IMPACT_CAPABILITIES, OpenSourceRelease.FULLY_OPEN, "DISAPPLIED"),
        (SystemicRisk.BELOW_THRESHOLD, OpenSourceRelease.FULLY_OPEN, "ONE HALF OF THE CARVE-OUT"),
        (SystemicRisk.NOT_STATED, OpenSourceRelease.NOT_STATED, "UNANSWERED"),
    ],
)
def test_a_model_is_told_which_side_of_each_chapter_v_gate_it_falls_on(
    spec, risk, release, expected
):
    """THE OTHER HALF OF NOT WITHHOLDING.

    Chapter V lists every obligation for every model, because neither of its gates is a fact a
    model card reliably settles. That is only defensible if the reader is then told what their own
    document says — otherwise the report answers "Art. 55 applies if you carry systemic risk",
    which they knew before they ran it.

    The `FULLY_OPEN` rows are the pair that matters, and they are not opposites. Above the
    threshold the carve-out is DISAPPLIED outright. Below it the licence half is answered and the
    Art. 51 half is not — a stated compute figure defeats the Art. 51(2) presumption and settles
    neither limb of Art. 51(1) — so the report says what the release establishes and stops short of
    saying the obligations are lifted. A note composed from the licence alone would tell either
    provider that four obligations had fallen away."""
    report = _report(spec, {})
    report.classification.use_cases[0].systemic_risk = _answer(report, risk)
    report.classification.use_cases[0].open_source_release = _answer(report, release)
    assert report.chapter_v_gate_note, "the note is no longer composed — re-derive this test"
    text = " ".join(render_report(report, spec).split())
    assert " ".join(report.chapter_v_gate_note.split()) in text
    assert expected in text


def test_a_document_that_is_not_a_model_gets_no_chapter_v_note(spec):
    """`None` means the questions were never put, and it must not read as "no systemic risk". An
    Art. 6-track system is not a model, and a paragraph about Art. 51 in its report would send its
    provider to read a chapter that does not reach them."""
    assert _report(spec, {}).chapter_v_gate_note is None


@pytest.mark.parametrize("risk", list(SystemicRisk))
@pytest.mark.parametrize("release", list(OpenSourceRelease))
def test_no_pair_of_answers_lets_the_report_lift_a_duty_without_naming_art_51(risk, release):
    """THE ONLY PLACE THIS TOOL SAYS AN OBLIGATION IS LIFTED, and it must never say it alone.

    Art. 53(2) and Art. 54(6) are both disapplied for a general-purpose AI model with systemic
    risk, so the open-source answer decides nothing by itself — it decides with Art. 51. And
    Art. 51 is a question no document settles in the negative: Art. 51(2) is a presumption running
    one way, so a stated compute figure below 10^25 defeats the presumption and leaves Art. 51(1)(a)
    standing as a substantive test and Art. 51(1)(b) standing as a Commission designation available
    at any compute.

    A report that says "Art. 53(2) lifts" without naming the Article that disapplies it clears the
    Annex XI technical documentation, the Annex XII downstream information and the whole of Art. 54
    on the single easiest number in a model card to understate.

    NOT THE SAME CHECK AS `test_neither_chapter_v_gate_is_allowed_to_clear_an_obligation`. That one
    compares the rules SELECTED across the gate answers and they are identical, as they should be.
    The clearance this catches is not in the rule set — it is in the sentence beside it, which a
    reader acts on and a rule-set comparison cannot see."""
    note = _release_note(risk, release)
    if "lift" not in note:
        return
    assert "Art. 51" in note, (
        f"the release note for {risk.value}/{release.value} states a Chapter V obligation is "
        f"lifted and never names Art. 51, which is what disapplies both carve-outs: "
        f"{note}"
    )


def test_no_document_can_put_a_model_outside_article_51():
    """`carries_systemic_risk` is True or None and NEVER False, and the whole Chapter V report
    rests on it.

    Art. 51(1) is a disjunction — high impact capabilities on limb (a), a Commission designation on
    limb (b) — and a model card can establish either and neither can be ruled out from one. The
    compute figure Art. 51(2) speaks to feeds a PRESUMPTION, and defeating a presumption is not
    proving its conclusion false. So there is no answer to this question that means "no systemic
    risk", and any enum member returning False would hand the open-source carve-out to a model that
    had merely stated a small number.

    DERIVED over the enum, so a member added later is covered without anyone remembering."""
    assert all(risk.carries_systemic_risk is not False for risk in SystemicRisk)


def test_a_model_is_told_the_transitional_deadline_written_for_it(spec):
    """Art. 111(3) is the one transitional limb addressed to a general-purpose model provider, and
    it is the one the other limbs cannot reach.

    `_article_111_2_note` returns None where no use case is HIGH_RISK, which is always true of a
    GPAI_MODEL classification, and `_article_111_4_note` fires on an Art. 50 duty a model never
    owes. So without a limb of its own the whole `legacy_system_note` is None for exactly the
    reader Art. 111(3) is written for — while every Chapter V rule beside it carries
    `effective_date: 2025-08-02` and the scope note says those duties are live now.

    THE DIRECTION MATTERS. Art. 111(3) is a DEFERRAL: a model placed before 2 August 2025 owes the
    Chapter V duties by 2 August 2027. Silence over-reports, which costs a reader a conversation
    with their adviser; but silence here also leaves a provider reading a 2025 date against a model
    it shipped in 2024 and concluding it is two years in breach of duties it is not yet late on."""
    report = _report(spec, {})
    report.classification.use_cases[0].risk_class = RiskClass.GPAI_MODEL
    report.classification.overall_risk_class = RiskClass.GPAI_MODEL
    note = report.legacy_system_note
    assert note, "a model gets no legacy note at all — Art. 111(3) reaches no reader"
    assert "Art. 111(3)" in note and "2 AUGUST 2027" in note
    assert " ".join(note.split()) in " ".join(render_report(report, spec).split())


def test_a_report_says_how_many_obligations_nobody_judged(spec):
    """`total_applicable` counts VERDICTS, and half this ruleset produces none.

    A process obligation never reaches the judge, so it is listed in the body and counted in no
    bucket. For a general-purpose AI model that is every obligation it owes, and the last line of
    the report then reads "0 applicable — 0 pass, 0 gap, 0 inadequate, 0 needs review" underneath a
    column of fourteen duties. That is the exact shape of a clean bill of health, printed over a
    report that judged nothing — and the summary line is the one a reader scans."""
    outstanding = [r.rule_id for r in spec.rules if not r.document_verifiable][:3]
    text = render_report(_report(spec, {ActorRole.PROVIDER: outstanding}), spec)
    assert "0 applicable" in text
    assert f"{len(outstanding)} further obligations listed above that nobody judged" in text


# Every way the Act writes a deadline, so a period in a qualifier is matched wherever it appears.
# "working days" and "calendar days" come before the bare form: an alternation that tries `days`
# first would match the tail of "15 working days" and compare the wrong unit.
_PERIOD = re.compile(
    r"\b(\d+)\s+(working\s+days?|calendar\s+days?|days?|weeks?|months?|years?)\b", re.I
)


def test_a_deadline_in_a_qualifier_reaches_the_reader_of_an_unjudged_rule(spec):
    """`qualifier_context` IS RENDERED BY THE JUDGE AND BY NOBODY ELSE, so on a rule no judge sees
    it is a field the reader never receives.

    `qualified_by` resolves neighbouring provisions into the rule at load, and the judge prints them
    in their own block beside the requirement. `_outstanding_block` — the branch that renders a
    `document_verifiable: false` rule — prints `evidence_expected` and stops. The two facts are
    fine apart and wrong together: seven rules today carry a qualifier and are never judged, and for
    each of them the qualifying text is written into the spec, resolved from the Act at load, and
    shown to no one.

    A DEADLINE IS THE PART THAT CANNOT SURVIVE THAT. Art. 79(2) gives the market surveillance
    authority's requirement a ceiling of the shorter of 15 working days or the sectoral period, and
    Art. 79(5) makes a missed period the trigger for provisional measures — a procedure written to
    a 30-day escalation satisfies every word the report would otherwise print. So where a qualifier
    states a period, `evidence_expected` must state the same period.

    IT CHECKS THE PERIODS AND NOT THE PROSE, because only the periods are mechanical. A qualifier
    can lose an addressee, a condition or a menu of remedies and nothing here notices; those stay a
    reading job, and this is the one part of the class a test can hold."""
    dropped: list[str] = []
    for rule in spec.rules:
        if rule.document_verifiable or not rule.qualifier_context:
            continue
        qualified = {(m[0], m[1].lower()) for m in _PERIOD.findall(rule.qualifier_context)}
        stated = {(m[0], m[1].lower()) for m in _PERIOD.findall(rule.evidence_expected)}
        for count, unit in sorted(qualified - stated):
            dropped.append(
                f"{rule.rule_id} qualifier says {count} {unit}, evidence_expected does not"
            )
    assert not dropped, (
        f"a deadline resolved into a rule nobody judges, and rendered to nobody: {dropped}. "
        f"`qualifier_context` reaches the judge only; on an unjudged rule `evidence_expected` is "
        f"the whole of what the reader gets, so a period stated only in the qualifier is a period "
        f"the reader is never given."
    )
