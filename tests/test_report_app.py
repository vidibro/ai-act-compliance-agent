"""The review endpoint, with the classification brain and the judge stubbed."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from aiact.classify.scripted_brain import ScriptedBrain
from aiact.gap.judge import Judgement
from aiact.policy_loader import load_policy_spec
from aiact.report_app.app import app, get_brain, get_judge, get_summariser
from aiact.report_app.views import resolve_rules
from aiact.schemas.enums import AnnexIIIArea, ProhibitedPractice, Verdict
from aiact.summary import SystemSummary

DOCUMENT = "# System card\n\n## Human oversight\n\nA panel reviews every recommendation.\n"


class GapJudge:
    name = "stub"

    def judge(self, rule, document):  # noqa: ANN001 - mirrors LLMJudge.judge
        return Judgement(
            verdict=Verdict.GAP,
            reasoning="stub",
            evidence_quote=None,
            evidence_chunk_id=None,
            confidence="high",
        )


class StubSummariser:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def summarise(self, document: str) -> SystemSummary | None:
        self.calls += 1
        if self.fail:
            raise RuntimeError("model unavailable")
        return SystemSummary(name="TalentRank", summary="Scores job applicants for recruiters.")


@pytest.fixture
def summariser() -> StubSummariser:
    return StubSummariser()


@pytest.fixture
def client_for(summariser) -> Iterator:
    def make(**answers: object) -> TestClient:
        app.dependency_overrides[get_brain] = lambda: ScriptedBrain({"is_ai": True, **answers})
        app.dependency_overrides[get_judge] = lambda: GapJudge()
        app.dependency_overrides[get_summariser] = lambda: summariser
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


def high_risk() -> dict[str, object]:
    return {"prohibited": None, "annex_iii": AnnexIIIArea.EMPLOYMENT, "profiling": True}


def test_a_review_returns_the_report_with_every_named_rule_resolved(client_for):
    response = client_for(**high_risk()).post(
        "/api/review", json={"document": DOCUMENT, "system_id": "scorer"}
    )

    assert response.status_code == 200
    body = response.json()
    report = body["report"]
    assert report["classification"]["overall_risk_class"] == "high_risk"
    assert report["findings"]
    named = {f["rule_id"] for f in report["findings"]} | {
        rule_id for ids in report["not_document_verifiable"].values() for rule_id in ids
    }
    assert named <= set(body["rules"])
    assert body["report"]["disclaimer"]


def test_every_judged_criterion_has_a_readable_title(client_for):
    body = client_for(**high_risk()).post("/api/review", json={"document": DOCUMENT}).json()

    findings = body["report"]["findings"]
    criteria = [(f["rule_id"], c["norm_id"]) for f in findings for c in f["criteria"]]
    assert criteria
    for rule_id, norm_id in criteria:
        title = body["rules"][rule_id]["criteria"][norm_id]
        assert title["citation"].startswith(("Art.", "Annex"))
        assert title["action"][0].isupper()


def test_rule_texts_name_other_rules_by_citation_not_by_id():
    spec = load_policy_spec()
    views = resolve_rules([rule.rule_id for rule in spec.rules], [], spec)

    texts = [
        text
        for view in views.values()
        for text in (view.evidence_expected, view.activation_condition, view.effective_date_note)
        if text
    ]
    assert not [text for text in texts if "AIA-RULE-" in text or "[non-binding guidance:" in text]


def test_future_duties_carry_their_date(client_for):
    """Art. 9 applies to an Annex III system from 2 December 2027."""
    body = client_for(**high_risk()).post("/api/review", json={"document": DOCUMENT}).json()

    [finding] = [f for f in body["report"]["findings"] if f["rule_id"] == "AIA-RULE-HR-A09"]
    assert finding["applies_from"] == "2027-12-02"
    assert body["rules"]["AIA-RULE-HR-A09"]["application_dates"] == {"system": "2027-12-02"}
    assert "2027-12-02" in body["report"]["summary"]["upcoming"]


def test_process_duties_get_their_date_from_the_rule(client_for):
    """Art. 17 is never judged, so its date has to come with the rule."""
    body = client_for(**high_risk()).post("/api/review", json={"document": DOCUMENT}).json()

    assert body["rules"]["AIA-RULE-PO-A17"]["application_dates"] == {"system": "2027-12-02"}
    assert body["rules"]["AIA-RULE-PO-A17"]["document_verifiable"] is False


def test_the_notes_are_sent_as_fields(client_for):
    """They are properties on the report, which serialisation drops."""
    body = client_for(**high_risk()).post("/api/review", json={"document": DOCUMENT}).json()

    assert body["notes"]["legacy_system"] and "Art. 111(2)" in body["notes"]["legacy_system"]


def test_a_prohibited_practice_comes_back_with_its_note_and_no_findings(client_for):
    client = client_for(prohibited=ProhibitedPractice.SOCIAL_SCORING)
    body = client.post("/api/review", json={"document": DOCUMENT}).json()

    assert body["report"]["classification"]["overall_risk_class"] == "prohibited"
    assert body["report"]["findings"] == []
    assert body["report"]["scope_note"]


def test_an_empty_document_is_rejected(client_for):
    response = client_for(**high_risk()).post("/api/review", json={"document": ""})
    assert response.status_code == 422


def test_a_document_over_the_limit_is_rejected_before_any_model_call(
    client_for, summariser, monkeypatch
):
    monkeypatch.setenv("AIACT_MAX_DOCUMENT_CHARS", "10")
    response = client_for(**high_risk()).post("/api/review", json={"document": DOCUMENT})

    assert response.status_code == 413
    assert "limit" in response.json()["detail"]
    assert summariser.calls == 0


def test_the_review_comes_with_the_system_name_and_a_summary(client_for):
    body = client_for(**high_risk()).post("/api/review", json={"document": DOCUMENT}).json()
    assert body["system_name"] == "TalentRank"
    assert body["system_summary"] == "Scores job applicants for recruiters."


def test_a_failed_summary_does_not_fail_the_review(client_for, summariser):
    summariser.fail = True
    response = client_for(**high_risk()).post("/api/review", json={"document": DOCUMENT})

    assert response.status_code == 200
    assert response.json()["system_summary"] is None
    assert response.json()["system_name"] is None
    assert response.json()["report"]["findings"]


def test_the_page_and_its_files_are_served(client_for):
    client = client_for(**high_risk())

    page = client.get("/")
    assert page.status_code == 200
    assert "/static/report.js" in page.text
    assert client.get("/static/report.js").status_code == 200
    assert client.get("/static/report.css").status_code == 200


def test_the_system_card_guide_is_served_as_a_page(client_for):
    client = client_for(**high_risk())

    assert 'href="/guide"' in client.get("/").text
    guide = client.get("/guide")
    assert guide.status_code == 200
    assert "<h1>How to write a system card" in guide.text
    assert "<table>" in guide.text  # the role and Art. 9–15 tables render as tables
    assert client.get("/static/guide.js").status_code == 200

    markdown = client.get("/guide.md")
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert markdown.text.startswith("# How to write a system card")


def test_page_files_are_revalidated_so_an_edit_shows_on_reload(client_for):
    response = client_for(**high_risk()).get("/static/report.js")
    assert response.headers["cache-control"] == "no-cache"


def test_the_page_is_told_the_document_limit(client_for, monkeypatch):
    monkeypatch.setenv("AIACT_MAX_DOCUMENT_CHARS", "1234")
    response = client_for(**high_risk()).get("/api/limits")
    assert response.json() == {"max_document_chars": 1234}


def test_a_saved_report_is_refreshed_without_calling_a_model(client_for):
    """The page sends back what a stored report names; rule details come from the current spec."""
    client = client_for(**high_risk())
    body = client.post("/api/review", json={"document": DOCUMENT}).json()
    app.dependency_overrides[get_brain] = lambda: pytest.fail("no model call on refresh")

    refreshed = client.post(
        "/api/refresh",
        json={
            "use_cases": body["report"]["classification"]["use_cases"],
            "rule_ids": list(body["rules"]),
            "norm_ids": list(body["norms"]),
        },
    ).json()

    assert refreshed["rules"] == body["rules"]
    assert refreshed["norms"] == body["norms"]
    assert refreshed["rules"]["AIA-RULE-HR-A09"]["action"]
