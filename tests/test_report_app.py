"""The review endpoint, with the classification brain and the judge stubbed."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from aiact.classify.scripted_brain import ScriptedBrain
from aiact.gap.judge import Judgement
from aiact.report_app.app import app, get_brain, get_judge, get_summariser
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


def test_page_files_are_revalidated_so_an_edit_shows_on_reload(client_for):
    response = client_for(**high_risk()).get("/static/report.js")
    assert response.headers["cache-control"] == "no-cache"


def test_the_page_is_told_the_document_limit(client_for, monkeypatch):
    monkeypatch.setenv("AIACT_MAX_DOCUMENT_CHARS", "1234")
    response = client_for(**high_risk()).get("/api/limits")
    assert response.json() == {"max_document_chars": 1234}
