from __future__ import annotations

from fastapi.testclient import TestClient

from aiact.ui.app import app


def test_coverage_map_serves_page_and_consistent_payload() -> None:
    with TestClient(app) as client:
        assert "AI Act Coverage" in client.get("/").text
        data = client.get("/api/coverage").json()

    doc_keys = {doc["key"] for doc in data["documents"]}
    assert {norm["doc"] for norm in data["norms"]} <= doc_keys
    assert {rule["doc"] for rule in data["rules"]} <= doc_keys
    assert all(doc["title"] for doc in data["documents"])
    assert any(rule["cases_dev"] for rule in data["rules"])
    for guidance in data["guidance"]:
        decided = sum(guidance.get(k, 0) for k in ("used", "not_followed", "no_effect"))
        assert decided + guidance["awaiting"] == guidance["paragraphs"]
