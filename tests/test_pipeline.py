"""The composed review: one document in, one ComplianceReport out.

Both halves are stubbed — a ScriptedBrain for the classification and a fixed-verdict judge — so
what is pinned here is the SEAM: which classifications reach the obligation check, which are
stopped before it, and whether a report that checked nothing says so.

The last point is why this file exists at all. Neither existing eval layer can catch it: Layer 1
stops at the risk class, and Layer 2 is handed the correct classification and never sees a
misclassification propagate. An empty `findings` list is indistinguishable from a clean bill of
health unless something asserts otherwise, and that failure mode is only reachable here.
"""

from __future__ import annotations

import pytest

from aiact.classify.scripted_brain import ScriptedBrain
from aiact.gap.judge import Judgement
from aiact.pipeline import review
from aiact.policy_loader import load_policy_spec
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    GpaiStatus,
    ProhibitedPractice,
    RiskClass,
    ScopeExclusion,
    TerritorialLink,
    TransparencyDuty,
    Verdict,
)

DOCUMENT = "# System card\n\n## Human oversight\n\nA panel reviews every recommendation.\n"


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


class StubJudge:
    """Answers PASS without a model. The judge's own behaviour is tested in test_gap_judge."""

    name = "stub"

    def __init__(self):
        self.calls = []

    def judge(self, rule, document):
        self.calls.append(rule.rule_id)
        return Judgement(
            verdict=Verdict.PASS,
            reasoning="stub",
            evidence_quote=None,
            evidence_chunk_id=None,
            confidence="high",
        )


def a_brain(**answers) -> ScriptedBrain:
    return ScriptedBrain({"is_ai": True, **answers})


def high_risk_brain() -> ScriptedBrain:
    """Annex III area plus profiling — the Art. 6(3) carve-back, so high_risk with no derogation."""
    return a_brain(prohibited=None, annex_iii=AnnexIIIArea.EMPLOYMENT, profiling=True)


# --- the happy path -------------------------------------------------------------------------------
def test_a_high_risk_document_is_classified_then_checked(spec):
    judge = StubJudge()
    report = review(DOCUMENT, spec, high_risk_brain(), judge=judge, system_id="sys-1")

    assert report.classification.overall_risk_class == RiskClass.HIGH_RISK
    assert judge.calls, "the obligation check never ran"
    assert report.findings, "a high-risk classification must produce findings"
    assert report.scope_note is None, "nothing was skipped, so nothing to explain"


def test_the_report_carries_the_classification_it_was_built_from(spec):
    """The report must be readable on its own — a finding cites a rule that a risk class activated,
    and without that class in the same document the citation cannot be checked."""
    report = review(DOCUMENT, spec, high_risk_brain(), judge=StubJudge(), system_id="sys-1")
    assert report.classification.use_cases[0].use_case_id == "sys-1"
    assert {f.use_case_id for f in report.findings} == {"sys-1"}


# --- the gate -------------------------------------------------------------------------------------
def test_a_prohibited_practice_is_never_checked_against_chapter_iii(spec):
    """Art. 5 bans the practice outright. Reporting documentation gaps against it would imply the
    system may ship once the paperwork is fixed."""
    judge = StubJudge()
    brain = a_brain(prohibited=ProhibitedPractice.SOCIAL_SCORING)
    report = review(DOCUMENT, spec, brain, judge=judge, system_id="sys-1")

    assert report.classification.overall_risk_class == RiskClass.PROHIBITED
    assert judge.calls == [], "the judge must not run on a prohibited practice"
    assert report.findings == []
    assert report.scope_note and "prohibited" in report.scope_note.lower()


def test_an_unresolved_classification_is_not_checked_either(spec):
    """needs_review means we do not know which obligations apply. Checking anyway would hand a
    provider findings to act on that may not be owed."""
    brain = ScriptedBrain({"is_ai": True}, low_confidence=frozenset({"prohibited"}))
    judge = StubJudge()
    report = review(DOCUMENT, spec, brain, judge=judge, system_id="sys-1")

    assert report.classification.overall_risk_class == RiskClass.NEEDS_REVIEW
    assert judge.calls == []
    assert report.scope_note is not None


def test_an_empty_report_always_explains_itself(spec):
    """THE POINT OF THIS FILE. `findings == []` reads as 'nothing wrong'. Whenever the pipeline
    reaches that state deliberately, the report must say why in the report itself."""
    for brain in (
        a_brain(prohibited=ProhibitedPractice.SOCIAL_SCORING),
        ScriptedBrain({"is_ai": True}, low_confidence=frozenset({"prohibited"})),
    ):
        report = review(DOCUMENT, spec, brain, judge=StubJudge(), system_id="sys-1")
        assert report.findings == []
        assert report.scope_note, "an empty findings list must never stand unexplained"


