from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aiact.ui.app import app


def test_coverage_map_serves_page_and_consistent_payload() -> None:
    with TestClient(app) as client:
        assert "AI Act Coverage" in client.get("/").text
        for asset in ("core.js", "map.js", "norms.js", "rules.js", "ui.css"):
            assert client.get(f"/static/{asset}").status_code == 200
        data = client.get("/api/coverage").json()

    doc_keys = {doc["key"] for doc in data["documents"]}
    assert {norm["doc"] for norm in data["norms"]} <= doc_keys
    assert {rule["doc"] for rule in data["rules"]} <= doc_keys
    assert all(doc["title"] for doc in data["documents"])
    assert any(rule["cases_dev"] for rule in data["rules"])
    for guidance in data["guidance"]:
        decided = sum(guidance.get(k, 0) for k in ("used", "not_followed", "no_effect"))
        assert decided + guidance["awaiting"] == guidance["paragraphs"]


def test_norm_cards_resolve_every_reference() -> None:
    with TestClient(app) as client:
        cards = client.get("/api/norms").json()

    norms, segments = cards["norms"], cards["segments"]
    for norm in norms.values():
        assert set(norm["primary_spans"]) <= set(segments)
        regime = norm["temporal_regime_id"]
        assert regime is None or regime in cards["regimes"]
    for relation in cards["relations"]:
        assert relation["source_norm_id"] in norms
        assert set(relation["target_norm_ids"]) <= set(norms)
    for link in cards["interpretations"]:
        assert set(link["snippet_refs"]) <= set(cards["snippets"])
    for rule in cards["rules"].values():
        assert set(rule["criteria"]) <= set(norms)
    question_ids = {question["id"] for question in cards["questions"]}
    implemented = {ref for norm in norms.values() for ref in norm["implementation_refs"]}
    assert {ref for ref in implemented if ref.startswith("AIA-CQ-")} <= question_ids



def test_version_changes_with_the_data_and_a_bad_edit_keeps_the_last_good_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aiact.ui import app as ui_app

    with TestClient(app) as client:
        first = client.get("/api/version").json()
        assert first["error"] is None
        good = client.get("/api/coverage").json()

        def broken() -> None:
            raise ValueError("bad yaml")

        monkeypatch.setattr(ui_app, "_fingerprint", lambda *args: "edited")
        monkeypatch.setattr(ui_app, "load_normative_coverage", broken)
        after = client.get("/api/version").json()
        assert after["data"] == "edited"
        assert after["error"] == "ValueError: bad yaml"
        assert client.get("/api/coverage").json() == good
