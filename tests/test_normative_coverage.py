"""Exact source spans, atomic norms, and interpretive-link assurance."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from yaml.constructor import ConstructorError

from aiact.config import get_settings
from aiact.norm_loader import load_normative_coverage
from aiact.policy_loader import article_filename, provision_text, source_body
from aiact.schemas.interpretation import InterpretiveLink
from aiact.schemas.norm import (
    Norm,
    NormInventory,
    ReviewRecord,
    TextReviewInventory,
    TextReviewSegment,
)

ROOT = Path(__file__).resolve().parents[1]
ARTICLES = ROOT / "data" / "policy" / "articles"
ANNEXES = ROOT / "data" / "policy" / "annexes"
GUIDANCE = ROOT / "data" / "policy" / "guidance"
VERSION = get_settings().act_version_date.isoformat()
ARTICLE = "32"  # short, undivided, and still a real integrity-checked source
ARTICLE_PATH = ARTICLES / VERSION / article_filename(ARTICLE)


def approved_review() -> dict:
    return {
        "status": "approved",
        "extracted_by": "source-pass-a",
        "verified_by": "reviewer-b",
        "review_run_id": "run-1",
        "presentation_mode": "complete-text",
        "display_chunks": 1,
        "fully_displayed": True,
    }


def segment(
    body: str,
    start: int,
    end: int,
    segment_id: str,
    norm_ids: list[str] | None = None,
) -> dict:
    text = body[start:end]
    return {
        "segment_id": segment_id,
        "source": {
            "kind": "article",
            "document": ARTICLE,
            "act_version_date": VERSION,
        },
        "start": start,
        "end": end,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "text": text,
        "disposition": "normative" if norm_ids else "structural",
        "norm_ids": norm_ids or [],
        "review": approved_review(),
    }


def norm(norm_id: str, spans: list[str]) -> dict:
    return {
        "norm_id": norm_id,
        "act_version_date": VERSION,
        "kind": "obligation",
        "subjects": [{"subject_ref": "provider", "category": "supported_operator"}],
        "action": "perform the reviewed action",
        "norm_text": "Article 32",
        "detection_channels": ["semantic_legal_effect"],
        "primary_spans": spans,
        "product_scope": "in_scope",
        "implementation_mode": "missing",
        "verification_mode": "unresolved",
        "review": approved_review(),
    }


def artifacts(tmp_path: Path, text: dict, norms: dict) -> tuple[Path, Path]:
    text_path = tmp_path / "text.yaml"
    norm_path = tmp_path / "norms.yaml"
    text_path.write_text(yaml.safe_dump(text, sort_keys=False), encoding="utf-8")
    norm_path.write_text(yaml.safe_dump(norms, sort_keys=False), encoding="utf-8")
    return text_path, norm_path


def load(tmp_path: Path, text: dict, norms: dict):
    text_path, norm_path = artifacts(tmp_path, text, norms)
    return load_normative_coverage(
        text_path,
        norm_path,
        articles_root=ARTICLES,
        annexes_root=ANNEXES,
        guidance_root=GUIDANCE,
    )


def one_document() -> tuple[str, dict, dict]:
    body = source_body(ARTICLE_PATH)
    split = len(body) // 2
    first = "AIA-TEXT-032-A"
    second = "AIA-TEXT-032-B"
    norm_id = "AIA-NORM-032-A"
    text = {
        "act_version_date": VERSION,
        "corpus_complete": False,
        "segments": [
            segment(body, 0, split, first, [norm_id]),
            segment(body, split, len(body), second, [norm_id]),
        ],
    }
    norms = {
        "act_version_date": VERSION,
        "norms": [norm(norm_id, [first, second])],
        "interpretations": [],
    }
    return body, text, norms


def truncate_last_segment(items: list[dict]) -> None:
    item = items[-1]
    item["end"] -= 1
    item["text"] = item["text"][:-1]
    item["sha256"] = hashlib.sha256(item["text"].encode()).hexdigest()


def test_repository_coverage_artifacts_load_without_touching_runtime():
    bundle = load_normative_coverage(
        articles_root=ARTICLES,
        annexes_root=ANNEXES,
        guidance_root=GUIDANCE,
    )
    assert bundle.runtime_integrated is False
    assert bundle.text_review.corpus_complete is True
    assert bundle.validated_documents == 133
    assert bundle.validated_segments == 1429
    assert bundle.validated_norms == 796


def test_exact_source_body_preserves_characters_that_rule_text_strips():
    exact = source_body(ARTICLE_PATH)
    assert exact.endswith("\n")
    assert provision_text(ARTICLE_PATH) == exact.strip()


def test_exact_source_body_rejects_a_different_version_pin(tmp_path):
    body = "Article 1\nTitle\n\nText.\n"
    digest = hashlib.sha256(body.encode()).hexdigest()
    path = tmp_path / "article-001.md"
    path.write_text(
        f"---\nact_version_date: 2024-07-12\nsha256: {digest}\n---\n{body}",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="pinned to '2026-07-27'"):
        source_body(path, expected_version="2026-07-27")


def test_an_included_document_must_be_partitioned_exactly(tmp_path):
    body, text, norms = one_document()
    bundle = load(tmp_path, text, norms)
    assert bundle.validated_documents == 1
    assert "".join(s.text for s in bundle.text_review.segments) == body


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda items: items[1].update(start=items[1]["start"] + 1), "gap before"),
        (lambda items: items[1].update(start=items[1]["start"] - 1), "overlap before"),
        (truncate_last_segment, "leaving 1 characters"),
        (lambda items: items[0].update(text=items[0]["text"] + "x"), "not the exact source"),
        (lambda items: items[0].update(sha256="0" * 64), "sha256 does not match"),
    ],
)
def test_partition_mutations_fail(tmp_path, mutation, message):
    _body, text, norms = one_document()
    mutation(text["segments"])
    with pytest.raises(ValueError, match=message):
        load(tmp_path, text, norms)


def test_corpus_complete_cannot_be_claimed_for_one_article(tmp_path):
    _body, text, norms = one_document()
    text["corpus_complete"] = True
    with pytest.raises(ValueError, match="corpus_complete.*missing"):
        load(tmp_path, text, norms)


def test_segment_version_must_match_inventory(tmp_path):
    _body, text, norms = one_document()
    text["segments"][0]["source"]["act_version_date"] = "2024-07-12"
    with pytest.raises(ValueError, match="uses Act version"):
        load(tmp_path, text, norms)


def test_norm_version_must_match_inventory(tmp_path):
    _body, text, norms = one_document()
    norms["norms"][0]["act_version_date"] = "2024-07-12"
    with pytest.raises(ValueError, match="uses Act version"):
        load(tmp_path, text, norms)


def test_norm_and_text_artifacts_must_use_the_same_version(tmp_path):
    _body, text, norms = one_document()
    norms["act_version_date"] = "2024-07-12"
    with pytest.raises(ValueError, match="different Act versions"):
        load(tmp_path, text, norms)


def test_norm_cannot_reference_an_unknown_span(tmp_path):
    _body, text, norms = one_document()
    norms["norms"][0]["primary_spans"].append("AIA-TEXT-032-MISSING")
    with pytest.raises(ValueError, match="unknown segment"):
        load(tmp_path, text, norms)


def test_norm_text_must_be_an_exact_quote_from_a_primary_span(tmp_path):
    _body, text, norms = one_document()
    norms["norms"][0]["norm_text"] = "paraphrased legal proposition"
    with pytest.raises(ValueError, match="norm_text is not an exact substring"):
        load(tmp_path, text, norms)


def test_norm_detection_channels_are_unique():
    raw = norm("AIA-NORM-032-A", ["AIA-TEXT-032-A"])
    raw["detection_channels"] = ["semantic_legal_effect", "semantic_legal_effect"]
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        Norm.model_validate(raw)


def test_segment_and_norm_links_must_agree_in_both_directions(tmp_path):
    _body, text, norms = one_document()
    text["segments"][1]["norm_ids"] = []
    text["segments"][1]["disposition"] = "structural"
    with pytest.raises(ValueError, match="norm links disagree"):
        load(tmp_path, text, norms)


def test_carried_norm_must_exist(tmp_path):
    _body, text, norms = one_document()
    item = norms["norms"][0]
    item["implementation_mode"] = "carried_by_other_norm"
    item["carried_by_norm_ids"] = ["AIA-NORM-032-MISSING"]
    with pytest.raises(ValueError, match="carried by unknown norm"):
        load(tmp_path, text, norms)


def test_superseded_norm_must_name_an_existing_successor(tmp_path):
    _body, text, norms = one_document()
    item = norms["norms"][0]
    item["review"]["status"] = "superseded"
    item["superseded_by_norm_ids"] = ["AIA-NORM-032-MISSING"]
    with pytest.raises(ValueError, match="superseded by unknown norm"):
        load(tmp_path, text, norms)


def test_internal_dependency_must_resolve_to_a_norm_or_segment(tmp_path):
    _body, text, norms = one_document()
    norms["norms"][0]["dependencies"] = [
        {
            "dependency_ref": "AIA-NORM-032-MISSING",
            "resolution": "internal_resolved",
        }
    ]
    with pytest.raises(ValueError, match="unresolved internal dependency"):
        load(tmp_path, text, norms)


def test_carried_norms_cannot_form_a_cycle(tmp_path):
    body, text, norms = one_document()
    first = norms["norms"][0]
    first["implementation_mode"] = "carried_by_other_norm"
    first["carried_by_norm_ids"] = ["AIA-NORM-032-B"]
    second = norm("AIA-NORM-032-B", ["AIA-TEXT-032-A"])
    second["implementation_mode"] = "carried_by_other_norm"
    second["carried_by_norm_ids"] = ["AIA-NORM-032-A"]
    norms["norms"].append(second)
    text["segments"][0]["norm_ids"].append("AIA-NORM-032-B")
    assert text["segments"][0]["text"] == body[: len(body) // 2]
    with pytest.raises(ValueError, match="cycle"):
        load(tmp_path, text, norms)


def test_approved_review_requires_an_independent_verifier():
    raw = approved_review()
    raw["verified_by"] = raw["extracted_by"]
    with pytest.raises(ValidationError, match="independent verifier"):
        ReviewRecord.model_validate(raw)


def test_approved_review_requires_the_whole_span_to_have_been_displayed():
    raw = approved_review()
    raw["fully_displayed"] = False
    with pytest.raises(ValidationError, match="full source"):
        ReviewRecord.model_validate(raw)


def test_a_normative_segment_requires_a_norm_link():
    body = source_body(ARTICLE_PATH)
    raw = segment(body, 0, len(body), "AIA-TEXT-032-A")
    raw["disposition"] = "normative"
    with pytest.raises(ValidationError, match="requires at least one norm_id"):
        TextReviewSegment.model_validate(raw)


def test_context_only_requires_a_reviewed_reason():
    body = source_body(ARTICLE_PATH)
    raw = segment(body, 0, len(body), "AIA-TEXT-032-A")
    raw["disposition"] = "context_only"
    with pytest.raises(ValidationError, match="requires disposition_reason"):
        TextReviewSegment.model_validate(raw)


def test_out_of_scope_norm_requires_a_reason():
    raw = norm("AIA-NORM-032-A", ["AIA-TEXT-032-A"])
    raw["product_scope"] = "outside_supported_actor"
    with pytest.raises(ValidationError, match="requires a reason"):
        Norm.model_validate(raw)


def test_none_required_implementation_requires_a_reason():
    raw = norm("AIA-NORM-032-A", ["AIA-TEXT-032-A"])
    raw["implementation_mode"] = "none_required"
    with pytest.raises(ValidationError, match="requires a reason"):
        Norm.model_validate(raw)


def interpretation(norm_id: str) -> dict:
    return {
        "interpretation_id": "AIA-INT-WORKPLACE-RECRUITMENT",
        "snippet_refs": ["C-2025-5052/workplace-covers-recruitment"],
        "norm_ids": [norm_id],
        "targets": [{"kind": "classification_question", "target_id": "prohibited"}],
        "effect": "expands_scope",
        "review_scope": "passage_with_context",
        "review_scope_detail": "paragraph (254), page 86 and adjacent worked examples",
        "binding": False,
        "review": approved_review(),
    }


def test_interpretive_link_resolves_verified_guidance_and_norm(tmp_path):
    _body, text, norms = one_document()
    norm_id = norms["norms"][0]["norm_id"]
    norms["interpretations"] = [interpretation(norm_id)]
    bundle = load(tmp_path, text, norms)
    assert bundle.norm_inventory.interpretations[0].binding is False


def test_guidance_linked_dependency_requires_an_interpretive_link(tmp_path):
    _body, text, norms = one_document()
    norms["norms"][0]["dependencies"] = [
        {
            "dependency_ref": "C-2025-5052/workplace-covers-recruitment",
            "resolution": "guidance_linked",
        }
    ]
    with pytest.raises(ValueError, match="without a matching interpretive link"):
        load(tmp_path, text, norms)


def test_guidance_dependency_must_match_the_linked_snippet(tmp_path):
    _body, text, norms = one_document()
    norm_id = norms["norms"][0]["norm_id"]
    norms["norms"][0]["dependencies"] = [
        {
            "dependency_ref": "C-2026-5054/synthetic-content-disclosure",
            "resolution": "guidance_linked",
        }
    ]
    norms["interpretations"] = [interpretation(norm_id)]
    with pytest.raises(ValueError, match="without a matching interpretive link"):
        load(tmp_path, text, norms)


def test_interpretive_link_cannot_call_guidance_binding():
    raw = interpretation("AIA-NORM-032-A")
    raw["binding"] = True
    with pytest.raises(ValidationError, match="False"):
        InterpretiveLink.model_validate(raw)


def test_bounded_guidance_review_requires_its_boundary():
    raw = interpretation("AIA-NORM-032-A")
    raw["review_scope_detail"] = ""
    with pytest.raises(ValidationError, match="requires review_scope_detail"):
        InterpretiveLink.model_validate(raw)


def test_interpretive_link_must_name_a_known_norm(tmp_path):
    _body, text, norms = one_document()
    norms["interpretations"] = [interpretation("AIA-NORM-032-MISSING")]
    with pytest.raises(ValueError, match="unknown norm"):
        load(tmp_path, text, norms)


def test_interpretive_link_must_resolve_a_verified_snippet(tmp_path):
    _body, text, norms = one_document()
    item = interpretation(norms["norms"][0]["norm_id"])
    item["snippet_refs"] = ["C-2025-5052/not-there"]
    norms["interpretations"] = [item]
    with pytest.raises(FileNotFoundError, match="guidance snippet"):
        load(tmp_path, text, norms)


def test_duplicate_segment_and_norm_ids_are_rejected():
    _body, text, norms = one_document()
    text["segments"].append(deepcopy(text["segments"][0]))
    with pytest.raises(ValidationError, match="duplicate segment_id"):
        TextReviewInventory.model_validate(text)

    norms["norms"].append(deepcopy(norms["norms"][0]))
    with pytest.raises(ValidationError, match="duplicate norm_id"):
        NormInventory.model_validate(norms)


def test_duplicate_yaml_mapping_keys_are_rejected(tmp_path):
    text_path = tmp_path / "text.yaml"
    norm_path = tmp_path / "norms.yaml"
    text_path.write_text(
        "act_version_date: 2026-07-27\ncorpus_complete: false\nsegments: []\nsegments: []\n",
        encoding="utf-8",
    )
    norm_path.write_text(
        "act_version_date: 2026-07-27\nnorms: []\ninterpretations: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ConstructorError, match="duplicate key 'segments'"):
        load_normative_coverage(text_path, norm_path)
