"""Stable validity findings become enforceable through reviewed adjudications."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from aiact.norm_loader import load_normative_coverage
from aiact.norm_validity import (
    FieldValidation,
    apply_recorded_fix,
    audit_attestation,
    audit_norm_validity,
    enforce_validity_adjudications,
    load_adjudication_ledger,
)
from aiact.schemas import ActorRole, NormActor, NormTarget, TargetKind, TemporalRegime
from aiact.schemas.norm import ConditionClause, NormRelationKind, SourceKind

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


def refresh_article_fifteen_audit(
    root: Path,
    bundle,
    required_field_validations: dict[tuple[SourceKind, str], set[FieldValidation]] | None = None,
) -> None:
    """A recorded fix changes the audited norm snapshot and therefore requires a fresh audit."""
    shard_path = root / "articles" / "015.yaml"
    shard = yaml.safe_load(shard_path.read_text(encoding="utf-8"))
    shard["audit"] = audit_attestation(
        bundle,
        scope={(SourceKind.ARTICLE, "15")},
        required_field_validations=required_field_validations,
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
    assert enforce_validity_adjudications(bundle, LEDGER) == (79, 83)


def test_article_sixteen_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()

    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "16")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "16")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "16")}
    )
    # Article 16 adds no decisions, but its hash-bound audit proves that the zero is current.
    assert enforce_validity_adjudications(bundle, LEDGER) == (79, 83)


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
        "AIA-VALID-60DB1D9CF0CAF668",
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


def test_article_thirteen_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()
    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "13")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "13")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "13")}
    )


def test_article_fourteen_fixed_condition_is_closed_in_its_own_shard():
    bundle = load_bundle()
    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "14")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "14")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "14")}
    )


def test_article_nineteen_retention_finding_is_recorded_in_its_own_shard():
    bundle = load_bundle()
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "19")})
    assert {finding.finding_id for finding in findings} == {
        "AIA-VALID-89C0BE07A90B8058"
    }
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "19")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "19")}
    )


def test_article_twenty_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()
    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "20")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "20")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "20")}
    )


def test_article_twenty_one_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()
    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "21")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "21")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "21")}
    )


def test_article_twenty_two_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()
    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "22")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "22")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "22")}
    )


def test_article_twenty_three_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()
    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "23")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "23")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "23")}
    )


def test_article_twenty_four_fragment_decisions_and_condition_fix_are_recorded():
    bundle = load_bundle()
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "24")})
    assert {finding.finding_id for finding in findings} == {
        "AIA-VALID-B71C206EA220FC8A",
        "AIA-VALID-946E85650B0AA4EC",
        "AIA-VALID-332B5BFC3925B813",
        "AIA-VALID-F67496A9B784CBD5",
    }
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "24")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "24")}
    )


def test_article_twenty_five_external_law_warning_is_recorded():
    bundle = load_bundle()
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "25")})
    assert {finding.finding_id for finding in findings} == {"AIA-VALID-0AA79DC2690256EC"}
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "25")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "25")}
    )


def test_article_twenty_six_duties_and_incident_fix_are_recorded():
    bundle = load_bundle()
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "26")})
    assert {finding.finding_id for finding in findings} == {
        "AIA-VALID-696BF1694FA2020C",
        "AIA-VALID-0166D938B7FF3472",
        "AIA-VALID-CAAE613AF39C23F1",
        "AIA-VALID-ED05F819E579B6E6",
        "AIA-VALID-53A0A965B90B54FC",
        "AIA-VALID-B0247D44F2A88999",
        "AIA-VALID-EA5E7ECE09FA3EB6",
        "AIA-VALID-495FB7D7B6530BC7",
    }
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "26")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "26")}
    )


def test_article_twenty_seven_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()
    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "27")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "27")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "27")}
    )


def test_article_forty_two_is_closed_with_an_explicit_empty_adjudication_shard():
    bundle = load_bundle()
    assert audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "42")}) == []
    ledger = load_adjudication_ledger(LEDGER)
    assert ledger.audit_by_scope[(SourceKind.ARTICLE, "42")] == audit_attestation(
        bundle, scope={(SourceKind.ARTICLE, "42")}
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


def test_actor_basis_is_checked_deterministically_and_hash_bound():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    norm.actors = [
        NormActor(
            actor_ref=ActorRole.COMMISSION,
            basis_segment_ids=["AIA-TEXT-A015-P002"],
        )
    ]

    assert not [
        finding
        for finding in audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "15")})
        if finding.rule == "actor_basis_does_not_name_actor"
    ]
    with pytest.raises(ValueError, match="audit attestation is stale"):
        enforce_validity_adjudications(bundle, LEDGER)

    norm.actors[0] = NormActor(
        actor_ref=ActorRole.COMMISSION,
        basis_segment_ids=["AIA-TEXT-A015-P009"],
    )
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "15")})

    assert [finding.rule for finding in findings].count("actor_basis_does_not_name_actor") == 1


def test_target_basis_is_checked_deterministically_and_hash_bound():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    norm.targets = [
        NormTarget(
            target_ref="Commission",
            target_kind=TargetKind.ORGANISATION,
            basis_segment_ids=["AIA-TEXT-A015-P002"],
        )
    ]

    assert not [
        finding
        for finding in audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "15")})
        if finding.rule == "target_basis_does_not_name_target"
    ]
    with pytest.raises(ValueError, match="audit attestation is stale"):
        enforce_validity_adjudications(bundle, LEDGER)

    norm.targets[0] = NormTarget(
        target_ref="Commission",
        target_kind=TargetKind.ORGANISATION,
        basis_segment_ids=["AIA-TEXT-A015-P009"],
    )
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "15")})

    assert [finding.rule for finding in findings].count("target_basis_does_not_name_target") == 1


def test_logical_expression_leaf_evidence_is_checked_when_the_field_is_enforced():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P4-FEEDBACK-LOOP-RISK-AND-MITIGATION"
    )
    assert norm.conditions is not None
    norm.conditions.operands[0] = ConditionClause(
        text="a condition that is not in the cited legal text",
        basis_segment_ids=["AIA-TEXT-A015-P006"],
    )
    requirements = {
        (SourceKind.ARTICLE, "15"): {FieldValidation.LOGICAL_EXPRESSION_EVIDENCE},
    }

    findings = audit_norm_validity(
        bundle,
        scope={(SourceKind.ARTICLE, "15")},
        required_field_validations=requirements,
    )

    target = (
        "AIA-NORM-A015-P4-FEEDBACK-LOOP-RISK-AND-MITIGATION:"
        "conditions:0:AIA-TEXT-A015-P006"
    )
    assert any(
        finding.target == target
        and finding.rule == "logical_expression_basis_does_not_contain_text"
        for finding in findings
    )


def test_logical_expression_unknown_basis_is_reported_when_the_field_is_enforced():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P4-FEEDBACK-LOOP-RISK-AND-MITIGATION"
    )
    assert norm.conditions is not None
    norm.conditions.operands[0] = ConditionClause(
        text="a condition with a missing cited segment",
        basis_segment_ids=["AIA-TEXT-A015-P999"],
    )
    requirements = {
        (SourceKind.ARTICLE, "15"): {FieldValidation.LOGICAL_EXPRESSION_EVIDENCE},
    }

    findings = audit_norm_validity(
        bundle,
        scope={(SourceKind.ARTICLE, "15")},
        required_field_validations=requirements,
    )

    target = (
        "AIA-NORM-A015-P4-FEEDBACK-LOOP-RISK-AND-MITIGATION:"
        "conditions:0:AIA-TEXT-A015-P999"
    )
    assert any(
        finding.target == target
        and finding.rule == "logical_expression_basis_segment_unknown"
        for finding in findings
    )


def test_temporal_assignment_needs_source_bound_adjudication_when_its_date_is_unproven(tmp_path):
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    regime = TemporalRegime(
        regime_id="AIA-TEMP-TEST-UNPROVEN",
        application_start="2030-01-02",
        legal_basis_spans=["AIA-TEXT-A015-P002"],
    )
    bundle.norm_inventory.temporal_regimes.append(regime)
    norm.temporal_regime_id = regime.regime_id

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "15")})
    assert [finding.rule for finding in findings].count(
        "temporal_application_start_not_in_basis"
    ) == 1

    root, manifest, shard = copied_ledger(tmp_path)
    write_ledger(root, manifest, shard)
    refresh_article_fifteen_audit(root, bundle)
    with pytest.raises(ValueError, match="findings lack adjudication"):
        enforce_validity_adjudications(bundle, root)


def test_temporal_deadline_must_be_in_its_legal_basis():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    regime = TemporalRegime(
        regime_id="AIA-TEMP-TEST-UNPROVEN-DEADLINE",
        deadline="2030-01-02",
        legal_basis_spans=["AIA-TEXT-A015-P002"],
    )
    bundle.norm_inventory.temporal_regimes.append(regime)
    norm.temporal_regime_id = regime.regime_id

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "15")})

    assert [finding.rule for finding in findings].count("temporal_deadline_not_in_basis") == 1


def test_temporal_gate_requires_a_regime_for_a_relative_deadline():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    norm.norm_text = "The provider shall act within 15 calendar days of receipt."
    norm.action = "act within 15 calendar days of receipt"
    requirements = {
        (SourceKind.ARTICLE, "15"): {FieldValidation.TEMPORAL_REGIME},
    }

    findings = audit_norm_validity(
        bundle,
        scope={(SourceKind.ARTICLE, "15")},
        required_field_validations=requirements,
    )

    assert [finding.rule for finding in findings].count("temporal_deadline_regime_missing") == 1


def test_temporal_gate_requires_a_matching_relative_deadline():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    norm.norm_text = "The provider shall act within 15 calendar days of receipt."
    norm.action = "act within 15 calendar days of receipt"
    regime = TemporalRegime(
        regime_id="AIA-TEMP-TEST-APPLICATION-ONLY",
        application_start="2030-01-02",
        legal_basis_spans=["AIA-TEXT-A015-P002"],
    )
    bundle.norm_inventory.temporal_regimes.append(regime)
    norm.temporal_regime_id = regime.regime_id
    requirements = {
        (SourceKind.ARTICLE, "15"): {FieldValidation.TEMPORAL_REGIME},
    }

    findings = audit_norm_validity(
        bundle,
        scope={(SourceKind.ARTICLE, "15")},
        required_field_validations=requirements,
    )

    assert [finding.rule for finding in findings].count("temporal_relative_deadline_missing") == 1


def test_article_forty_six_relative_deadline_is_source_backed():
    bundle = load_bundle()

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "46")})

    assert not [
        finding
        for finding in findings
        if finding.rule
        in {"temporal_relative_deadline_not_in_basis", "temporal_deadline_trigger_not_in_basis"}
    ]


def test_relative_deadline_trigger_must_be_in_its_legal_basis():
    bundle = load_bundle().model_copy(deep=True)
    regime = next(
        item
        for item in bundle.norm_inventory.temporal_regimes
        if item.regime_id == "AIA-TEMP-A046-P4-OBJECTION-PERIOD"
    )
    assert regime.relative_deadline is not None
    regime.relative_deadline.trigger = "receipt of an unrelated notification"

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "46")})

    assert [finding.rule for finding in findings].count(
        "temporal_deadline_trigger_not_in_basis"
    ) == 1


def test_a_norm_with_multiple_deadline_constraints_is_a_structural_finding():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    norm.norm_text = (
        "The provider shall report immediately and not later than 15 days after awareness."
    )
    norm.action = "report immediately and not later than 15 days after awareness"

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "15")})

    assert [finding.rule for finding in findings].count(
        "multiple_deadline_constraints_in_norm"
    ) == 1


def test_article_seventy_three_splits_each_cumulative_deadline_into_atomic_norms():
    bundle = load_bundle()
    norm_ids = {norm.norm_id for norm in bundle.norm_inventory.norms}

    assert {
        "AIA-NORM-A073-P2-REPORT-IMMEDIATELY",
        "AIA-NORM-A073-P2-REPORT-NO-LATER-THAN-FIFTEEN-DAYS",
        "AIA-NORM-A073-P3-REPORT-IMMEDIATELY",
        "AIA-NORM-A073-P3-REPORT-NO-LATER-THAN-TWO-DAYS",
        "AIA-NORM-A073-P4-REPORT-IMMEDIATELY",
        "AIA-NORM-A073-P4-REPORT-NO-LATER-THAN-TEN-DAYS",
    } <= norm_ids
    assert "AIA-NORM-A073-P2-DEFAULT-REPORTING-DEADLINE" not in norm_ids
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "73")})
    assert not [
        finding for finding in findings if finding.rule == "multiple_deadline_constraints_in_norm"
    ]
    assert not [
        finding
        for finding in findings
        if finding.rule
        in {
            "temporal_relative_deadline_not_in_basis",
            "temporal_deadline_trigger_not_in_basis",
        }
    ]


def test_article_five_splits_the_urgent_authorisation_timing_constraints():
    bundle = load_bundle()
    norm_ids = {norm.norm_id for norm in bundle.norm_inventory.norms}

    assert {
        "AIA-NORM-A005-P3-URGENT-USE",
        "AIA-NORM-A005-P3-REQUEST-URGENT-AUTHORISATION-WITHOUT-UNDUE-DELAY",
        "AIA-NORM-A005-P3-REQUEST-URGENT-AUTHORISATION-WITHIN-TWENTY-FOUR-HOURS",
    } <= norm_ids
    relation = next(
        item
        for item in bundle.norm_inventory.relations
        if item.relation_id
        == "AIA-REL-A005-P3-URGENT-USE-CONDITIONAL-ON-AUTHORISATION-REQUEST-DEADLINES"
    )
    assert relation.source_norm_id == "AIA-NORM-A005-P3-URGENT-USE"
    assert relation.target_norm_ids == [
        "AIA-NORM-A005-P3-REQUEST-URGENT-AUTHORISATION-WITHOUT-UNDUE-DELAY",
        "AIA-NORM-A005-P3-REQUEST-URGENT-AUTHORISATION-WITHIN-TWENTY-FOUR-HOURS",
    ]
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "5")})
    assert not [
        finding
        for finding in findings
        if finding.target == "AIA-NORM-A005-P3-URGENT-USE"
        and finding.rule == "multiple_deadline_constraints_in_norm"
    ]


def test_article_seventy_five_splits_its_cumulative_information_deadlines():
    bundle = load_bundle()
    norm_ids = {norm.norm_id for norm in bundle.norm_inventory.norms}

    assert {
        "AIA-NORM-A075-P3-SUPPLY-INFORMATION-WITHOUT-DELAY",
        "AIA-NORM-A075-P3-SUPPLY-INFORMATION-WITHIN-THIRTY-DAYS",
    } <= norm_ids
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "75")})
    assert not [
        finding
        for finding in findings
        if finding.rule == "multiple_deadline_constraints_in_norm"
    ]


def test_article_eighty_one_objection_windows_are_conditions_not_deadlines():
    bundle = load_bundle()
    consultation = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A081-P1-CONSULT-AND-EVALUATE"
    )
    assert consultation.temporal_regime_id == "AIA-TEMP-A081-P1-CONSULT-WITHOUT-UNDUE-DELAY"
    assert {
        "AIA-NORM-A081-P1-DECIDE-JUSTIFICATION-WITHIN-SIX-MONTHS",
        "AIA-NORM-A081-P1-DECIDE-JUSTIFICATION-WITHIN-SIXTY-DAYS",
    } <= {item.norm_id for item in bundle.norm_inventory.norms}
    assert bundle.norm_inventory.target_norm_ids_for(
        "AIA-NORM-A081-P1-DECIDE-JUSTIFICATION-WITHIN-SIX-MONTHS",
        NormRelationKind.ALTERNATIVE_NORMS,
    ) == ["AIA-NORM-A081-P1-DECIDE-JUSTIFICATION-WITHIN-SIXTY-DAYS"]

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "81")})
    assert not [
        finding
        for finding in findings
        if finding.target == consultation.norm_id
        and finding.rule == "multiple_deadline_constraints_in_norm"
    ]

    consultation.conditions = []
    findings_without_conditions = audit_norm_validity(
        bundle, scope={(SourceKind.ARTICLE, "81")}
    )
    assert any(
        finding.target == consultation.norm_id
        and finding.rule == "multiple_deadline_constraints_in_norm"
        for finding in findings_without_conditions
    )


def test_article_ninety_nine_splits_initial_and_amendment_notifications():
    bundle = load_bundle()
    norm_ids = {norm.norm_id for norm in bundle.norm_inventory.norms}

    assert {
        "AIA-NORM-A099-P2-NOTIFY-PENALTY-RULES-WITHOUT-DELAY",
        "AIA-NORM-A099-P2-NOTIFY-PENALTY-RULES-BY-APPLICATION-DATE",
        "AIA-NORM-A099-P2-NOTIFY-PENALTY-AMENDMENT-WITHOUT-DELAY",
    } <= norm_ids
    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "99")})
    assert not [
        finding
        for finding in findings
        if finding.rule == "multiple_deadline_constraints_in_norm"
    ]


def test_field_validation_gate_requires_complete_actor_evidence_for_an_article(tmp_path):
    bundle = load_bundle()
    requirements = {
        (SourceKind.ARTICLE, "15"): {FieldValidation.ACTOR_EVIDENCE},
    }

    findings = audit_norm_validity(
        bundle,
        scope={(SourceKind.ARTICLE, "15")},
        required_field_validations=requirements,
    )
    assert any(finding.rule == "actor_basis_missing" for finding in findings)

    root, manifest, shard = copied_ledger(tmp_path)
    next(
        scope for scope in manifest["enforced_scope"] if scope["document"] == "15"
    )["required_field_validations"] = ["actor_evidence"]
    shard["source"]["required_field_validations"] = ["actor_evidence"]
    write_ledger(root, manifest, shard)
    refresh_article_fifteen_audit(root, bundle, requirements)

    with pytest.raises(ValueError, match="findings lack adjudication"):
        enforce_validity_adjudications(bundle, root)


def test_target_evidence_gate_requires_a_basis_for_every_listed_target():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    norm.targets = [NormTarget(target_ref="Commission", target_kind=TargetKind.ORGANISATION)]
    requirements = {
        (SourceKind.ARTICLE, "15"): {FieldValidation.TARGET_EVIDENCE},
    }

    findings = audit_norm_validity(
        bundle,
        scope={(SourceKind.ARTICLE, "15")},
        required_field_validations=requirements,
    )

    assert [finding.rule for finding in findings].count("target_basis_missing") == 1


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
    (root / "articles" / "054.yaml").write_text(
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
    manifest["enforced_scope"].append({"kind": "article", "document": "54"})
    manifest["shards"].append({"kind": "article", "document": "54", "file": "articles/054.yaml"})
    write_ledger(root, manifest, shard)
    duplicate = {**shard, "source": {"kind": "article", "document": "54"}}
    (root / "articles" / "054.yaml").write_text(
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
