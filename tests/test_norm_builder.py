"""Reusable normative-coverage compilation from versioned reviewed inputs."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from aiact.norm_builder import (
    DivisionSource,
    DocumentSource,
    NormBuilderPaths,
    NormSourceInventory,
    NormSourceRecord,
    ReviewedDocumentInventory,
    build_artifacts,
    load_builder_inputs,
)
from aiact.policy_loader import article_filename, load_policy_spec
from aiact.schemas.norm import SegmentDisposition, SourceKind, SubjectCategory
from aiact.yaml_loader import load_yaml_mapping

ROOT = Path(__file__).resolve().parents[1]


def write_article(root: Path, version: str, number: str, body: str) -> None:
    version_root = root / version
    version_root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(body.encode()).hexdigest()
    (version_root / article_filename(number)).write_text(
        f"---\nact_version_date: {version}\nsha256: {digest}\n---\n{body}",
        encoding="utf-8",
    )


def paths(tmp_path: Path) -> NormBuilderPaths:
    return NormBuilderPaths(
        reviewed_documents=tmp_path / "segments.yaml",
        norm_sources=tmp_path / "source-records.yaml",
        articles_root=tmp_path / "articles",
        annexes_root=tmp_path / "annexes",
        guidance_root=tmp_path / "guidance",
        text_output=tmp_path / "text-review.yaml",
        norm_output=tmp_path / "norms.yaml",
        report_output=tmp_path / "report.md",
        generated_by="test builder",
    )


def test_generic_builder_uses_input_version_and_discovers_its_complete_corpus(tmp_path):
    version = "2030-01-02"
    body = "Article 4a\nFuture provision\n\nText awaiting review.\n"
    configured_paths = paths(tmp_path)
    write_article(configured_paths.articles_root, version, "4a", body)
    (configured_paths.annexes_root / version).mkdir(parents=True)

    text, norms = build_artifacts(
        ReviewedDocumentInventory(
            act_version_date=version,
            review_run_id="future-review",
        ),
        NormSourceInventory(act_version_date=version),
        configured_paths,
    )

    assert text["act_version_date"] == version
    assert text["corpus_complete"] is True
    assert norms == {"act_version_date": version, "norms": [], "interpretations": []}
    segment = text["segments"][0]
    assert segment["segment_id"] == "AIA-TEXT-A004A-FULL"
    assert segment["text"] == body
    assert segment["disposition"] == "needs_review"


def test_reviewed_divisions_and_norm_sources_compile_without_version_specific_code(tmp_path):
    version = "2030-01-02"
    body = "Article 1\nPurpose\n\n1. The provider shall keep a record.\n"
    configured_paths = paths(tmp_path)
    write_article(configured_paths.articles_root, version, "1", body)
    (configured_paths.annexes_root / version).mkdir(parents=True)
    reviewed = ReviewedDocumentInventory(
        act_version_date=version,
        review_run_id="future-review",
        documents=[
            DocumentSource(
                kind=SourceKind.ARTICLE,
                number="1",
                divisions=[
                    DivisionSource(
                        label="HEAD",
                        marker=None,
                        disposition=SegmentDisposition.STRUCTURAL,
                    ),
                    DivisionSource(
                        label="P1",
                        marker="1. ",
                        disposition=SegmentDisposition.NORMATIVE,
                    ),
                ],
            )
        ],
    )
    sources = NormSourceInventory(
        act_version_date=version,
        records=[
            NormSourceRecord(
                norm_id="AIA-NORM-A001-P1-RECORD",
                source="A001-P1",
                quote="shall keep a record",
                action="keep a record",
                subject_ref="provider",
                subject_category=SubjectCategory.SUPPORTED_OPERATOR,
            )
        ],
    )

    text, norms = build_artifacts(reviewed, sources, configured_paths)

    normative_segment = text["segments"][1]
    assert normative_segment["segment_id"] == "AIA-TEXT-A001-P1"
    assert normative_segment["norm_ids"] == ["AIA-NORM-A001-P1-RECORD"]
    norm = norms["norms"][0]
    assert norm["act_version_date"] == version
    assert norm["primary_spans"] == ["AIA-TEXT-A001-P1"]
    assert norm["implementation_mode"] == "missing"


def test_versioned_builder_inputs_must_use_the_same_act_snapshot(tmp_path):
    configured_paths = paths(tmp_path)
    configured_paths.reviewed_documents.write_text(
        "act_version_date: 2030-01-02\nreview_run_id: run\ndocuments: []\n",
        encoding="utf-8",
    )
    configured_paths.norm_sources.write_text(
        "act_version_date: 2030-01-03\nrecords: []\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="different Act versions"):
        load_builder_inputs(configured_paths)


def test_versioned_implementation_targets_exist_in_the_pinned_policy_spec():
    source_path = (
        ROOT
        / "data"
        / "policy"
        / "normative-coverage"
        / "2026-07-27"
        / "source-records.yaml"
    )
    source_inventory = NormSourceInventory.model_validate(
        load_yaml_mapping(source_path, description="norm source inventory")
    )
    policy = load_policy_spec()

    assert source_inventory.act_version_date == policy.act_version_date
    assert set(source_inventory.implementation_targets) <= {
        rule.rule_id for rule in policy.rules
    }
