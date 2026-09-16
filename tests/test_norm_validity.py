"""Stable validity findings become enforceable through reviewed adjudications."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from aiact.norm_loader import load_normative_coverage
from aiact.norm_validity import (
    apply_recorded_fix,
    audit_attestation,
    audit_norm_validity,
    enforce_validity_adjudications,
    load_adjudication_ledger,
)
from aiact.schemas.norm import SourceKind

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data" / "policy"
COVERAGE = POLICY / "normative-coverage" / "2026-07-27"
LEDGER = COVERAGE / "adjudications"
SHARD = LEDGER / "articles" / "015.yaml"


def load_bundle():
    return load_normative_coverage(
        COVERAGE / "text-review",
        COVERAGE / "norms",
        articles_root=POLICY / "articles",
        annexes_root=POLICY / "annexes",
        guidance_root=POLICY / "guidance",
    )


def copied_ledger(tmp_path: Path) -> tuple[Path, dict, dict]:
    """A writable manifest/shard pair for one test's isolated mutation."""
    root = tmp_path / "adjudications"
    manifest = yaml.safe_load((LEDGER / "index.yaml").read_text(encoding="utf-8"))
    shard = yaml.safe_load(SHARD.read_text(encoding="utf-8"))
    for declared in manifest["shards"]:
        source = LEDGER / declared["file"]
        target = root / declared["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    for source in (LEDGER.parent / "fixes").glob("*.patch.yaml"):
        target = root.parent / "fixes" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        patch = yaml.safe_load(source.read_text(encoding="utf-8"))
        canonical_target = LEDGER.parent / patch["target_file"]
        copied_target = root.parent / patch["target_file"]
        copied_target.parent.mkdir(parents=True, exist_ok=True)
        copied_target.write_bytes(canonical_target.read_bytes())
    return root, manifest, shard


def write_ledger(root: Path, manifest: dict, shard: dict) -> Path:
    (root / "index.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (root / "articles" / "015.yaml").write_text(
        yaml.safe_dump(shard, sort_keys=False), encoding="utf-8"
    )
    return root


def refresh_article_fifteen_audit(root: Path, bundle) -> None:
    """A recorded fix changes the audited norm snapshot and therefore requires a fresh audit."""
    shard_path = root / "articles" / "015.yaml"
    shard = yaml.safe_load(shard_path.read_text(encoding="utf-8"))
    shard["audit"] = audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "15")}
    ).model_dump(mode="json")
    shard_path.write_text(yaml.safe_dump(shard, sort_keys=False), encoding="utf-8")


def test_article_fifteen_findings_are_stable_and_fully_adjudicated():
    bundle = load_bundle()
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "15")})

    assert {finding.finding_id for finding in findings} == {
        "AIA-VALID-135096E293C37A15",
        "AIA-VALID-9EC25FA4CC5D0B6C",
        "AIA-VALID-6368468E67B41E10",
        "AIA-VALID-37D8E4202A80F45B",
        "AIA-VALID-9315A03614CD290E",
        "AIA-VALID-68BAAE428CB98553",
        "AIA-VALID-EB70A75FE17CB5C0",
    }
    assert enforce_validity_adjudications(bundle, LEDGER) == (63, 64)


def test_article_sixteen_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()

    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "16")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "16")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "16")}
    )
    # Article 16 adds no decisions, but its hash-bound audit proves that the zero is current.
    assert enforce_validity_adjudications(bundle, LEDGER) == (63, 64)


def test_article_ten_findings_are_recorded_in_its_own_shard():
    bundle = load_bundle()

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "10")})
    assert {finding.finding_id for finding in findings} == {
        "AIA-VALID-3055859FD804996F",
        "AIA-VALID-CD1D0313E0D42BCD",
        "AIA-VALID-3649F8849C42880C",
        "AIA-VALID-6D85A1D563F40FFA",
        "AIA-VALID-A9EC122C931BAB2F",
    }
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "10")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "10")}
    )


def test_article_five_findings_are_recorded_in_its_own_shard():
    bundle = load_bundle()

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "5")})
    assert {finding.finding_id for finding in findings} == {
        "AIA-VALID-5B7FCD27DF45309C",
        "AIA-VALID-DC823E5A83D8EE0D",
        "AIA-VALID-D2ABA6D6C6B42844",
        "AIA-VALID-62C9635045474CEA",
        "AIA-VALID-BF5D52A6D881F67C",
        "AIA-VALID-3B5963DF02D90B91",
        "AIA-VALID-FFFAA9BB86305D59",
        "AIA-VALID-CC024E9D9725C0ED",
        "AIA-VALID-73B9E41ED09A43EA",
        "AIA-VALID-F92BDFB651B38558",
        "AIA-VALID-2F3A48673D9CF580",
    }
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "5")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "5")}
    )


