"""Demo mode: the review with no model behind it, and how the page is told which mode it is in.

Nothing here calls a model. The demo stand-ins are pinned on the sample documents the page offers,
so the demo's story — a compliant file passes, a bare card shows its gaps, a vendor page describing
emotion inference is prohibited — cannot drift without a test noticing.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from aiact.classify.scripted_brain import ScriptedBrain
from aiact.policy_loader import load_policy_spec
from aiact.report_app.app import app, get_brain, get_judge, get_summariser
from aiact.report_app.demo import (
    DEMO_PREFIX,
    DemoBrain,
    DemoJudge,
    DemoSummariser,
    Reader,
)
from aiact.report_app.samples import list_samples, load_sample
from aiact.schemas.enums import AnnexIIIArea, Verdict
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Question

HIGH_RISK_RULES = [
    "AIA-RULE-HR-A09",
    "AIA-RULE-HR-A10",
    "AIA-RULE-HR-A11",
    "AIA-RULE-HR-A12",
    "AIA-RULE-HR-A13",
    "AIA-RULE-HR-A13-3",
    "AIA-RULE-HR-A14",
    "AIA-RULE-HR-A15",
]


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def no_model(monkeypatch) -> None:
    monkeypatch.setenv("AIACT_LLM_MODEL", "")


@pytest.fixture
def no_model_calls(monkeypatch) -> None:
    """Any completion call fails the test: the demo must never reach a model."""
    import litellm

    def fail(*args, **kwargs):  # noqa: ANN001
        pytest.fail("demo mode called a model")

    monkeypatch.setattr(litellm, "completion", fail)
    app.dependency_overrides[get_brain] = lambda: pytest.fail("demo mode built the live brain")
    app.dependency_overrides[get_summariser] = lambda: pytest.fail("demo mode built the summariser")


def sample(sample_id: str) -> str:
    found = load_sample(sample_id)
    assert found is not None, sample_id
    return found.text


def verdicts(body: dict) -> dict[str, str]:
    return {f["rule_id"]: f["verdict"] for f in body["report"]["findings"]}


# ---- which mode --------------------------------------------------------------------------------


def test_the_page_is_told_when_no_model_is_configured(client, no_model):
    info = client.get("/api/mode").json()
    assert info["live_available"] is False
    assert "AIACT_LLM_MODEL is empty" in info["live_unavailable_because"]
    assert info["llm_model"] is None
    assert info["demo_mode"] == "available"
    assert "DEMO" in info["demo_note"]


def test_a_model_without_its_key_cannot_run_live_and_the_page_is_told_so(client, monkeypatch):
    monkeypatch.setenv("AIACT_LLM_MODEL", "anthropic/claude-haiku-4-5")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    info = client.get("/api/mode").json()
    assert info["live_available"] is False
    reason = info["live_unavailable_because"]
    assert "No provider key is set" in reason and "anthropic/claude-haiku-4-5" in reason
    # Provider-agnostic: the page never tells a reader which vendor's variable to set.
    assert "ANTHROPIC" not in reason and "API_KEY" not in reason

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    info = client.get("/api/mode").json()
    assert info == {**info, "live_available": True, "live_unavailable_because": None}
    assert info["llm_model"] == "anthropic/claude-haiku-4-5"


def test_a_proxy_or_an_unknown_vendor_is_given_the_benefit_of_the_doubt(client, monkeypatch):
    """A proxy holds its own key; a vendor this page does not know may take credentials from
    anywhere. Locking either into demo mode would be the worse mistake."""
    monkeypatch.setenv("AIACT_LLM_MODEL", "litellm_proxy/gemini-2.5-flash")
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://proxy.example")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.get("/api/mode").json()["live_available"] is True

    monkeypatch.delenv("LITELLM_PROXY_URL")
    monkeypatch.setenv("AIACT_LLM_MODEL", "bedrock/some-model")
    assert client.get("/api/mode").json()["live_available"] is True


def test_demo_only_switches_live_reviews_off(client, monkeypatch):
    monkeypatch.setenv("AIACT_LLM_MODEL", "anthropic/claude-haiku-4-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("AIACT_DEMO_MODE", "only")
    info = client.get("/api/mode").json()
    assert info["demo_mode"] == "only" and info["live_available"] is False
    assert "AIACT_DEMO_MODE=only" in info["live_unavailable_because"]
    response = client.post("/api/review", json={"document": sample("guide-system-card")})
    assert response.status_code == 503
    assert "AIACT_DEMO_MODE=only" in response.json()["detail"]
    assert (
        client.post(
            "/api/demo/review", json={"document": sample("sentinel-m-military")}
        ).status_code
        == 200
    )


def test_demo_off_switches_the_demo_off(client, no_model, monkeypatch):
    monkeypatch.setenv("AIACT_DEMO_MODE", "off")
    info = client.get("/api/mode").json()
    assert info["demo_mode"] == "off"
    response = client.post("/api/demo/review", json={"document": sample("sentinel-m-military")})
    assert response.status_code == 403
    assert "AIACT_DEMO_MODE=off" in response.json()["detail"]
    # And with no model either, the live refusal says to set one rather than to use the demo.
    refused = client.post("/api/review", json={"document": sample("guide-system-card")})
    assert refused.status_code == 503
    assert "demo" not in refused.json()["detail"].lower()


def test_without_a_model_a_normal_review_is_refused_before_any_call(client, no_model):
    response = client.post("/api/review", json={"document": sample("guide-system-card")})
    assert response.status_code == 503
    assert "AIACT_LLM_MODEL" in response.json()["detail"]
    assert "demo mode" in response.json()["detail"]


def test_a_normal_review_that_cannot_reach_the_model_says_so(client):
    class Broken:
        name = "broken"

        def decide(self, question, description):  # noqa: ANN001
            raise RuntimeError("Missing Anthropic API Key")

    app.dependency_overrides[get_brain] = lambda: Broken()
    app.dependency_overrides[get_judge] = lambda: DemoJudge()  # the brain fails first either way
    app.dependency_overrides[get_summariser] = lambda: DemoSummariser()
    response = client.post("/api/review", json={"document": sample("guide-system-card")})
    assert response.status_code == 502
    assert "Missing Anthropic API Key" in response.json()["detail"]


def test_normal_mode_still_works_and_is_not_marked_as_a_demo(client):
    app.dependency_overrides[get_brain] = lambda: ScriptedBrain(
        {"is_ai": True, "prohibited": None, "annex_iii": AnnexIIIArea.EMPLOYMENT, "profiling": True}
    )
    app.dependency_overrides[get_judge] = lambda: DemoJudge()  # any judge; the mode is the point
    app.dependency_overrides[get_summariser] = lambda: DemoSummariser()
    body = client.post("/api/review", json={"document": sample("guide-system-card")}).json()
    assert body["demo"] is False
    assert body["demo_note"] is None
    assert body["report"]["classification"]["overall_risk_class"] == "high_risk"


# ---- the demo review ---------------------------------------------------------------------------


def test_a_demo_review_runs_without_a_model_and_says_it_is_one(client, no_model, no_model_calls):
    response = client.post("/api/demo/review", json={"document": sample("hr-candidate-scoring")})

    assert response.status_code == 200
    body = response.json()
    assert body["demo"] is True
    assert "DEMO" in body["demo_note"]
    assert body["system_name"] == "TalentRank Candidate Scoring"
    assert body["system_summary"].startswith("TalentRank produces a ranked fit score")
    # Every verdict and every classification answer wears the demo mark, so one copied out of the
    # response cannot pass for a model's.
    report = body["report"]
    assert report["findings"]
    for finding in report["findings"]:
        # A rule judged part by part carries the pipeline's own tally; its parts carry the mark.
        marked = [finding["reasoning"], *(c["reasoning"] for c in finding["criteria"])]
        assert marked[0].startswith(DEMO_PREFIX) or all(
            m.startswith(DEMO_PREFIX) for m in marked[1:]
        ), finding
    assert all(a["reasoning"].startswith(DEMO_PREFIX) for a in report["classification"]["answers"])
    # The report is the real pipeline's: rules and norms are resolved as for a live review.
    named = {f["rule_id"] for f in report["findings"]}
    assert named <= set(body["rules"])
    assert body["norms"]


def test_a_demo_review_is_still_bounded_by_the_document_limit(client, monkeypatch):
    monkeypatch.setenv("AIACT_MAX_DOCUMENT_CHARS", "10")
    response = client.post("/api/demo/review", json={"document": sample("guide-system-card")})
    assert response.status_code == 413


def test_the_compliant_reference_file_passes_every_checked_duty(client, no_model_calls):
    body = client.post("/api/demo/review", json={"document": sample("hr-candidate-scoring")}).json()

    assert body["report"]["classification"]["overall_risk_class"] == "high_risk"
    found = verdicts(body)
    assert {found[rule_id] for rule_id in HIGH_RISK_RULES} == {"pass"}
    assert found["AIA-RULE-PO-A16-B"] == "pass"
    # A passing duty cites the document, and the quote is really in it.
    [finding] = [f for f in body["report"]["findings"] if f["rule_id"] == "AIA-RULE-HR-A09"]
    assert finding["evidence_quote"]
    assert finding["evidence_quote"].split(" ")[0] in sample("hr-candidate-scoring")


def test_the_guide_s_card_classifies_and_shows_the_high_risk_duties_as_gaps(client, no_model_calls):
    """The guide says so itself: the card is enough to classify and lists the Arts. 9-15 duties as
    gaps. Art. 16(b) is the one point a card can meet, and this one does."""
    body = client.post("/api/demo/review", json={"document": sample("guide-system-card")}).json()

    assert body["report"]["classification"]["overall_risk_class"] == "high_risk"
    assert body["system_name"] == "Smart Screening"
    found = verdicts(body)
    assert {found[rule_id] for rule_id in HIGH_RISK_RULES} == {"gap"}
    assert found["AIA-RULE-PO-A16-B"] == "pass"
    # The card's stated facts reach the role questions too: private-sector deployers, no live
    # trials before release.
    assert body["notes"]["deployer_type"]
    assert "private" in body["notes"]["deployer_type"].lower()


def test_a_vendor_page_describing_emotion_inference_in_hiring_is_prohibited(client, no_model_calls):
    body = client.post(
        "/api/demo/review", json={"document": sample("vendor-video-interview-analysis")}
    ).json()

    assert body["report"]["classification"]["overall_risk_class"] == "prohibited"
    assert body["report"]["findings"] == []
    assert body["report"]["scope_note"]
    [evidence] = [
        e for e in body["report"]["classification"]["triggered_by"] if e["source"]["article"] == "5"
    ]
    assert evidence["evidence_quote"]  # the sentence it rests on, quoted


def test_a_scheduling_tool_that_evaluates_nobody_is_not_high_risk(client, no_model_calls):
    body = client.post(
        "/api/demo/review", json={"document": sample("vendor-interview-coordination")}
    ).json()

    assert body["report"]["classification"]["overall_risk_class"] == "not_high_risk"
    assert verdicts(body) == {"AIA-RULE-NHR-A06-4": "gap"}


def test_a_saved_demo_report_refreshes_like_any_other(client, no_model_calls):
    body = client.post("/api/demo/review", json={"document": sample("guide-system-card")}).json()
    refreshed = client.post(
        "/api/refresh",
        json={
            "use_cases": body["report"]["classification"]["use_cases"],
            "rule_ids": list(body["rules"]),
            "norm_ids": list(body["norms"]),
        },
    ).json()
    assert refreshed["rules"] == body["rules"]


# ---- the stand-ins -----------------------------------------------------------------------------


def question(node_id: str) -> Question:
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689", article=6, act_version_date=date(2026, 7, 27)
    )
    return Question(node_id, source, "?", "")


def test_the_demo_brain_reads_a_negation():
    brain = DemoBrain()
    scores = "Each applicant receives a 0-100 fit score against the role."
    extracts = "It extracts fields and does not score, rank or evaluate the applicant."

    assert brain.decide(question("profiling"), scores).value is True
    assert brain.decide(question("profiling"), extracts).value is False
    answer = brain.decide(question("profiling"), scores)
    assert answer.reasoning.startswith(DEMO_PREFIX)
    assert answer.confidence == "medium"
    assert answer.evidence_quote == scores


def test_the_demo_brain_abstains_on_a_question_it_has_no_heuristic_for():
    answer = DemoBrain().decide(question("something_new"), "anything")
    assert answer.confidence == "low"
    assert answer.abstained_because == "reply_unusable"


def test_the_demo_judge_tells_a_missing_section_from_a_thin_one():
    spec = load_policy_spec()
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-HR-A14")
    judge = DemoJudge()

    missing = judge.judge(rule, "# System\n\n## Data\n\nWe train on 400,000 applications.\n")
    thin = judge.judge(rule, "# System\n\n## Human oversight\n\nOur oversight is appropriate.\n")

    assert missing.verdict is Verdict.GAP
    assert all(c.verdict is Verdict.GAP for c in missing.criteria)
    assert thin.verdict is Verdict.INADEQUATE
    assert all(c.verdict is Verdict.INADEQUATE for c in thin.criteria)
    assert thin.evidence_quote == "Our oversight is appropriate."
    assert thin.reasoning.startswith(DEMO_PREFIX)


def test_the_demo_summariser_quotes_the_document():
    text = (
        "# Acme Scorer — Technical Documentation\n\n"
        "**Provider:** Acme B.V.\n"
        "**Intended purpose:** Acme Scorer ranks loan applications for a bank's credit officers. "
        "It is used in the Netherlands.\n\n## 1. General description\n"
    )
    summary = DemoSummariser().summarise(text)
    assert summary is not None
    assert summary.name == "Acme Scorer"
    assert summary.summary.startswith("Acme Scorer ranks loan applications")
    assert DemoSummariser().summarise("") is None


def test_the_reader_splits_sections_and_keeps_each_paragraph_once():
    text = "# Title\n\nIntro.\n\n## A\n\nFirst paragraph here.\n\n### A.1\n\nDeeper text.\n"
    reader = Reader(text)
    by_heading = {s.heading: s for s in reader.sections}
    assert "Deeper text." in by_heading["A"].body  # a parent says what its children say
    assert by_heading["A"].paragraphs == ["First paragraph here."]  # but owns only its own
    assert reader.affirms(r"paragraph") == "First paragraph here."
    assert reader.denies(r"paragraph") is None


# ---- the samples -------------------------------------------------------------------------------


@pytest.mark.parametrize("registered", list_samples(), ids=lambda s: s.id)
def test_every_case_in_the_gallery_reaches_the_outcome_on_its_card(
    client, no_model_calls, registered
):
    """The gallery card says which risk class the demo reaches; the demo must reach it."""
    body = client.post("/api/demo/review", json={"document": sample(registered.id)}).json()
    assert body["report"]["classification"]["overall_risk_class"] == registered.outcome


def test_the_new_cases_show_what_the_golden_set_cannot(client, no_model_calls):
    """Annex I, Art. 50, Chapter V, Art. 2 and an abstention — each with the duties it brings."""
    medical = client.post(
        "/api/demo/review", json={"document": sample("sepsis-watch-medical-device")}
    ).json()
    found = verdicts(medical)
    assert "AIA-RULE-HR-A11-2" in found  # the Annex I duty: one technical file for both regimes
    assert {found[r] for r in HIGH_RISK_RULES} >= {"pass", "gap", "inadequate"}  # mixed

    chatbot = client.post(
        "/api/demo/review", json={"document": sample("shopassist-retail-chatbot")}
    ).json()
    assert verdicts(chatbot) == {"AIA-RULE-TR-A50-1": "pass", "AIA-RULE-TR-A50-2": "inadequate"}

    model = client.post(
        "/api/demo/review", json={"document": sample("aurora-7b-model-card")}
    ).json()
    assert model["report"]["findings"] == []
    assert "gpai_provider" in model["report"]["not_document_verifiable"]
    assert model["notes"]["chapter_v_gate"]

    lift = client.post(
        "/api/demo/review", json={"document": sample("liftguard-assessor-not-stated")}
    ).json()
    assert "conformity is assessed" in lift["report"]["classification"]["reasoning"]
    assert lift["report"]["findings"] == []

    military = client.post(
        "/api/demo/review", json={"document": sample("sentinel-m-military")}
    ).json()
    assert military["report"]["not_document_verifiable"] == {}
    assert "Art. 2" in military["report"]["scope_note"]


def test_the_samples_are_the_repository_s_own_documents(client):
    listed = client.get("/api/samples").json()
    by_id = {s["id"]: s for s in listed}

    assert {"guide-system-card", "hr-candidate-scoring", "internal-mobility"} <= set(by_id)
    assert by_id["hr-candidate-scoring"]["kind"] == "reference"
    assert by_id["guide-system-card"]["kind"] == "system_card"
    assert by_id["vendor-screening-and-ranking"]["kind"] == "vendor_page"
    assert by_id["aurora-7b-model-card"]["kind"] == "model_card"
    # Every card carries its outcome and a label, and the outcomes cover the report's range.
    assert all(s["outcome"] and s["label"] and s["about"] for s in listed)
    assert {s["outcome"] for s in listed} == {
        "high_risk",
        "needs_review",
        "not_high_risk",
        "minimal",
        "gpai_model",
        "prohibited",
        "out_of_scope",
    }
    source = by_id["hr-candidate-scoring"]["source"]
    assert source == "data/golden_set/reference/hr-candidate-scoring.md"
    assert [s.id for s in list_samples()] == [s["id"] for s in listed]


def test_a_reference_sample_is_served_without_its_authoring_comments(client):
    doc = client.get("/api/samples/hr-candidate-scoring").json()
    assert doc["title"] == "TalentRank Candidate Scoring — Technical Documentation"
    assert doc["text"].startswith("# TalentRank Candidate Scoring")
    assert "<!--" not in doc["text"]
    assert "rule: AIA-RULE" not in doc["text"]


def test_the_guide_s_worked_example_is_served_as_a_document_of_its_own(client):
    doc = client.get("/api/samples/guide-system-card").json()
    assert doc["text"].startswith("# Smart Screening — system card\n")
    assert "\n## Parties\n" in doc["text"]
    assert "\n## Use case 2: candidate fit scoring and ranking\n" in doc["text"]
    assert client.get("/api/samples/nope").status_code == 404


# ---- the page ----------------------------------------------------------------------------------


def test_the_page_carries_the_mode_switch_and_the_demo_banner(client):
    page = client.get("/").text
    assert 'id="demo-switch"' in page and 'role="switch"' in page
    assert 'id="modebar"' in page
    # The samples are demo mode's cases and nothing else: normal mode offers no stock document,
    # which would read as a template of a complete system card (the guide is the way to write one).
    assert 'id="sample"' not in page
    # Demo mode has no free text input: the cases are the input, and the reviewed document is
    # shown read-only on request.
    styles = client.get("/static/report.css").text
    assert 'html[data-demo="1"] #form[data-mode="edit"] textarea' in styles
    assert 'id="show-doc"' in page
    script = client.get("/static/report.js").text
    assert "const memory = new Map(); // the demo workspace" in script  # never local storage
    assert 'demo_mode !== "off"' in script
    script = client.get("/static/report.js").text
    assert "/api/demo/review" in script and "/api/review" in script
    assert "/api/mode" in script and "/api/samples" in script
    styles = client.get("/static/report.css").text
    assert 'html[data-demo="1"]' in styles


def test_demo_mode_offers_a_case_gallery(client):
    """One card per sample, marked with its outcome; a click pastes, a second button runs."""
    page = client.get("/").text
    assert 'id="cases"' in page and 'id="cases-grid"' in page
    gallery = page.split('id="cases"')[0][-80:]
    assert "<details" in gallery and "demo-only" in gallery
    assert "<summary>" in page.split('id="cases"')[1][:40]
    script = client.get("/static/report.js").text
    assert "function buildGallery(list)" in script
    assert "pickSample(s.id)" in script  # one click runs the case
    assert "requestSubmit()" in script
    assert '$("cases").open = mode === "edit";' in script  # open while choosing, folded after


def test_demo_mode_keeps_a_label_fixed_to_the_window(client):
    """The bar and banner scroll away with the top of the page; this label does not."""
    page = client.get("/").text
    assert 'id="demo-float"' in page and "demo-only" in page.split('id="demo-float"')[0][-80:]
    assert 'id="demo-float-off"' in page
    # In the row fixed to the window, beside the report's Print and Download while reading.
    floatbar = page.split('<div class="floatbar" id="floatbar">')[1].split("\n</div>")[0]
    assert 'id="demo-float"' in floatbar
    styles = client.get("/static/report.css").text
    rule = styles.split(".floatbar {", 1)[1].split("}", 1)[0]
    assert "position: fixed" in rule
    # One line: the mode and a way out, no subline; on a phone, "Demo" and a ✕ that keeps its name.
    label = floatbar.split('id="demo-float"')[1].split("</aside>")[0]
    assert "Illustrative" not in label and 'id="demo-float-sub"' not in label
    assert 'aria-label="Turn off demo mode"' in label
    script = client.get("/static/report.js").text
    assert '$("demo-float-off").addEventListener("click"' in script
    assert "demo-float-sub" not in script


def test_each_mode_keeps_its_own_document_and_report(client):
    """A demo document must never be shown beside the live "Run review" button: the page stores
    the two modes' drafts and reports under separate keys and swaps them on a mode change."""
    script = client.get("/static/report.js").text
    assert '"aiact-review:demo:last"' in script and '"aiact-review:demo:draft"' in script
    assert "function loadWorkspace()" in script
    assert "if (changed) loadWorkspace();" in script
    # Outside the one-off migration of older saves, nothing writes to a fixed key: every save goes
    # through the current mode's key.
    migration = script.split("function migrateSaved()", 1)[1].split("\n}\n", 1)[0]
    elsewhere = script.replace(migration, "")
    assert "store(STORE." not in elsewhere and "store(DEMO_STORE." not in elsewhere
    assert "store(keyFor(" in elsewhere
