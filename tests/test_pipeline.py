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
from aiact.schemas.enums import AnnexIIIArea, RiskClass, ScopeExclusion, Verdict

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
    return a_brain(prohibited=False, annex_iii=AnnexIIIArea.EMPLOYMENT, profiling=True)


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
    report = review(DOCUMENT, spec, a_brain(prohibited=True), judge=judge, system_id="sys-1")

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
        a_brain(prohibited=True),
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
        prohibited=False,
        annex_iii=AnnexIIIArea.EMPLOYMENT,
        profiling=False,
        derogation="narrow_procedural_task",
    )
    judge = StubJudge()
    report = review(DOCUMENT, spec, brain, judge=judge, system_id="sys-1")

    assert report.classification.overall_risk_class == RiskClass.NOT_HIGH_RISK
    checked = set(judge.calls) | set(report.not_document_verifiable)
    assert "AIA-NHR-A06-4" in checked, "Art. 6(4) must survive a not_high_risk classification"


def test_a_minimal_system_owes_nothing_and_that_is_not_an_error(spec):
    """No rule attaches to `minimal`, so an empty report here is the correct answer rather than a
    skipped check — the obligation layer ran and found nothing owed."""
    report = review(DOCUMENT, spec, a_brain(prohibited=False, annex_iii=None), judge=StubJudge())
    assert report.classification.overall_risk_class == RiskClass.MINIMAL
    assert report.summary.total_applicable == 0


# --- Art. 2: nothing is owed, and the report has to say which kind of nothing ---------------------
def test_an_out_of_scope_system_is_never_checked(spec):
    """Art. 2 withholds the Regulation entirely, so there is no obligation to check against. The
    judge must not be called at all — running it would produce findings for duties that do not
    exist."""
    judge = StubJudge()
    report = review(
        DOCUMENT,
        spec,
        a_brain(prohibited=False, scope=ScopeExclusion.MILITARY_DEFENCE_NATIONAL_SECURITY),
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
        a_brain(prohibited=False, scope=ScopeExclusion.SCIENTIFIC_RESEARCH),
        judge=StubJudge(),
        system_id="research",
    )
    note = report.scope_note or ""
    assert "Art. 2" in note
    assert "minimal" in note, "the note must name the tier it is not"
    assert "Art. 4" in note, "and what a minimal system would still owe"