# --- what the gate deliberately does NOT do -------------------------------------------------------
def test_a_not_high_risk_use_case_still_owes_article_6_4(spec):
    """The gate is not 'high risk only'. A provider claiming an Art. 6(3) derogation must still
    document that assessment and register it — gating on high_risk would drop a real obligation."""
    brain = a_brain(
        prohibited=None,
        annex_iii=AnnexIIIArea.EMPLOYMENT,
        profiling=False,
        derogation="narrow_procedural_task",
        significant_risk=False,
    )
    judge = StubJudge()
    report = review(DOCUMENT, spec, brain, judge=judge, system_id="sys-1")

    assert report.classification.overall_risk_class == RiskClass.NOT_HIGH_RISK
    outstanding = {r for ids in report.not_document_verifiable.values() for r in ids}
    checked = set(judge.calls) | outstanding
    assert "AIA-NHR-A06-4" in checked, "Art. 6(4) must survive a not_high_risk classification"


def test_a_minimal_system_still_owes_article_4(spec):
    """`minimal` means governed and lightly burdened, NOT ungoverned. Art. 4 binds providers and
    deployers of every AI system at every tier the Regulation reaches, so an empty report here
    would make `minimal` indistinguishable from `out_of_scope` — the collapse that tells a
    defence contractor they hold duties the legislator withheld, in reverse."""
    report = review(DOCUMENT, spec, a_brain(prohibited=None, annex_iii=None), judge=StubJudge())
    assert report.classification.overall_risk_class == RiskClass.MINIMAL
    # Nothing to JUDGE — Art. 4 is an organisational measure, not a property of the system.
    assert report.summary.total_applicable == 0
    assert report.not_document_verifiable[ActorRole.PROVIDER] == ["AIA-ALL-A04", "AIA-ALL-A79"]
    assert report.not_document_verifiable[ActorRole.DEPLOYER] == ["AIA-ALL-A04", "AIA-ALL-A79"]


def test_a_minimal_system_that_generates_content_owes_article_50(spec):
    """The tier-crossing case, end to end. `minimal` is the tier a rule gated on `high_risk` would
    miss entirely, and Art. 50(2) is a real duty of a text generator that owes nothing else. The
    duty comes from the classification's own transparency answer, not from the risk class."""
    brain = a_brain(
        prohibited=None,
        annex_iii=None,
        transparency=[TransparencyDuty.SYNTHETIC_CONTENT_MARKING],
    )
    report = review(DOCUMENT, spec, brain, judge=StubJudge())

    assert report.classification.overall_risk_class == RiskClass.MINIMAL
    # 50(2) binds the PROVIDER and is built into the system, so it is judged rather than deferred.
    assert "AIA-TR-A50-2" in {f.rule_id for f in report.findings}
    assert "AIA-TR-A50-2" not in report.not_document_verifiable.get(ActorRole.DEPLOYER, [])


def test_an_out_of_scope_system_owes_nothing_at_all(spec):
    """The contrast that gives the test above its meaning: an Art. 2 exclusion withholds the whole
    Regulation, Art. 4 included."""
    report = review(
        DOCUMENT,
        spec,
        a_brain(prohibited=None, scope=ScopeExclusion.MILITARY_DEFENCE_NATIONAL_SECURITY),
        judge=StubJudge(),
    )
    assert report.classification.overall_risk_class == RiskClass.OUT_OF_SCOPE
    assert report.not_document_verifiable == {}


def test_the_report_covers_both_duty_holders(spec):
    """Obligations attach to the ROLE, so one system produces two obligation sets. A report naming
    only the provider's is not narrower — it is misleading, because that provider's customers owe
    Arts. 26-27 on the same system and nothing else tells them so."""
    judge = StubJudge()
    report = review(DOCUMENT, spec, high_risk_brain(), judge=judge, system_id="sys-1")

    assert report.classification.overall_risk_class == RiskClass.HIGH_RISK
    outstanding = report.not_document_verifiable
    assert "AIA-PO-A17" in outstanding[ActorRole.PROVIDER]
    assert outstanding[ActorRole.DEPLOYER] == [
        "AIA-ALL-A04",
        "AIA-ALL-A79",
        "AIA-DP-A26",
        "AIA-DP-A27",
        "AIA-DP-A27-2",
        "AIA-DP-A27-3",
        "AIA-DP-A49-3",
        "AIA-DP-A86",
    ]
    # Every judged finding says whose duty it is, so the two sets never merge in a reader's eye.
    assert {f.role for f in report.findings} == {ActorRole.PROVIDER}
    assert (report.summary.per_role or {})[ActorRole.PROVIDER].total_applicable == len(
        report.findings
    )