def test_article_six_profiling_override_finding_is_adjudicated():
    bundle = load_bundle()

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "6")})
    assert {finding.finding_id for finding in findings} == {"AIA-VALID-F54275A92121A610"}
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "6")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "6")}
    )


def test_article_seven_legal_consequence_finding_is_adjudicated():
    bundle = load_bundle()

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "7")})
    assert {finding.finding_id for finding in findings} == {"AIA-VALID-B382E4EBE1A01D32"}
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "7")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "7")}
    )


def test_article_eight_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()

    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "8")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "8")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "8")}
    )


def test_article_nine_structural_findings_are_recorded_in_its_own_shard():
    bundle = load_bundle()
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "9")})

    assert len(findings) == 7
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "9")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "9")}
    )


def test_article_eleven_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()
    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "11")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "11")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "11")}
    )


def test_article_twelve_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()
    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "12")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "12")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "12")}
    )


def test_article_seventeen_findings_are_recorded_in_its_own_shard():
    bundle = load_bundle()

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "17")})
    assert {finding.finding_id for finding in findings} == {
        "AIA-VALID-61D9AC963E66CBF0",
        "AIA-VALID-C96B327A7FEA05BA",
        "AIA-VALID-87FF392123F03574",
    }
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "17")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "17")}
    )


def test_article_two_scope_findings_are_recorded_in_its_own_shard():
    bundle = load_bundle()
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "2")})

    assert len(findings) == 8
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "2")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "2")}
    )


def test_article_three_definition_findings_are_recorded_in_its_own_shard():
    bundle = load_bundle()
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "3")})

    assert len(findings) == 8
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "3")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "3")}
    )


def test_article_four_literacy_finding_is_recorded_in_its_own_shard():
    bundle = load_bundle()
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "4")})

    assert {finding.finding_id for finding in findings} == {"AIA-VALID-703E31C51690F78F"}
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "4")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "4")}
    )


def test_article_fifty_nine_conditions_are_recorded_in_its_own_shard():
    bundle = load_bundle()
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "59")})

    assert len(findings) == 10
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "59")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "59")}
    )


def test_audit_hashes_nested_structured_conditions_as_canonical_json():
    bundle = load_bundle()

    # Article 3 includes nested all-of/any-of condition groups. The audit must remain fully
    # deterministic rather than failing to serialize those structured legal conditions.
    audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "3")})


def test_missing_adjudication_fails_closed(tmp_path):
    bundle = load_bundle()
    root, manifest, shard = copied_ledger(tmp_path)
    shard["decisions"] = shard["decisions"][:-1]
    path = write_ledger(root, manifest, shard)

    with pytest.raises(ValueError, match="lack adjudication"):
        enforce_validity_adjudications(bundle, path)


def test_changed_source_hash_invalidates_adjudication(tmp_path):
    bundle = load_bundle()
    root, manifest, shard = copied_ledger(tmp_path)
    shard["decisions"][0]["source_sha256"] = "0" * 64
    path = write_ledger(root, manifest, shard)

    with pytest.raises(ValueError, match="no longer matches"):
        enforce_validity_adjudications(bundle, path)


def test_changed_norm_record_requires_a_new_adjudication():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P5-MODEL-FLAWS"
    )
    norm.action = f"{norm.action} with a changed interpretation"

    with pytest.raises(ValueError, match="audit attestation is stale"):
        enforce_validity_adjudications(bundle, LEDGER)


def test_legal_basis_must_be_an_exact_source_quote(tmp_path):
    bundle = load_bundle()
    root, manifest, shard = copied_ledger(tmp_path)
    fragment = next(
        decision
        for decision in shard["decisions"]
        if decision["target"] == "AIA-NORM-A015-P5-MODEL-FLAWS"
    )
    fragment["legal_basis"][0]["quote"] = "words that are not in the enacted source"
    path = write_ledger(root, manifest, shard)

    with pytest.raises(ValueError, match="basis quote is not exact"):
        enforce_validity_adjudications(bundle, path)


