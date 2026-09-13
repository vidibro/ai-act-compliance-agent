"""Reusable normative-coverage compilation from versioned reviewed inputs."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from aiact.norm_builder import (
    DivisionSource,
    DocumentSource,
    NormBuilderPaths,
    NormSourceInventory,
    NormSourceRecord,
    ParagraphOverride,
    ReviewedDocumentInventory,
    build_artifacts,
    load_builder_inputs,
)
from aiact.policy_loader import article_filename, load_policy_spec
from aiact.schemas.norm import (
    Norm,
    NormRelation,
    NormRelationKind,
    SegmentDisposition,
    SourceKind,
    SubjectCategory,
)
from aiact.yaml_loader import load_yaml_mapping_or_shards

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
    assert norms == {
        "act_version_date": version,
        "norms": [],
        "relations": [],
        "interpretations": [],
    }
    assert [segment["segment_id"] for segment in text["segments"]] == [
        "AIA-TEXT-A004A-HEAD",
        "AIA-TEXT-A004A-P001",
    ]
    assert "".join(segment["text"] for segment in text["segments"]) == body
    assert text["segments"][0]["disposition"] == "structural"
    assert text["segments"][1]["text"] == "Text awaiting review.\n"
    assert text["segments"][1]["disposition"] == "needs_review"


def test_undeclared_document_uses_one_exact_segment_per_source_paragraph(tmp_path):
    version = "2030-01-02"
    body = (
        "Article 1\nPurpose\n\n"
        "1. The provider shall keep records.\n"
        "2. The records shall contain:\n"
        "    (a) the system identifier;\n"
        "    (b) the operating period.\n"
    )
    configured_paths = paths(tmp_path)
    write_article(configured_paths.articles_root, version, "1", body)
    (configured_paths.annexes_root / version).mkdir(parents=True)

    text, _norms = build_artifacts(
        ReviewedDocumentInventory(act_version_date=version, review_run_id="paragraph-review"),
        NormSourceInventory(act_version_date=version),
        configured_paths,
    )

    assert [segment["segment_id"] for segment in text["segments"]] == [
        "AIA-TEXT-A001-HEAD",
        "AIA-TEXT-A001-P001",
        "AIA-TEXT-A001-P002",
        "AIA-TEXT-A001-P003",
        "AIA-TEXT-A001-P004",
    ]
    assert [segment["text"] for segment in text["segments"][1:]] == [
        "1. The provider shall keep records.\n",
        "2. The records shall contain:\n",
        "    (a) the system identifier;\n",
        "    (b) the operating period.\n",
    ]
    assert "".join(segment["text"] for segment in text["segments"]) == body


def test_declared_paragraph_document_can_apply_one_reviewed_disposition(tmp_path):
    version = "2030-01-02"
    body = "Article 1\nDefinitions\n\nA first definition.\nA second definition.\n"
    configured_paths = paths(tmp_path)
    write_article(configured_paths.articles_root, version, "1", body)
    (configured_paths.annexes_root / version).mkdir(parents=True)
    reviewed = ReviewedDocumentInventory(
        act_version_date=version,
        review_run_id="paragraph-review",
        documents=[
            DocumentSource(
                kind=SourceKind.ARTICLE,
                number="1",
                segmentation="paragraphs",
                paragraph_disposition=SegmentDisposition.CONTEXT_ONLY,
                paragraph_reason="Reviewed together as non-operative explanatory text.",
                verified_by="reviewer-b",
                divisions=[
                    DivisionSource(
                        label="HEAD",
                        marker=None,
                        disposition=SegmentDisposition.STRUCTURAL,
                    )
                ],
            )
        ],
    )

    text, _norms = build_artifacts(
        reviewed,
        NormSourceInventory(act_version_date=version),
        configured_paths,
    )

    assert [segment["disposition"] for segment in text["segments"]] == [
        "structural",
        "context_only",
        "context_only",
    ]
    assert all(segment["review"]["status"] == "approved" for segment in text["segments"])
    assert all(segment["review"]["verified_by"] == "reviewer-b" for segment in text["segments"])


def test_paragraph_overrides_approve_only_the_reviewed_chunk(tmp_path):
    version = "2030-01-02"
    body = "Article 1\nMixed review\n\nFirst paragraph.\nSecond paragraph.\n"
    configured_paths = paths(tmp_path)
    write_article(configured_paths.articles_root, version, "1", body)
    (configured_paths.annexes_root / version).mkdir(parents=True)
    reviewed = ReviewedDocumentInventory(
        act_version_date=version,
        review_run_id="partial-paragraph-review",
        documents=[
            DocumentSource(
                kind=SourceKind.ARTICLE,
                number="1",
                segmentation="paragraphs",
                paragraph_overrides={
                    "P001": ParagraphOverride(
                        disposition=SegmentDisposition.CONTEXT_ONLY,
                        reason="Reviewed as explanatory context.",
                        verified_by="reviewer-b",
                    )
                },
                divisions=[
                    DivisionSource(
                        label="HEAD",
                        marker=None,
                        disposition=SegmentDisposition.STRUCTURAL,
                    )
                ],
            )
        ],
    )

    text, _norms = build_artifacts(
        reviewed,
        NormSourceInventory(act_version_date=version),
        configured_paths,
    )

    assert [segment["disposition"] for segment in text["segments"]] == [
        "structural",
        "context_only",
        "needs_review",
    ]
    assert [segment["review"]["status"] for segment in text["segments"]] == [
        "proposed",
        "approved",
        "needs_review",
    ]
    assert text["segments"][1]["review"]["verified_by"] == "reviewer-b"
    assert text["segments"][2]["review"]["verified_by"] == ""


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


def test_condition_relationship_is_canonical_and_legacy_source_field_is_rejected(tmp_path):
    version = "2030-01-02"
    body = (
        "Article 1\nConditions\n\n1. A provider may act if condition A is met.\n2. Condition A.\n"
    )
    configured_paths = paths(tmp_path)
    write_article(configured_paths.articles_root, version, "1", body)
    (configured_paths.annexes_root / version).mkdir(parents=True)
    reviewed = ReviewedDocumentInventory(
        act_version_date=version,
        review_run_id="condition-relation",
        documents=[
            DocumentSource(
                kind=SourceKind.ARTICLE,
                number="1",
                divisions=[
                    DivisionSource(
                        label="HEAD", marker=None, disposition=SegmentDisposition.STRUCTURAL
                    ),
                    DivisionSource(
                        label="P1", marker="1. ", disposition=SegmentDisposition.NORMATIVE
                    ),
                    DivisionSource(
                        label="P2", marker="2. ", disposition=SegmentDisposition.NORMATIVE
                    ),
                ],
            )
        ],
    )
    parent = NormSourceRecord(
        norm_id="AIA-NORM-A001-P1-PERMISSION",
        source="A001-P1",
        quote="may act if condition A is met",
        action="act when condition A is met",
        subject_ref="provider",
        subject_category=SubjectCategory.SUPPORTED_OPERATOR,
    )
    child = NormSourceRecord(
        norm_id="AIA-NORM-A001-P2-CONDITION",
        source="A001-P2",
        quote="Condition A.",
        action="satisfy condition A",
        subject_ref="provider",
        subject_category=SubjectCategory.SUPPORTED_OPERATOR,
    )
    relation = NormRelation(
        relation_id="AIA-REL-A001-P1-CONDITIONAL-ON-P2",
        source_norm_id=parent.norm_id,
        kind=NormRelationKind.CONDITIONAL_ON_NORMS,
        target_norm_ids=[child.norm_id],
        legal_basis_spans=["AIA-TEXT-A001-P1"],
    )
    _text, compiled = build_artifacts(
        reviewed,
        NormSourceInventory(
            act_version_date=version, records=[parent, child], norm_relations=[relation]
        ),
        configured_paths,
    )
    norms = {norm["norm_id"]: norm for norm in compiled["norms"]}
    assert "condition_norm_ids" not in norms[parent.norm_id]
    assert "condition_of_norm_ids" not in norms[child.norm_id]
    assert compiled["relations"] == [relation.model_dump(mode="json")]

    with pytest.raises(ValueError, match="condition_norm_ids"):
        NormSourceRecord.model_validate(
            {**parent.model_dump(), "condition_norm_ids": [child.norm_id]}
        )
    with pytest.raises(ValueError, match="condition_norm_ids"):
        Norm.model_validate({**norms[parent.norm_id], "condition_norm_ids": [child.norm_id]})


@pytest.mark.parametrize(
    ("kind", "targets"),
    [
        (NormRelationKind.RELIES_ON_NORMS, {"target_norm_ids": ["AIA-NORM-A001-P2-CHILD"]}),
        (
            NormRelationKind.INTERPRETED_BY_COMMISSION_GUIDANCE,
            {"guidance_refs": ["C-2025-5052/example"]},
        ),
        (
            NormRelationKind.OUT_OF_SCOPE_REGULATION,
            {"external_regulations": ["national procurement law"]},
        ),
        (NormRelationKind.UNRESOLVED_DEPENDENCY, {"detail": "Target is not yet identified."}),
        (NormRelationKind.MISSING_DEPENDENCY, {"detail": "Required target is absent."}),
    ],
)
def test_dependency_relation_kinds_have_only_their_declared_target(kind, targets):
    relation = NormRelation(
        relation_id="AIA-REL-A001-P1-DEPENDENCY",
        source_norm_id="AIA-NORM-A001-P1-PARENT",
        kind=kind,
        legal_basis_spans=["AIA-TEXT-A001-P1"],
        **targets,
    )

    assert relation.kind is kind


def test_relation_schema_rejects_retired_factual_conditions_field():
    with pytest.raises(ValueError, match="factual_conditions"):
        NormRelation.model_validate(
            {
                "relation_id": "AIA-REL-A001-P1-DEPENDENCY",
                "source_norm_id": "AIA-NORM-A001-P1-PARENT",
                "kind": "relies_on_norms",
                "target_norm_ids": ["AIA-NORM-A001-P2-CHILD"],
                "legal_basis_spans": ["AIA-TEXT-A001-P1"],
                "factual_conditions": [],
            }
        )


def test_source_record_rejects_legacy_internal_norm_dependency():
    with pytest.raises(ValueError, match="internal norm dependencies must use relies_on_norms"):
        NormSourceRecord.model_validate(
            {
                "norm_id": "AIA-NORM-A001-P1-PARENT",
                "source": "A001-P1",
                "quote": "Parent requirement.",
                "action": "meet the parent requirement",
                "subject_ref": "provider",
                "subject_category": "supported_operator",
                "dependencies": [
                    {
                        "dependency_ref": "AIA-NORM-A001-P2-CHILD",
                        "resolution": "internal_resolved",
                    }
                ],
            }
        )


def test_document_verifier_approves_all_non_debt_segments(tmp_path):
    version = "2030-01-02"
    body = "Article 1\nPurpose\n\n1. Context only.\n"
    configured_paths = paths(tmp_path)
    write_article(configured_paths.articles_root, version, "1", body)
    (configured_paths.annexes_root / version).mkdir(parents=True)
    reviewed = ReviewedDocumentInventory(
        act_version_date=version,
        review_run_id="verified-review",
        documents=[
            DocumentSource(
                kind=SourceKind.ARTICLE,
                number="1",
                verified_by="reviewer-b",
                divisions=[
                    DivisionSource(
                        label="HEAD",
                        marker=None,
                        disposition=SegmentDisposition.STRUCTURAL,
                    ),
                    DivisionSource(
                        label="P1",
                        marker="1. ",
                        disposition=SegmentDisposition.CONTEXT_ONLY,
                        reason="The paragraph creates no independent legal proposition.",
                    ),
                ],
            )
        ],
    )

    text, _norms = build_artifacts(
        reviewed,
        NormSourceInventory(act_version_date=version),
        configured_paths,
    )

    assert all(segment["review"]["status"] == "approved" for segment in text["segments"])
    assert all(segment["review"]["verified_by"] == "reviewer-b" for segment in text["segments"])


def test_document_verifier_cannot_approve_review_debt():
    with pytest.raises(ValueError, match="review-debt divisions"):
        DocumentSource(
            kind=SourceKind.ARTICLE,
            number="1",
            verified_by="reviewer-b",
            divisions=[
                DivisionSource(
                    label="P1",
                    marker=None,
                    disposition=SegmentDisposition.NEEDS_REVIEW,
                    reason="Not reviewed.",
                )
            ],
        )


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


def test_yaml_inventory_shards_merge_metadata_lists_and_mappings(tmp_path):
    shard_root = tmp_path / "source-records"
    (shard_root / "articles").mkdir(parents=True)
    (shard_root / "manifest.yaml").write_text(
        "act_version_date: 2030-01-02\nimplementation_targets: [RULE-1]\n"
        "carried_by: {NORM-2: [NORM-1]}\n",
        encoding="utf-8",
    )
    (shard_root / "articles" / "001.yaml").write_text(
        "records:\n- {norm_id: NORM-1}\n",
        encoding="utf-8",
    )
    (shard_root / "articles" / "002.yaml").write_text(
        "records:\n- {norm_id: NORM-2}\n",
        encoding="utf-8",
    )

    merged = load_yaml_mapping_or_shards(shard_root, description="test inventory")

    assert merged == {
        "act_version_date": date(2030, 1, 2),
        "implementation_targets": ["RULE-1"],
        "carried_by": {"NORM-2": ["NORM-1"]},
        "records": [{"norm_id": "NORM-1"}, {"norm_id": "NORM-2"}],
    }


def test_versioned_implementation_targets_exist_in_the_pinned_policy_spec():
    """Targets come in two families, each resolved against its own registry: an obligation is
    implemented by a policy rule, an applicability question by a cascade node. Both must name
    something that exists, or the norm claims an implementation it does not have."""
    from aiact.classify.graph import QUESTIONS

    source_path = ROOT / "data" / "policy" / "normative-coverage" / "2026-07-27" / "source-records"
    source_inventory = NormSourceInventory.model_validate(
        load_yaml_mapping_or_shards(source_path, description="norm source inventory")
    )
    policy = load_policy_spec()
    targets = set(source_inventory.implementation_targets)
    questions = {target for target in targets if target.startswith("AIA-CQ-")}

    assert source_inventory.act_version_date == policy.act_version_date
    assert targets - questions <= {rule.rule_id for rule in policy.rules}
    assert questions == {f"AIA-CQ-{node.upper().replace('_', '-')}" for node in QUESTIONS}