# --- Art. 2: nothing is owed, and the report has to say which kind of nothing ---------------------
def test_an_out_of_scope_system_is_never_checked(spec):
    """Art. 2 withholds the Regulation entirely, so there is no obligation to check against. The
    judge must not be called at all — running it would produce findings for duties that do not
    exist."""
    judge = StubJudge()
    report = review(
        DOCUMENT,
        spec,
        a_brain(prohibited=None, scope=ScopeExclusion.MILITARY_DEFENCE_NATIONAL_SECURITY),
        judge=judge,
        system_id="defence",
    )
    assert report.classification.overall_risk_class == RiskClass.OUT_OF_SCOPE
    assert not report.findings
    assert judge.calls == []


def test_the_out_of_scope_note_distinguishes_itself_from_minimal(spec):
    """An empty findings list is the same output a clean bill of health produces, so the note is
    the only thing telling the two apart — and `minimal` is the neighbour it will be confused with.
    A minimal system is INSIDE the Regulation and still owes Art. 4; this one owes nothing."""
    report = review(
        DOCUMENT,
        spec,
        a_brain(prohibited=None, scope=ScopeExclusion.SCIENTIFIC_RESEARCH),
        judge=StubJudge(),
        system_id="research",
    )
    note = report.scope_note or ""
    assert "Art. 2" in note
    assert "minimal" in note, "the note must name the tier it is not"
    assert "Art. 4" in note, "and what a minimal system would still owe"


def test_a_gpai_model_is_not_checked_but_is_not_cleared_either(spec):
    """The distinction that matters. `out_of_scope` owes nothing; a general-purpose AI model owes
    plenty — just under Chapter V, which this ruleset does not carry. An empty findings list with
    no note would read as a clean bill of health for a provider who owes Art. 53 today."""
    brain = a_brain(
        territorial=TerritorialLink.NOT_ADDRESSED,
        scope=None,
        gpai_model=GpaiStatus.GENERAL_PURPOSE_MODEL,
    )
    report = review(DOCUMENT, spec, brain, judge=StubJudge(), system_id="model")

    assert report.classification.overall_risk_class == RiskClass.GPAI_MODEL
    assert report.findings == []
    assert report.not_document_verifiable == {}
    assert report.scope_note and "NOT ASSESSED, not compliant" in report.scope_note
    # The handover travels with it, so the reader is told what DOES govern.
    assert "Art. 53" in report.scope_note and "Chapter V" in report.scope_note


# --- Art. 5's two dates ---------------------------------------------------------------------
def test_a_prohibition_not_yet_in_force_reports_its_date(spec):
    """Art. 5(1)(ba) and (bb) were inserted by Reg (EU) 2026/1744 and apply only from 2 December
    2026 — the first time Art. 5 has had more than one date. Telling an organisation to withdraw a
    practice the Article does not yet reach would be wrong; saying nothing about the date would be
    wrong the other way, because it does become unlawful and no documentation changes that."""
    brain = a_brain(prohibited=ProhibitedPractice.NON_CONSENSUAL_INTIMATE_IMAGERY)
    report = review(DOCUMENT, spec, brain, judge=StubJudge())

    assert report.classification.overall_risk_class == RiskClass.PROHIBITED
    assert report.findings == [], "Chapter III is never checked against a prohibited practice"
    note = report.scope_note or ""
    assert "2026-12-02" in note
    assert "Art. 5(1)(ba)" in note
    assert "withdrawal deadline" in note


def test_a_prohibition_already_in_force_says_withdraw(spec):
    """The contrast that gives the test above its meaning: for a point that already applies, the
    answer is still the plain one."""
    brain = a_brain(prohibited=ProhibitedPractice.SOCIAL_SCORING)
    report = review(DOCUMENT, spec, brain, judge=StubJudge())

    note = report.scope_note or ""
    assert "Withdraw the practice." in note
    assert "2026-12-02" not in note


def test_the_report_can_name_which_point_banned_the_practice(spec):
    """The tier alone no longer settles whether a practice is banned today, so the point has to
    reach the report rather than only the reasoning string."""
    brain = a_brain(prohibited=ProhibitedPractice.CHILD_SEXUAL_ABUSE_MATERIAL)
    report = review(DOCUMENT, spec, brain, judge=StubJudge())
    practice = report.classification.prohibited_practice

    assert practice is ProhibitedPractice.CHILD_SEXUAL_ABUSE_MATERIAL
    assert practice.point == "bb"