def test_manifest_rejects_an_undeclared_shard(tmp_path):
    root, manifest, shard = copied_ledger(tmp_path)
    write_ledger(root, manifest, shard)
    (root / "articles" / "019.yaml").write_text(
        yaml.safe_dump(shard, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="shard set differs from manifest"):
        load_adjudication_ledger(root)


def test_manifest_rejects_a_shard_with_the_wrong_declared_source(tmp_path):
    root, manifest, shard = copied_ledger(tmp_path)
    shard["source"]["document"] = "16"
    path = write_ledger(root, manifest, shard)

    with pytest.raises(ValueError, match="source differs from manifest"):
        load_adjudication_ledger(path)


def test_manifest_rejects_a_finding_duplicated_across_shards(tmp_path):
    root, manifest, shard = copied_ledger(tmp_path)
    manifest["enforced_scope"].append({"kind": "article", "document": "19"})
    manifest["shards"].append({"kind": "article", "document": "19", "file": "articles/019.yaml"})
    write_ledger(root, manifest, shard)
    duplicate = {**shard, "source": {"kind": "article", "document": "19"}}
    (root / "articles" / "019.yaml").write_text(
        yaml.safe_dump(duplicate, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(
        ValueError, match="duplicate validity adjudication finding_id across shards"
    ):
        load_adjudication_ledger(root)


def _fixed_p2_ledger(tmp_path: Path) -> tuple[Path, Path, bytes, bytes]:
    root = tmp_path / "coverage"
    target = root / "source-records" / "articles" / "015.yaml"
    target.parent.mkdir(parents=True)
    before = b"quote: old fragment\n"
    after = b"quote: complete sentence\n"
    target.write_bytes(before)

    manifest = yaml.safe_load((LEDGER / "index.yaml").read_text(encoding="utf-8"))
    manifest["enforced_scope"] = [{"kind": "article", "document": "15"}]
    manifest["shards"] = [{"kind": "article", "document": "15", "file": "articles/015.yaml"}]
    shard = yaml.safe_load(SHARD.read_text(encoding="utf-8"))
    fixed = next(
        item
        for item in shard["decisions"]
        if item["target"] == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    fixed["decision"] = "fixed"
    fixed["reason"] = "The canonical source record was rewritten to retain the full sentence."
    patch_payload = {
        "schema_version": 1,
        "finding_id": fixed["finding_id"],
        "target_file": "source-records/articles/015.yaml",
        "before_sha256": hashlib.sha256(before).hexdigest(),
        "after_sha256": hashlib.sha256(after).hexdigest(),
        "replacements": [
            {
                "old": "quote: old fragment",
                "new": "quote: complete sentence",
                "expected_occurrences": 1,
            }
        ],
    }
    patch_bytes = yaml.safe_dump(patch_payload, sort_keys=False).encode()
    patch_relative = f"fixes/{fixed['finding_id']}.patch.yaml"
    patch_path = root / patch_relative
    patch_path.parent.mkdir(parents=True)
    patch_path.write_bytes(patch_bytes)
    fixed["fix"] = {
        "patch_file": patch_relative,
        "patch_sha256": hashlib.sha256(patch_bytes).hexdigest(),
    }
    ledger_path = root / "adjudications"
    (ledger_path / "articles").mkdir(parents=True)
    write_ledger(ledger_path, manifest, shard)
    return ledger_path, target, before, after


def test_recorded_fix_applies_exact_patch_and_is_idempotent(tmp_path):
    ledger_path, target, _, after = _fixed_p2_ledger(tmp_path)
    finding_id = "AIA-VALID-135096E293C37A15"

    assert apply_recorded_fix(ledger_path, finding_id) == (target, True)
    assert target.read_bytes() == after
    assert apply_recorded_fix(ledger_path, finding_id) == (target, False)


def test_recorded_fix_refuses_unknown_preimage(tmp_path):
    ledger_path, target, _, _ = _fixed_p2_ledger(tmp_path)
    target.write_text("somebody changed this file\n", encoding="utf-8")

    with pytest.raises(ValueError, match="refuses unexpected preimage"):
        apply_recorded_fix(ledger_path, "AIA-VALID-135096E293C37A15")


def test_fixed_finding_must_be_absent_and_patch_must_be_applied(tmp_path):
    ledger_path, target, _, _ = _fixed_p2_ledger(tmp_path)
    apply_recorded_fix(ledger_path, "AIA-VALID-135096E293C37A15")
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    norm.qualifier_spans = [norm.primary_spans[0]]
    refresh_article_fifteen_audit(ledger_path, bundle)

    assert enforce_validity_adjudications(bundle, ledger_path) == (6, 7)

    norm.qualifier_spans = []
    refresh_article_fifteen_audit(ledger_path, bundle)
    with pytest.raises(ValueError, match="fixed are still active"):
        enforce_validity_adjudications(bundle, ledger_path)
