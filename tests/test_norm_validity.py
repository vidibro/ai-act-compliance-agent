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
from aiact.schemas import (
    ActorRole,
    HighRiskRoute,
    NormActor,
    NormTarget,
    TargetKind,
    TemporalRegime,
)
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



def test_all_enforced_adjudications_are_current():
    """The current corpus is governed by the ledger, not hard-coded article snapshots."""
    enforce_validity_adjudications(load_bundle(), LEDGER)


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


def test_logical_expression_gate_requires_detected_conditions_and_exceptions():
    condition_bundle = load_bundle().model_copy(deep=True)
    condition_norm = next(
        item
        for item in condition_bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P4-FEEDBACK-LOOP-RISK-AND-MITIGATION"
    )
    condition_norm.conditions = None
    condition_norm.norm_text = f"{condition_norm.norm_text} where appropriate."
    condition_requirements = {
        (SourceKind.ARTICLE, "15"): {FieldValidation.LOGICAL_EXPRESSION_EVIDENCE},
    }
    condition_findings = audit_norm_validity(
        condition_bundle,
        scope={(SourceKind.ARTICLE, "15")},
        required_field_validations=condition_requirements,
    )
    assert any(
        finding.target == condition_norm.norm_id and finding.rule == "condition_expression_missing"
        for finding in condition_findings
    )

    exception_bundle = load_bundle().model_copy(deep=True)
    exception_norm = next(
        item
        for item in exception_bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A031-P7-CONFIDENTIALITY-AND-SECRECY"
    )
    exception_norm.exceptions = None
    exception_requirements = {
        (SourceKind.ARTICLE, "31"): {FieldValidation.LOGICAL_EXPRESSION_EVIDENCE},
    }
    exception_findings = audit_norm_validity(
        exception_bundle,
        scope={(SourceKind.ARTICLE, "31")},
        required_field_validations=exception_requirements,
    )
    assert any(
        finding.target == exception_norm.norm_id and finding.rule == "exception_expression_missing"
        for finding in exception_findings
    )


@pytest.mark.parametrize("cue", ["if", "where", "when"])
def test_logical_expression_gate_does_not_duplicate_an_except_clause_as_a_condition(cue):
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A031-P7-CONFIDENTIALITY-AND-SECRECY"
    )
    norm.norm_text = f"{norm.norm_text} except {cue} the exception applies."
    assert norm.exceptions is not None
    requirements = {
        (SourceKind.ARTICLE, "31"): {FieldValidation.LOGICAL_EXPRESSION_EVIDENCE},
    }

    findings = audit_norm_validity(
        bundle,
        scope={(SourceKind.ARTICLE, "31")},
        required_field_validations=requirements,
    )

    assert not [
        finding
        for finding in findings
        if finding.target == norm.norm_id and finding.rule == "condition_expression_missing"
    ]


def test_logical_expression_gate_does_not_treat_an_applicability_exclusion_as_its_own_exception():
    bundle = load_bundle()
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A002-P3-MILITARY-EXCLUSION"
    )
    assert norm.exceptions is None
    requirements = {
        (SourceKind.ARTICLE, "2"): {FieldValidation.LOGICAL_EXPRESSION_EVIDENCE},
    }

    findings = audit_norm_validity(
        bundle,
        scope={(SourceKind.ARTICLE, "2")},
        required_field_validations=requirements,
    )

    assert not [
        finding
        for finding in findings
        if finding.target == norm.norm_id and finding.rule == "exception_expression_missing"
    ]


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


def test_conditional_application_routes_must_be_enacted_and_classified():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A015-P2-ENCOURAGE-MEASUREMENT"
    )
    regime = TemporalRegime(
        regime_id="AIA-TEMP-TEST-INVALID-CONDITIONAL-APPLICATION",
        application_routes=[
            {
                "route": HighRiskRoute.ANNEX_III,
                "application_start": "2027-12-02",
            }
        ],
        legal_basis_spans=["AIA-TEXT-A015-P002"],
    )
    bundle.norm_inventory.temporal_regimes.append(regime)
    norm.temporal_regime_id = regime.regime_id

    findings = audit_norm_validity(bundle, scope={(SourceKind.ARTICLE, "15")})

    assert {
        finding.rule
        for finding in findings
        if finding.target == f"{norm.norm_id}:temporal:{regime.regime_id}"
    } == {
        "temporal_application_route_classification_not_in_basis",
        "temporal_application_route_start_not_in_basis",
    }


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

    consultation.conditions = None
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


def test_universal_actor_scope_requires_the_enacted_prohibition_chapeau():
    bundle = load_bundle().model_copy(deep=True)
    norm = next(
        item
        for item in bundle.norm_inventory.norms
        if item.norm_id == "AIA-NORM-A005-P1-A-MANIPULATIVE-TECHNIQUES"
    )
    requirements = {(SourceKind.ARTICLE, "5"): {FieldValidation.ACTOR_EVIDENCE}}

    assert norm.applies_to_all_actors
    assert not [
        finding
        for finding in audit_norm_validity(
            bundle,
            scope={(SourceKind.ARTICLE, "5")},
            required_field_validations=requirements,
        )
        if finding.target == f"{norm.norm_id}:actor:universal"
    ]

    norm.qualifier_spans = []
    findings = audit_norm_validity(
        bundle,
        scope={(SourceKind.ARTICLE, "5")},
        required_field_validations=requirements,
    )

    universal_rules = [
        finding.rule
        for finding in findings
        if finding.target == f"{norm.norm_id}:actor:universal"
    ]
    assert universal_rules == ["universal_actor_scope_not_evidenced"]


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
