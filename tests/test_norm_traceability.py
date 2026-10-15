"""Norm-to-rule traceability for the Article 15 pilot, proved without a model.

Four links, each held here by a deterministic test: every enforced Article 15 compliance norm is an
explicit criterion of AIA-RULE-HR-A15; each criterion resolves to the canonical norm and is
materialised from it; each is judged and reported on its own; and the rule passes only when every
mandatory criterion does. A stub judge stands in for the model — whether a real model judges the
fixture well is an evaluation question, not what these tests prove.
"""

from __future__ import annotations

import dataclasses
import json
import sys
import types
from datetime import date
from pathlib import Path

import pytest
import yaml

from aiact import scope_notes
from aiact.classify import ScriptedBrain
from aiact.gap.criteria import settle
from aiact.gap.graph import analyse
from aiact.gap.judge import Judgement, LLMJudge
from aiact.norm_builder import NormBuilderPaths, run_builder
from aiact.norm_loader import load_normative_coverage
from aiact.norm_traceability import traceability_errors
from aiact.norm_validity import load_adjudication_ledger
from aiact.policy_loader import load_policy_spec
from aiact.report_loader import load_compliance_report
from aiact.reporting import render_report
from aiact.retrieval.chunking import Chunk
from aiact.retrieval.store import Hit
from aiact.schemas.classification import (
    ClassificationEvidence,
    ClassificationResult,
    UseCaseClassification,
)
from aiact.schemas.enums import ActorRole, AnnexIIIArea, RiskClass, Verdict
from aiact.schemas.norm import ImplementationMode, NormRelationKind, SourceKind
from aiact.schemas.policy import LegalSource, PolicyRule, PolicyRuleset, RuleCriterion
from aiact.schemas.report import (
    ComplianceReport,
    CriterionFinding,
    Finding,
    aggregate_criteria,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data" / "policy"
COVERAGE = POLICY / "normative-coverage" / "2026-07-27"
LEDGER = COVERAGE / "adjudications"
SPEC = POLICY / "spec.yaml"
FIXTURE = ROOT / "data" / "golden_set" / "criteria" / "AIA-NORM-A015-P5-MODEL-FLAWS__omitted.md"

RULE = "AIA-RULE-HR-A15"
ARTICLE_10_RULE = "AIA-RULE-HR-A10"
ARTICLE_17_RULE = "AIA-RULE-PO-A17"
MODEL_FLAWS = "AIA-NORM-A015-P5-MODEL-FLAWS"
SECTION_2_ALLOCATION = "AIA-REL-A016-A-ALLOCATES-SECTION-2"
SIBLING_THREATS = {
    "AIA-NORM-A015-P5-DATA-POISONING": "Data poisoning",
    "AIA-NORM-A015-P5-MODEL-POISONING": "Model poisoning",
    "AIA-NORM-A015-P5-ADVERSARIAL-ATTACKS": "Adversarial examples and model evasion",
    "AIA-NORM-A015-P5-CONFIDENTIALITY-ATTACKS": "Confidentiality attacks",
}
MODEL_FLAWS_REASON = "Nothing prevents, detects, responds to, resolves or controls model flaws."


@pytest.fixture(scope="module")
def bundle():
    return load_normative_coverage(
        COVERAGE / "text-review",
        COVERAGE / "norms",
        articles_root=POLICY / "articles",
        annexes_root=POLICY / "annexes",
        guidance_root=POLICY / "guidance",
    )


@pytest.fixture(scope="module")
def spec() -> PolicyRuleset:
    return load_policy_spec(SPEC, POLICY / "articles", norms_root=COVERAGE / "norms")


def a15(spec: PolicyRuleset) -> PolicyRule:
    return next(rule for rule in spec.rules if rule.rule_id == RULE)


def a10(spec: PolicyRuleset) -> PolicyRule:
    return next(rule for rule in spec.rules if rule.rule_id == ARTICLE_10_RULE)


def a17(spec: PolicyRuleset) -> PolicyRule:
    return next(rule for rule in spec.rules if rule.rule_id == ARTICLE_17_RULE)


def with_criteria(spec: PolicyRuleset, criteria: list[RuleCriterion]) -> PolicyRuleset:
    """The spec with AIA-RULE-HR-A15's criteria replaced, unvalidated, to test the checker
    itself."""
    rules = [
        rule.model_copy(update={"criteria": criteria}) if rule.rule_id == RULE else rule
        for rule in spec.rules
    ]
    return spec.model_copy(update={"rules": rules})


# --- the mapping, both directions ----------------------------------------------------------------
def test_every_article_15_norm_implemented_by_the_rule_is_exactly_one_criterion(bundle, spec):
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    implemented = {
        norm.norm_id
        for norm in bundle.norm_inventory.norms
        if segments[norm.primary_spans[0]].source.document == "15"
        and segments[norm.primary_spans[0]].source.kind is SourceKind.ARTICLE
        and norm.implementation_mode is ImplementationMode.COMPLIANCE_RULE
        and RULE in norm.implementation_refs
    }
    listed = [criterion.norm_id for criterion in a15(spec).criteria]

    assert len(implemented) == 12
    assert len(listed) == len(set(listed))
    assert set(listed) == implemented


def test_every_criterion_resolves_to_one_norm_that_points_back(bundle, spec):
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    for criterion in a15(spec).criteria:
        assert RULE in norms[criterion.norm_id].implementation_refs
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_six_separates_document_and_process_duties(bundle, spec):
    """Each Article 6(4) provider duty has one deterministic, distinct implementation path."""
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    expected = {
        "AIA-NORM-A006-P4-DOCUMENT-ASSESSMENT": "AIA-RULE-NHR-A06-4",
        "AIA-NORM-A006-P4-REGISTER-SYSTEM": "AIA-RULE-NHR-A06-4-REGISTER",
        "AIA-NORM-A006-P4-PROVIDE-ASSESSMENT": "AIA-RULE-NHR-A06-4-PROVIDE-ASSESSMENT",
    }
    assert {norm_id: norms[norm_id].implementation_refs for norm_id in expected} == {
        norm_id: [rule_id] for norm_id, rule_id in expected.items()
    }
    rules = {rule.rule_id: rule for rule in spec.rules}
    assert rules["AIA-RULE-NHR-A06-4"].criteria == []
    assert rules["AIA-RULE-NHR-A06-4-PROVIDE-ASSESSMENT"].criteria == []
    # Article 49(2) writes the registration duty out again, so the rule names both provisions.
    assert [criterion.norm_id for criterion in rules["AIA-RULE-NHR-A06-4-REGISTER"].criteria] == [
        "AIA-NORM-A006-P4-REGISTER-SYSTEM",
        "AIA-NORM-A049-P2-PROVIDER-REGISTER-NON-HIGH-RISK",
    ]
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_seven_is_recorded_as_commission_amendment_law_not_product_rules(bundle, spec):
    """Article 7 may change Annex III later; it creates no live supported-operator duty."""
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    article_seven = [
        norm
        for norm in bundle.norm_inventory.norms
        if segments[norm.primary_spans[0]].source.kind is SourceKind.ARTICLE
        and segments[norm.primary_spans[0]].source.document == "7"
    ]
    assert {norm.implementation_mode for norm in article_seven} == {
        ImplementationMode.NONE_REQUIRED
    }
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_eight_materialises_the_sectoral_integration_permission(bundle, spec):
    """An optional integration route must not disappear into its Article 8(2) obligation rule."""
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    permission_id = "AIA-NORM-A008-P2-INTEGRATE-COMPLIANCE-PROCESSES"
    assert norms[permission_id].implementation_mode is ImplementationMode.REPORT_ONLY
    report_norm = next(item for item in spec.report_norms if item.norm_id == permission_id)
    assert report_norm.activation_rule_ids == ["AIA-RULE-PO-A08-2"]
    assert norms["AIA-NORM-A008-P2-ENSURE-PRODUCT-COMPLIANCE"].implementation_mode is (
        ImplementationMode.COMPLIANCE_RULE
    )
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_nine_separates_its_eighteen_duties_from_scope_and_permission_entries(bundle, spec):
    rule = next(rule for rule in spec.rules if rule.rule_id == "AIA-RULE-HR-A09")
    assert len(rule.criteria) == 19

    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    assert (
        norms["AIA-NORM-A009-P3-MITIGABLE-RISK-SCOPE"].implementation_mode
        is ImplementationMode.REPORT_ONLY
    )
    assert (
        norms["AIA-NORM-A009-P7-REAL-WORLD-TESTING"].implementation_mode
        is ImplementationMode.REPORT_ONLY
    )
    assert (
        norms["AIA-NORM-A009-P10-INTEGRATE-RISK-PROCESSES"].implementation_mode
        is ImplementationMode.REPORT_ONLY
    )
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_eleven_separates_the_simplified_documentation_permission(bundle, spec):
    rule = next(rule for rule in spec.rules if rule.rule_id == "AIA-RULE-HR-A11")
    assert [criterion.norm_id for criterion in rule.criteria] == [
        "AIA-NORM-A011-P1-DRAW",
        "AIA-NORM-A011-P1-DEMONSTRATE",
        "AIA-NORM-A011-P1-ANNEX-IV",
        "AIA-NORM-A011-P1-USE-FORM",
    ]
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    assert norms["AIA-NORM-A011-P1-SIMPLIFY"].implementation_mode is ImplementationMode.REPORT_ONLY
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_twelve_maps_each_general_logging_duty_to_a_criterion(bundle, spec):
    rule = next(rule for rule in spec.rules if rule.rule_id == "AIA-RULE-HR-A12")
    assert [criterion.norm_id for criterion in rule.criteria] == [
        "AIA-NORM-A012-P1-AUTOMATIC-LOGGING",
        "AIA-NORM-A012-P2-A-RISK-MODIFICATION-EVENTS",
        "AIA-NORM-A012-P2-B-POST-MARKET-EVENTS",
        "AIA-NORM-A012-P2-C-OPERATION-MONITORING-EVENTS",
    ]
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_thirteen_maps_transparency_and_instruction_contents_separately(bundle, spec):
    rules = {rule.rule_id: rule for rule in spec.rules}
    assert len(rules["AIA-RULE-HR-A13"].criteria) == 3
    assert len(rules["AIA-RULE-HR-A13-3"].criteria) == 13
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_fourteen_separates_oversight_duties_from_its_scope_exception(bundle, spec):
    rule = next(rule for rule in spec.rules if rule.rule_id == "AIA-RULE-HR-A14")
    assert len(rule.criteria) == 9
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    assert (
        norms["AIA-NORM-A014-P5-DISPROPORTIONATE-EXCEPTION"].implementation_mode
        is ImplementationMode.REPORT_ONLY
    )
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_nineteen_maps_each_log_retention_duty_to_a_criterion(bundle, spec):
    rules = {rule.rule_id: rule for rule in spec.rules}
    assert len(rules["AIA-RULE-PO-A19"].criteria) == 2
    assert [criterion.norm_id for criterion in rules["AIA-RULE-PO-A19-2"].criteria] == [
        "AIA-NORM-A019-P2-FINANCIAL-DOCUMENTATION"
    ]
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_twenty_separates_corrective_response_from_risk_investigation(bundle, spec):
    rules = {rule.rule_id: rule for rule in spec.rules}
    assert len(rules["AIA-RULE-PO-A20"].criteria) == 2
    assert rules["AIA-RULE-PO-A20-2"].criteria == []
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_twenty_one_reports_receiving_authority_confidentiality(bundle, spec):
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    norm_id = "AIA-NORM-A021-P3-CONFIDENTIALITY"
    assert norms[norm_id].implementation_mode is ImplementationMode.REPORT_ONLY
    report_norm = next(item for item in spec.report_norms if item.norm_id == norm_id)
    assert report_norm.activation_rule_ids == ["AIA-RULE-PO-A21", "AIA-RULE-PO-A21-2"]
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_twenty_two_separates_mandate_content_from_representative_tasks(bundle, spec):
    rules = {rule.rule_id: rule for rule in spec.rules}
    assert [criterion.norm_id for criterion in rules["AIA-RULE-PO-A22"].criteria] == [
        "AIA-NORM-A022-P1-APPOINT-REPRESENTATIVE",
        "AIA-NORM-A022-P2-ENABLE-REPRESENTATIVE",
        "AIA-NORM-A022-P3-MANDATE-EMPOWER-TASKS",
    ]
    representative_criteria = [criterion.norm_id for criterion in rules["AIA-RULE-AR-A22"].criteria]
    assert "AIA-NORM-A022-P3-MANDATE-EMPOWER-TASKS" not in representative_criteria
    assert len(representative_criteria) == 12
    # Article 49(1) gives the representative its own EU-database registration duty.
    assert representative_criteria[-1] == "AIA-NORM-A049-P1-REPRESENTATIVE-REGISTER"
    task_set = bundle.norm_inventory.target_norm_ids_for(
        "AIA-NORM-A022-P3-MANDATE-EMPOWER-TASKS", NormRelationKind.RELIES_ON_NORMS
    )
    assert task_set == [
        "AIA-NORM-A022-P3-A-VERIFY",
        "AIA-NORM-A022-P3-B-KEEP-RECORDS",
        "AIA-NORM-A022-P3-C-PROVIDE-CONFORMITY-INFORMATION",
        "AIA-NORM-A022-P3-C-PROVIDE-LOG-ACCESS",
        "AIA-NORM-A022-P3-D-COOPERATE",
        "AIA-NORM-A022-P3-E-REGISTER",
        "AIA-NORM-A022-P3-E-ENSURE-REGISTRATION-CORRECT",
    ]
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_twenty_three_makes_each_importer_duty_a_criterion(bundle, spec):
    rule = next(rule for rule in spec.rules if rule.rule_id == "AIA-RULE-IM-A23")
    assert len(rule.criteria) == 12
    assert {criterion.norm_id for criterion in rule.criteria} == {
        norm.norm_id
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A023-")
    }
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_twenty_four_makes_each_distributor_duty_a_criterion(bundle, spec):
    rule = next(rule for rule in spec.rules if rule.rule_id == "AIA-RULE-DI-A24")
    assert len(rule.criteria) == 10
    assert {criterion.norm_id for criterion in rule.criteria} == {
        norm.norm_id
        for norm in bundle.norm_inventory.norms
        if norm.norm_id.startswith("AIA-NORM-A024-")
    }
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_twenty_five_reports_external_law_constraint_from_role_transfer(bundle, spec):
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    protection_id = "AIA-NORM-A025-P5-PROTECT-RIGHTS-AND-SECRETS"
    protection = norms[protection_id]
    assert protection.implementation_mode is ImplementationMode.REPORT_ONLY
    assert protection.implementation_refs == ["AIA-RULE-IP-A25-2"]
    assert protection.verification_mode.value == "reported_conditionally"
    report_norm = next(item for item in spec.report_norms if item.norm_id == protection_id)
    assert report_norm.activation_rule_ids == ["AIA-RULE-IP-A25-2"]
    relation = next(
        relation
        for relation in bundle.norm_inventory.relations
        if relation.source_norm_id == protection_id
        and relation.kind is NormRelationKind.SUBJECT_TO_EXTERNAL_REQUIREMENTS
    )
    assert relation.external_requirements == [
        "applicable Union and national intellectual-property, confidentiality, and trade-secret law"
    ]
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_twenty_six_splits_distinct_deployer_duties_into_criteria(bundle, spec):
    rules = {rule.rule_id: rule for rule in spec.rules}
    expected = {
        "AIA-RULE-DP-A26": 7,
        "AIA-RULE-DP-A26-6": 1,
        "AIA-RULE-DP-A26-7": 1,
        "AIA-RULE-DP-A26-8": 1,
        "AIA-RULE-DP-A26-8-UNREGISTERED-PROHIBITION": 1,
        "AIA-RULE-DP-A26-8-UNREGISTERED-NOTICE": 1,
        "AIA-RULE-DP-A26-9": 1,
        "AIA-RULE-DP-A26-10": 6,
        "AIA-RULE-DP-A26-10-LAW-ENFORCEMENT": 2,
        "AIA-RULE-DP-A26-11": 1,
        "AIA-RULE-DP-A26-12": 1,
    }
    assert {rule_id: len(rules[rule_id].criteria) for rule_id in expected} == expected

    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    for norm_id in (
        "AIA-NORM-A026-P5-FALLBACK",
        "AIA-NORM-A026-P5-SENSITIVE",
        "AIA-NORM-A026-P5-FINANCIAL",
        "AIA-NORM-A026-P7-FOLLOW-WORKER-INFORMATION-RULES",
        "AIA-NORM-A026-P10-PRESERVE-DIRECTIVE-2016-680",
        "AIA-NORM-A026-P10-PRESERVE-BIOMETRIC-DATA-LAW",
        "AIA-NORM-A026-P10-PRESERVE-SUPERVISORY-POWERS",
    ):
        assert norms[norm_id].implementation_mode is ImplementationMode.REPORT_ONLY
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_twenty_seven_keeps_fria_duties_separate_from_permissions(bundle, spec):
    rules = {rule.rule_id: rule for rule in spec.rules}
    assert {
        rule_id: [criterion.norm_id for criterion in rules[rule_id].criteria]
        for rule_id in ("AIA-RULE-DP-A27", "AIA-RULE-DP-A27-2", "AIA-RULE-DP-A27-3")
    } == {
        "AIA-RULE-DP-A27": ["AIA-NORM-A027-P1-PERFORM-FRIA"],
        "AIA-RULE-DP-A27-2": ["AIA-NORM-A027-P2-UPDATE"],
        "AIA-RULE-DP-A27-3": ["AIA-NORM-A027-P3-NOTIFY-RESULTS"],
    }
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    for norm_id in (
        "AIA-NORM-A027-P2-FIRST-USE",
        "AIA-NORM-A027-P2-RELY-ON-PREVIOUS-ASSESSMENT",
        "AIA-NORM-A027-P3-ARTICLE-46-EXEMPTION",
        "AIA-NORM-A027-P4-INCORPORATE-DPIA",
    ):
        assert norms[norm_id].implementation_mode is ImplementationMode.REPORT_ONLY
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_forty_two_reports_presumptions_against_the_affected_rules(bundle, spec):
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    expected_activation = {
        "AIA-NORM-A042-P1-REPRESENTATIVE-DATA-PRESUMPTION": ["AIA-RULE-HR-A10"],
        "AIA-NORM-A042-P2-CYBERSECURITY-CERTIFICATE-PRESUMPTION": ["AIA-RULE-HR-A15"],
        "AIA-NORM-A042-P3-CYBER-RESILIENCE-DEEMING": ["AIA-RULE-HR-A15"],
    }
    projected = {item.norm_id: item for item in spec.report_norms}
    for norm_id, rule_ids in expected_activation.items():
        assert norms[norm_id].implementation_mode is ImplementationMode.REPORT_ONLY
        assert projected[norm_id].activation_rule_ids == rule_ids
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_ten_has_thirteen_provider_obligation_criteria_and_reachable_carried_permission(
    bundle, spec
):
    """Article 10(5) reaches Article 4a's report route without becoming a false pass/fail duty."""
    listed = [criterion.norm_id for criterion in a10(spec).criteria]
    assert len(listed) == 13
    assert all(norm_id.startswith("AIA-NORM-A010-") for norm_id in listed)

    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    special_data = norms["AIA-NORM-A010-P5-SPECIAL-CATEGORY-PROCESSING"]
    assert special_data.implementation_mode is ImplementationMode.CARRIED_BY_OTHER_NORM
    carrier_id = bundle.norm_inventory.target_norm_ids_for(
        special_data.norm_id, NormRelationKind.CARRIED_BY_NORMS
    )
    assert carrier_id == ["AIA-NORM-A004A-P1-HIGH-RISK-BIAS-DATA-PROCESSING"]
    assert norms[carrier_id[0]].implementation_mode is ImplementationMode.REPORT_ONLY
    testing_data_limit = next(
        norm for norm in spec.report_norms if norm.norm_id == "AIA-NORM-A010-P6-TESTING-DATA-ONLY"
    )
    assert testing_data_limit.kind.value == "applicability"
    assert testing_data_limit.activation_rule_ids == [ARTICLE_10_RULE]
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_five_public_authority_norms_are_reported_without_becoming_report_actors(
    bundle, spec
):
    statements = [
        norm
        for norm in spec.report_norms
        if norm.norm_id.startswith("AIA-NORM-A005-P2-")
        or norm.norm_id.startswith("AIA-NORM-A005-P3-")
        or norm.norm_id.startswith("AIA-NORM-A005-P4-")
    ]
    assert len(statements) == 16
    assert all(
        "public_authority" in {category.value for category in norm.actor_categories}
        for norm in statements
    )
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_model_flaws_is_materialised_with_its_full_action_and_condition(spec):
    criterion = next(c for c in a15(spec).criteria if c.norm_id == MODEL_FLAWS)

    assert criterion.norm_text == "model flaws"
    assert criterion.actors == ["provider"]
    assert criterion.mandatory
    for verb in ("prevent", "detect", "respond to", "resolve", "control"):
        assert verb in criterion.action
    assert "model flaws" in criterion.action
    assert criterion.conditions == ["where appropriate"]
    assert criterion.source_spans == ["AIA-TEXT-A015-P009", "AIA-TEXT-A016-P001"]


def test_permissions_are_materialised_separately_from_obligation_criteria(spec):
    redundancy = next(
        norm for norm in spec.report_norms if norm.norm_id == "AIA-NORM-A015-P4-REDUNDANCY"
    )
    assert redundancy.kind.value == "permission"
    assert redundancy.activation_rule_ids == [RULE]
    assert redundancy.norm_id not in {criterion.norm_id for criterion in a15(spec).criteria}


def test_missing_report_norm_fails_the_bidirectional_strict_check(bundle, spec):
    broken = spec.model_copy(
        update={
            "report_norms": [
                norm for norm in spec.report_norms if norm.norm_id != "AIA-NORM-A015-P4-REDUNDANCY"
            ]
        }
    )
    assert "AIA-NORM-A015-P4-REDUNDANCY has no materialised report norm" in traceability_errors(
        bundle, broken, LEDGER
    )


def test_enforced_norm_cannot_keep_an_undecided_implementation_mode(bundle, spec):
    norm_id = "AIA-NORM-A015-P5-MODEL-FLAWS"
    broken = bundle.model_copy(deep=True)
    broken.norm_inventory.norms = [
        norm.model_copy(update={"implementation_mode": ImplementationMode.MISSING})
        if norm.norm_id == norm_id
        else norm
        for norm in broken.norm_inventory.norms
    ]

    assert (
        f"{norm_id} is in enforced scope but implementation_mode is missing"
    ) in traceability_errors(broken, spec, LEDGER)


def test_in_scope_permission_cannot_be_hidden_in_a_compliance_rule(bundle, spec):
    """Permissions and legal effects have one mandatory, report-only implementation path."""
    norm_id = "AIA-NORM-A015-P4-REDUNDANCY"
    broken = bundle.model_copy(deep=True)
    broken.norm_inventory.norms = [
        norm.model_copy(update={"implementation_mode": ImplementationMode.COMPLIANCE_RULE})
        if norm.norm_id == norm_id
        else norm
        for norm in broken.norm_inventory.norms
    ]

    assert (
        f"{norm_id} is permission in enforced scope but implementation_mode is compliance_rule; "
        "permissions and legal consequences must be report_only or carried_by_other_norm"
    ) in traceability_errors(broken, spec, LEDGER)


def test_a_rule_no_norm_names_fails_the_build(bundle, spec):
    """A rule fires a verdict, so a rule with no criteria that no norm names has no enacted text
    behind it. Report-only links count as naming: the Article 5(2) to (4) deployer rules are named
    only by report-only norms and are not flagged."""
    orphan = a15(spec).model_copy(update={"rule_id": "AIA-RULE-HR-A15-ORPHAN", "criteria": []})
    widened = spec.model_copy(update={"rules": [*spec.rules, orphan]})

    errors = traceability_errors(bundle, widened, LEDGER)

    assert "AIA-RULE-HR-A15-ORPHAN is named by no norm" in errors
    assert not any(e.startswith("AIA-RULE-DP-A05-") for e in errors)


@pytest.mark.parametrize(
    ("norm_id", "kind"),
    [
        ("AIA-NORM-A055-P2-RELY-ON-CODES", "permission"),
        ("AIA-NORM-A055-P2-HARMONISED-STANDARD-PRESUMPTION", "legal_consequence"),
    ],
)
def test_an_operator_route_marked_as_needing_nothing_fails_the_build(bundle, spec, norm_id, kind):
    """A permission, right or legal effect of a supported operator is something the report owes
    its reader. Marking one `none_required` would drop it from every report, so the build refuses
    it."""
    changed = bundle.model_copy(deep=True)
    route = next(norm for norm in changed.norm_inventory.norms if norm.norm_id == norm_id)
    route.implementation_mode = ImplementationMode.NONE_REQUIRED

    errors = traceability_errors(changed, spec, LEDGER)

    assert any(e.startswith(f"{norm_id} is a {kind} of a supported operator") for e in errors)


@pytest.mark.parametrize(
    "norm_id",
    ["AIA-NORM-A086-P1-PROVIDE-EXPLANATION", "AIA-NORM-A086-P2-LEGAL-EXCEPTIONS"],
)
def test_any_operator_norm_marked_as_needing_nothing_fails_the_build(bundle, spec, norm_id):
    """Whatever its kind, a norm a supported operator holds must reach them. Only a
    `dependency_only` effect, which the product applies itself, may need nothing."""
    changed = bundle.model_copy(deep=True)
    norm = next(norm for norm in changed.norm_inventory.norms if norm.norm_id == norm_id)
    norm.implementation_mode = ImplementationMode.NONE_REQUIRED

    errors = traceability_errors(changed, spec, LEDGER)

    assert (
        f"{norm_id} binds a supported operator but implementation_mode is none_required; "
        "it must reach them through a rule, the report or a scope note"
    ) in errors
    assert not any(e.startswith("AIA-NORM-A025-P1-A-NAME-ROLE-TRANSFER") for e in errors)


def test_a_scope_note_norm_must_be_stated_by_its_note(bundle, spec, monkeypatch):
    """A scope note is the norm's only report entry, so the note must exist and quote it."""
    norm_id = "AIA-NORM-A060A-P6-COMPLY-WITH-SECTORAL-LAW"
    renamed = bundle.model_copy(deep=True)
    norm = next(norm for norm in renamed.norm_inventory.norms if norm.norm_id == norm_id)
    norm.implementation_refs = ["AIA-SCOPE-NOTE-UNKNOWN"]
    assert f"{norm_id} names unknown scope note AIA-SCOPE-NOTE-UNKNOWN" in traceability_errors(
        renamed, spec, LEDGER
    )

    monkeypatch.setitem(scope_notes.SCOPE_NOTES, scope_notes.SECTION_B, "Chapter III not checked.")
    assert f"{norm_id} scope note {scope_notes.SECTION_B} does not state its enacted text" in (
        traceability_errors(bundle, spec, LEDGER)
    )


def test_every_guidance_use_is_recorded_as_an_interpretation_link(bundle, spec):
    """Handing a question or rule Commission guidance changes its answers, so each use needs a
    link naming the norm it reads; deleting the Article 5 link must fail the build."""
    unlinked = bundle.model_copy(deep=True)
    unlinked.norm_inventory.interpretations = [
        link
        for link in unlinked.norm_inventory.interpretations
        if link.interpretation_id != "AIA-INT-A005-P1-F-C2025-5052"
    ]

    assert (
        "AIA-CQ-PROHIBITED uses guidance C-2025-5052/workplace-covers-recruitment but no "
        "interpretation link records it"
    ) in traceability_errors(unlinked, spec, LEDGER)


def test_an_interpretation_link_may_claim_only_a_real_use(bundle, spec):
    """A link naming a rule that is never handed the passage would record an interpretation the
    product does not apply."""
    rules = [
        rule.model_copy(update={"guidance_refs": []})
        if rule.rule_id == "AIA-RULE-TR-A50-4"
        else rule
        for rule in spec.rules
    ]
    unused = spec.model_copy(update={"rules": rules})

    assert (
        "AIA-INT-A050-P4-TEXT-C2026-5054 says AIA-RULE-TR-A50-4 uses guidance "
        "C-2026-5054/substantive-human-review, but it does not"
    ) in traceability_errors(bundle, unused, LEDGER)


def test_a_question_may_tag_only_guidance_it_is_handed(bundle, spec, monkeypatch):
    """A guidance line in a question's own text names its passage, so the model can tell it from
    the Act; naming a passage the question is not handed would cite text it never sees."""
    import aiact.norm_traceability as traceability

    guidance = dict(traceability.QUESTION_GUIDANCE)
    guidance["territorial"] = ()
    monkeypatch.setattr(traceability, "QUESTION_GUIDANCE", guidance)

    assert (
        "question territorial tags guidance "
        "C-2026-5054/third-country-incidental-use-not-covered, which it is not handed"
    ) in traceability_errors(bundle, spec, LEDGER)


def test_a_rule_may_tag_only_guidance_it_is_handed(bundle, spec):
    rules = [
        rule.model_copy(update={"guidance_refs": []})
        if rule.rule_id == "AIA-RULE-ALL-A05-1"
        else rule
        for rule in spec.rules
    ]

    assert (
        "AIA-RULE-ALL-A05-1 tags guidance C-2025-5052/misuse-and-provider-safeguards, which it "
        "is not handed"
    ) in traceability_errors(bundle, spec.model_copy(update={"rules": rules}), LEDGER)


def test_the_checker_names_each_broken_link(bundle, spec, tmp_path):
    criteria = a15(spec).criteria
    model_flaws = next(c for c in criteria if c.norm_id == MODEL_FLAWS)
    others = [c for c in criteria if c.norm_id != MODEL_FLAWS]
    stranger = model_flaws.model_copy(update={"norm_id": "AIA-NORM-A015-P9-NOT-A-NORM"})
    # Every document is enforced, so one annex is taken out of scope to have a norm outside it.
    ledger = load_adjudication_ledger(LEDGER).model_dump(mode="json")
    ledger["enforced_scope"] = [
        entry for entry in ledger["enforced_scope"] if entry["document"] != "XIV"
    ]
    ledger["decisions"] = [
        decision
        for decision in ledger["decisions"]
        if not decision["source_ref"].startswith("AIA-TEXT-ANNEX-XIV-")
    ]
    narrowed = tmp_path / "adjudications.yaml"
    narrowed.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
    outside_scope = next(
        n for n in bundle.norm_inventory.norms if n.norm_id.startswith("AIA-NORM-ANNEX-XIV-")
    )
    unrelated = model_flaws.model_copy(update={"norm_id": outside_scope.norm_id})
    edited = model_flaws.model_copy(update={"action": "implement measures against model flaws"})

    def errors(new: list[RuleCriterion]) -> str:
        return "\n".join(traceability_errors(bundle, with_criteria(spec, new), narrowed))

    assert f"{RULE} omits criterion {MODEL_FLAWS}" in errors(others)
    assert f"{RULE} lists criterion {MODEL_FLAWS} more than once" in errors(
        [*criteria, model_flaws]
    )
    assert f"{RULE} names missing norm AIA-NORM-A015-P9-NOT-A-NORM" in errors([*criteria, stranger])
    assert f"{RULE} names {outside_scope.norm_id}, which does not point back" in errors(
        [*criteria, unrelated]
    )
    assert "outside the adjudicated validity scope" in errors([*criteria, unrelated])
    assert f"{MODEL_FLAWS} differs from its canonical norm" in errors([*others, edited])


def test_an_unadjudicated_fragment_cannot_be_a_criterion(bundle, spec, tmp_path):
    ledger = load_adjudication_ledger(LEDGER).model_dump(mode="json")
    ledger["decisions"] = [d for d in ledger["decisions"] if d["target"] != MODEL_FLAWS]
    path = tmp_path / "adjudications.yaml"
    path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")

    found = traceability_errors(bundle, spec, path)
    assert any(
        f"criterion {MODEL_FLAWS} cannot be reconstructed: validity finding" in e for e in found
    )


def test_article_sixteen_cross_references_are_typed_relations_not_hidden_criteria(bundle, spec):
    relations = {relation.relation_id: relation for relation in bundle.norm_inventory.relations}
    norms = {norm.norm_id: norm for norm in bundle.norm_inventory.norms}
    allocation = relations[SECTION_2_ALLOCATION]
    source = norms[allocation.source_norm_id]

    assert allocation.kind is NormRelationKind.ALLOCATES_DUTY_TO_POLICY_RULES
    assert set(allocation.target_rule_ids) == set(source.implementation_refs)
    assert "AIA-RULE-HR-A15" in allocation.target_rule_ids

    # Article 16 is the hard reference case. Every one of its twelve duties has exactly one
    # explicit handling path; none is an untracked duplicate of a rule-level finding.
    direct = {
        "AIA-NORM-A016-B-PROVIDER-IDENTIFICATION": "AIA-RULE-PO-A16-B",
        "AIA-NORM-A016-K-DEMONSTRATE-CONFORMITY": "AIA-RULE-PO-A16-K",
        "AIA-NORM-A016-L-ACCESSIBILITY": "AIA-RULE-PO-A16-L",
    }
    policy_relation_sources = {
        relation.source_norm_id
        for relation in relations.values()
        if relation.kind
        in {
            NormRelationKind.ALLOCATES_DUTY_TO_POLICY_RULES,
            NormRelationKind.CARRIED_BY_POLICY_RULES,
        }
    }
    assert {
        norm_id
        for norm_id, norm in norms.items()
        if norm_id.startswith("AIA-NORM-A016-")
        and norm.implementation_mode is ImplementationMode.COMPLIANCE_RULE
        and len(norm.implementation_refs) == 1
        and norm_id not in policy_relation_sources
    } == set(direct)
    assert {norm_id: norms[norm_id].implementation_refs for norm_id in direct} == {
        norm_id: [rule_id] for norm_id, rule_id in direct.items()
    }

    carried_by_rules = {
        "AIA-NORM-A016-F-CONFORMITY-ASSESSMENT",
        "AIA-NORM-A016-G-EU-DECLARATION",
        "AIA-NORM-A016-H-CE-MARKING",
        "AIA-NORM-A016-I-REGISTRATION",
    }
    assert {
        relation.source_norm_id
        for relation in relations.values()
        if relation.kind is NormRelationKind.CARRIED_BY_POLICY_RULES
    } & set(norms) >= carried_by_rules

    carried_by_norms = {
        "AIA-NORM-A016-C-QUALITY-MANAGEMENT",
        "AIA-NORM-A016-D-KEEP-DOCUMENTATION",
        "AIA-NORM-A016-E-KEEP-LOGS",
        "AIA-NORM-A016-J-CORRECTIVE-ACTION",
    }
    assert {
        relation.source_norm_id
        for relation in relations.values()
        if relation.kind is NormRelationKind.CARRIED_BY_NORMS
    } & set(norms) >= carried_by_norms

    external = relations["AIA-REL-A016-L-REQUIRES-ACCESSIBILITY-DIRECTIVES"]
    assert external.kind is NormRelationKind.SUBJECT_TO_EXTERNAL_REQUIREMENTS
    assert external.target_rule_ids == []
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_article_sixteen_allocation_relation_cannot_be_deleted(bundle, spec):
    broken = bundle.model_copy(deep=True)
    broken.norm_inventory.relations = [
        relation
        for relation in broken.norm_inventory.relations
        if relation.relation_id != SECTION_2_ALLOCATION
    ]

    errors = traceability_errors(broken, spec, LEDGER)
    assert (
        "AIA-RULE-HR-A15 omits criterion AIA-NORM-A016-A-SECTION-2-COMPLIANCE, which names it"
        in errors
    )


def test_article_sixteen_norm_carried_duty_cannot_be_deleted(bundle, spec):
    relation_id = "AIA-REL-A016-C-QUALITY-MANAGEMENT-CARRIED-BY-NORMS"
    broken = bundle.model_copy(deep=True)
    broken.norm_inventory.relations = [
        relation
        for relation in broken.norm_inventory.relations
        if relation.relation_id != relation_id
    ]

    assert (
        "AIA-NORM-A016-C-QUALITY-MANAGEMENT carried_by_other_norm requires exactly one "
        "carried_by_norms relation, found 0"
    ) in traceability_errors(broken, spec, LEDGER)


def test_article_seventeen_groups_only_homogeneous_qms_obligations(bundle, spec):
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    implemented = {
        norm.norm_id
        for norm in bundle.norm_inventory.norms
        if segments[norm.primary_spans[0]].source.kind is SourceKind.ARTICLE
        and segments[norm.primary_spans[0]].source.document == "17"
        and norm.implementation_mode is ImplementationMode.COMPLIANCE_RULE
        and ARTICLE_17_RULE in norm.implementation_refs
    }
    rule = a17(spec)

    assert len(implemented) == 17
    assert {criterion.norm_id for criterion in rule.criteria} == implemented
    assert not any(criterion.mandatory for criterion in rule.criteria)
    verdict, reported = settle(rule, Verdict.PASS, ())
    assert verdict is Verdict.NOT_APPLICABLE
    assert len(reported) == 17
    assert all(item.verdict is Verdict.NOT_APPLICABLE and not item.mandatory for item in reported)
    projected = {norm.norm_id: norm for norm in spec.report_norms}
    assert projected["AIA-NORM-A017-P3-SECTORAL-INTEGRATION"].kind.value == "permission"
    assert projected["AIA-NORM-A017-P4-FINANCIAL-DEEMING"].kind.value == "legal_consequence"
    assert all(
        criterion.kind.value == "obligation" and criterion.actors == ["provider"]
        for criterion in rule.criteria
    )
    assert traceability_errors(bundle, spec, LEDGER) == []


def test_deleting_the_model_flaws_criterion_fails_the_strict_build(tmp_path):
    """The whole `build_normative_coverage.py --check` path, against a spec missing one line."""
    text = SPEC.read_text(encoding="utf-8")
    line = f"      - norm_id: {MODEL_FLAWS}\n"
    assert text.count(line) == 1
    broken = tmp_path / "spec.yaml"
    broken.write_text(text.replace(line, ""), encoding="utf-8")
    paths = NormBuilderPaths(
        reviewed_documents=COVERAGE / "segments",
        norm_sources=COVERAGE / "source-records",
        articles_root=POLICY / "articles",
        annexes_root=POLICY / "annexes",
        guidance_root=POLICY / "guidance",
        text_output=COVERAGE / "text-review",
        norm_output=COVERAGE / "norms",
        report_output=COVERAGE / "report.md",
        generated_by="src/aiact/norm_builder.py",
        adjudications=LEDGER,
        policy_spec=broken,
    )

    with pytest.raises(ValueError, match=f"{RULE} omits criterion {MODEL_FLAWS}"):
        run_builder(paths, check=True)
    run_builder(dataclasses.replace(paths, policy_spec=SPEC), check=True)


# --- the loader resolves meaning; it never accepts it written by hand ---------------------------
def _spec_with(tmp_path: Path, old: str, new: str) -> Path:
    text = SPEC.read_text(encoding="utf-8")
    assert text.count(old) == 1
    path = tmp_path / "spec.yaml"
    path.write_text(text.replace(old, new), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("new", "error"),
    [
        (
            f"      - norm_id: {MODEL_FLAWS}\n        action: control model flaws\n",
            "must name only `norm_id`",
        ),
        ("      - norm_id: AIA-NORM-A015-P9-NOT-A-NORM\n", "not in the norm inventory"),
        ("      - norm_id: AIA-NORM-A014-P1-EFFECTIVE-OVERSIGHT\n", "do not point back"),
        (f"      - norm_id: {MODEL_FLAWS}\n" * 2, "duplicate criteria"),
    ],
)
def test_the_loader_refuses_a_criterion_it_cannot_resolve(tmp_path, new, error):
    path = _spec_with(tmp_path, f"      - norm_id: {MODEL_FLAWS}\n", new)
    with pytest.raises(ValueError, match=error):
        load_policy_spec(path, POLICY / "articles", norms_root=COVERAGE / "norms")


# --- one rule, several duty-holders --------------------------------------------------------------
def _rule_with(spec, roles: list[str], actor_sets: list[list[str]]) -> dict:
    """HR-A15 with its first criteria re-assigned, so only the actor fields differ."""
    rule = next(rule for rule in spec.rules if rule.rule_id == RULE).model_dump()
    rule["applies_to_role"] = roles
    rule["criteria"] = [
        {**criterion, "actors": actors}
        for criterion, actors in zip(rule["criteria"], actor_sets, strict=False)
    ]
    return rule


def test_a_rule_may_bind_several_roles_and_each_reads_only_what_it_owes(spec):
    rule = PolicyRule.model_validate(
        _rule_with(spec, ["provider", "deployer"], [["provider"], ["provider", "deployer"]])
    )
    assert rule.for_role(ActorRole.PROVIDER) is rule
    deployer = rule.for_role(ActorRole.DEPLOYER)
    assert [c.norm_id for c in deployer.criteria] == [rule.criteria[1].norm_id]


def test_a_criterion_no_role_of_the_rule_owes_is_refused(spec):
    with pytest.raises(ValueError, match="none of which is or covers a role in applies_to_role"):
        PolicyRule.model_validate(_rule_with(spec, ["provider"], [["provider"], ["deployer"]]))


def test_an_operator_criterion_is_owed_by_every_role_it_covers(spec):
    """Art. 3(8) makes "operator" the collective noun for six roles, so a duty the Act addresses
    to operators is owed by each role of the rule that it covers, and each reads it."""
    rule = PolicyRule.model_validate(
        _rule_with(spec, ["provider", "deployer"], [["operator"], ["provider"]])
    )
    assert [c.norm_id for c in rule.for_role(ActorRole.DEPLOYER).criteria] == [
        rule.criteria[0].norm_id
    ]
    assert rule.for_role(ActorRole.PROVIDER) is rule
    assert ActorRole.OPERATOR.covered_roles == {
        ActorRole.PROVIDER,
        ActorRole.PRODUCT_MANUFACTURER,
        ActorRole.DEPLOYER,
        ActorRole.AUTHORISED_REPRESENTATIVE,
        ActorRole.IMPORTER,
        ActorRole.DISTRIBUTOR,
    }
    assert ActorRole.PROVIDER.covered_roles == {ActorRole.PROVIDER}


def test_a_role_that_owes_no_criterion_is_refused(spec):
    with pytest.raises(ValueError, match="applies to deployer, but no criterion names that role"):
        PolicyRule.model_validate(
            _rule_with(spec, ["provider", "deployer"], [["provider"], ["provider"]])
        )


# --- aggregation is conservative ------------------------------------------------------------------
def _c(norm_id: str, verdict: Verdict, mandatory: bool = True) -> CriterionFinding:
    return CriterionFinding(
        norm_id=norm_id,
        mandatory=mandatory,
        verdict=verdict,
        reasoning="because",
        confidence="high",
    )


P, G, THIN, R, NA = (
    Verdict.PASS,
    Verdict.GAP,
    Verdict.INADEQUATE,
    Verdict.NEEDS_REVIEW,
    Verdict.NOT_APPLICABLE,
)


@pytest.mark.parametrize(
    ("verdicts", "expected"),
    [
        ([P, P, P], P),
        ([P, P, G], THIN),
        ([P, THIN, P], THIN),
        ([G, G, G], G),
        ([G, R, G], G),
        ([P, R, P], R),
        ([P, NA, P], R),
        ([NA, NA], NA),
    ],
)
def test_one_criterion_is_never_outvoted(verdicts, expected):
    criteria = [_c(f"AIA-NORM-X-{n}", v) for n, v in enumerate(verdicts)]
    assert aggregate_criteria(criteria) is expected


def test_a_non_mandatory_criterion_neither_passes_nor_fails_the_rule():
    criteria = [_c("AIA-NORM-X-1", P), _c("AIA-NORM-X-2", G, mandatory=False)]
    assert aggregate_criteria(criteria) is P


def test_a_finding_cannot_pass_over_a_failing_criterion():
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689", article="15", act_version_date=date(2026, 7, 27)
    )
    with pytest.raises(ValueError, match="aggregate to inadequate"):
        Finding(
            rule_id=RULE,
            use_case_id="scoring",
            role="provider",
            verdict=Verdict.PASS,
            reasoning="looks fine",
            citation=source,
            confidence="high",
            criteria=[_c("AIA-NORM-X-1", P), _c(MODEL_FLAWS, G)],
        )


# --- a stub judge through the graph and the report ------------------------------------------------
def a_classification() -> ClassificationResult:
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689", article="6", act_version_date=date(2026, 7, 27)
    )
    evidence = [ClassificationEvidence(source=source, quote="scores candidates", reasoning="6(2)")]
    use_case = UseCaseClassification(
        use_case_id="scoring",
        description="ranks job applicants",
        risk_class=RiskClass.HIGH_RISK,
        annex_iii_area=AnnexIIIArea.EMPLOYMENT,
        reasoning="fixture",
        confidence="high",
        triggered_by=evidence,
    )
    return ClassificationResult(
        use_cases=[use_case],
        overall_risk_class=RiskClass.HIGH_RISK,
        reasoning="fixture",
        triggered_by=evidence,
        confidence="high",
    )


class CriterionStubJudge:
    """Passes every criterion except the ones named in `verdicts`; skips those in `omit`."""

    def __init__(
        self, verdicts: dict[str, Verdict] | None = None, omit: frozenset[str] = frozenset()
    ):
        self.verdicts = verdicts or {}
        self.omit = omit

    def judge(self, rule: PolicyRule, document: str) -> Judgement:
        reported = tuple(
            CriterionFinding(
                norm_id=c.norm_id,
                mandatory=True,
                verdict=self.verdicts.get(c.norm_id, Verdict.PASS),
                reasoning=(
                    MODEL_FLAWS_REASON
                    if c.norm_id == MODEL_FLAWS
                    else f"Section 8.3 addresses {c.norm_id}."
                ),
                confidence="high",
            )
            for c in rule.criteria
            if c.mandatory and c.norm_id not in self.omit
        )
        return Judgement(
            # Deliberately claims a pass: the graph must not believe it.
            verdict=Verdict.PASS,
            reasoning="every control is described",
            evidence_quote=None,
            evidence_chunk_id=None,
            confidence="high",
            criteria=reported,
        )


def _review(spec: PolicyRuleset, judge: CriterionStubJudge) -> ComplianceReport:
    return analyse(
        FIXTURE.read_text(encoding="utf-8"),
        a_classification(),
        spec,
        brain=ScriptedBrain({}),
        judge=judge,  # type: ignore[arg-type]
        system_id="talentrank",
        max_workers=1,
    )


def _a15_finding(report: ComplianceReport) -> Finding:
    return next(f for f in report.findings if f.rule_id == RULE)


def test_the_fixture_addresses_every_sibling_threat_and_not_model_flaws():
    text = FIXTURE.read_text(encoding="utf-8")
    for heading in SIBLING_THREATS.values():
        assert f"\n{heading}." in text
    assert "flaw" not in text.lower()


def test_a_model_flaws_gap_cannot_yield_an_article_15_pass(spec, tmp_path):
    report = _review(spec, CriterionStubJudge({MODEL_FLAWS: Verdict.GAP}))
    finding = _a15_finding(report)
    by_id = {c.norm_id: c for c in finding.criteria}

    assert finding.verdict is Verdict.INADEQUATE
    assert [c.norm_id for c in finding.criteria] == [c.norm_id for c in a15(spec).criteria]
    assert by_id[MODEL_FLAWS].verdict is Verdict.GAP
    assert by_id[MODEL_FLAWS].reasoning == MODEL_FLAWS_REASON
    assert all(by_id[norm_id].verdict is Verdict.PASS for norm_id in SIBLING_THREATS)
    assert MODEL_FLAWS in finding.reasoning
    assert report.summary.passed < report.summary.total_applicable
    # The only persisted-report entry point requires the policy spec and keeps every criterion.
    path = tmp_path / "report.json"
    path.write_text(report.model_dump_json(), encoding="utf-8")
    reloaded = load_compliance_report(path, spec)
    assert _a15_finding(reloaded).criteria == finding.criteria


def test_the_rendered_report_names_the_norm_and_its_reason(spec):
    report = _review(spec, CriterionStubJudge({MODEL_FLAWS: Verdict.GAP}))
    text = render_report(report, spec)
    lines = text.splitlines()
    criterion_lines = [i for i, line in enumerate(lines) if line.split() == ["GAP", MODEL_FLAWS]]

    assert len(criterion_lines) == 1
    assert "controls model flaws" in lines[criterion_lines[0] + 1]
    rule_line = next(line for line in text.splitlines() if f" {RULE} " in line)
    assert not rule_line.strip().startswith("ok")


def test_a_criterion_the_judge_skips_is_needs_review_not_pass(spec):
    finding = _a15_finding(_review(spec, CriterionStubJudge(omit=frozenset({MODEL_FLAWS}))))
    model_flaws = next(c for c in finding.criteria if c.norm_id == MODEL_FLAWS)

    assert finding.verdict is Verdict.NEEDS_REVIEW
    assert model_flaws.verdict is Verdict.NEEDS_REVIEW
    assert "no verdict" in model_flaws.reasoning


def test_a_whole_rule_pass_without_criteria_is_not_a_pass(spec):
    verdict, criteria = settle(a15(spec), Verdict.PASS, ())
    assert verdict is Verdict.NEEDS_REVIEW
    assert {c.verdict for c in criteria if c.mandatory} == {Verdict.NEEDS_REVIEW}


def test_the_report_refuses_a_finding_that_drops_a_criterion(spec, tmp_path):
    report = _review(spec, CriterionStubJudge({MODEL_FLAWS: Verdict.GAP}))
    payload = json.loads(report.model_dump_json())
    finding = next(f for f in payload["findings"] if f["rule_id"] == RULE)
    finding["criteria"] = [c for c in finding["criteria"] if c["norm_id"] != MODEL_FLAWS]
    finding["verdict"] = "pass"
    finding["reasoning"] = "All mandatory criteria pass."

    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="reports criteria"):
        load_compliance_report(path, spec)


# --- the real judge's parsing, with the model stubbed ---------------------------------------------
@pytest.fixture
def llm_judge(monkeypatch):
    body = FIXTURE.read_text(encoding="utf-8")
    hit = Hit(
        chunk=Chunk(
            chunk_id="c001",
            body=body,
            heading_path="Doc > Accuracy, robustness and cybersecurity",
            char_start=0,
            char_end=len(body),
        ),
        distance=0.5,
    )
    judge = LLMJudge(model="stub/model")
    monkeypatch.setattr("aiact.gap.judge.find_evidence", lambda index, rule, k: [hit])
    monkeypatch.setattr(
        LLMJudge,
        "index_for",
        lambda self, document: types.SimpleNamespace(chunks={"c001": hit.chunk}),
    )
    return judge


@pytest.fixture
def model_reply(monkeypatch):
    """Install a fake `litellm` returning one JSON body, and keep the prompt it was sent."""
    sent: list[str] = []

    def _install(payload: dict) -> list[str]:
        message = types.SimpleNamespace(content=json.dumps(payload))
        response = types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

        def completion(**kwargs):
            sent.append(json.dumps(kwargs["messages"]))
            return response

        monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=completion))
        return sent

    return _install


def _entries(spec: PolicyRuleset, **overrides: str) -> list[dict]:
    return [
        {
            "norm_id": c.norm_id,
            "verdict": overrides.get(c.norm_id, "pass"),
            "reasoning": MODEL_FLAWS_REASON if c.norm_id == MODEL_FLAWS else "Described in 8.3.",
            "evidence_quote": None,
            "evidence_chunk_id": None,
            "confidence": "high",
        }
        for c in a15(spec).criteria
        if c.mandatory
    ]


def test_the_judge_rules_per_criterion_and_computes_the_rule(spec, llm_judge, model_reply):
    sent = model_reply({"criteria": _entries(spec, **{MODEL_FLAWS: "gap"}), "verdict": "pass"})
    judgement = llm_judge.judge(a15(spec), FIXTURE.read_text(encoding="utf-8"))
    by_id = {c.norm_id: c for c in judgement.criteria}

    assert judgement.verdict is Verdict.INADEQUATE
    assert by_id[MODEL_FLAWS].verdict is Verdict.GAP
    assert by_id[MODEL_FLAWS].reasoning == MODEL_FLAWS_REASON
    assert "AIA-NORM-A015-P4-REDUNDANCY" not in by_id
    # The prompt carries the materialised criterion, not only the two-word slice.
    prompt = json.loads(sent[0])[1]["content"]
    prompt = prompt if isinstance(prompt, str) else "".join(p["text"] for p in prompt)
    assert f"- {MODEL_FLAWS}" in prompt
    action = "implement measures to prevent, detect, respond to, resolve, and control model flaws"
    assert action in prompt
    assert "only where: where appropriate" in prompt
    assert "AIA-NORM-A015-P4-REDUNDANCY" not in prompt


@pytest.mark.parametrize(
    "mangle",
    [
        lambda entries: [e for e in entries if e["norm_id"] != MODEL_FLAWS],
        lambda entries: entries + [e for e in entries if e["norm_id"] == MODEL_FLAWS],
        lambda entries: [
            {**e, "verdict": "maybe"} if e["norm_id"] == MODEL_FLAWS else e for e in entries
        ],
    ],
    ids=["omitted", "duplicated", "unreadable"],
)
def test_a_criterion_the_model_mishandles_is_needs_review(spec, llm_judge, model_reply, mangle):
    model_reply({"criteria": mangle(_entries(spec))})
    judgement = llm_judge.judge(a15(spec), FIXTURE.read_text(encoding="utf-8"))
    model_flaws = next(c for c in judgement.criteria if c.norm_id == MODEL_FLAWS)

    assert model_flaws.verdict is Verdict.NEEDS_REVIEW
    assert judgement.verdict is Verdict.NEEDS_REVIEW
    assert llm_judge.check(a15(spec), FIXTURE.read_text(encoding="utf-8")) is Verdict.NEEDS_REVIEW


def test_a_rule_with_criteria_rejects_a_legacy_rule_level_model_reply(spec, llm_judge, model_reply):
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-HR-A14")
    sent = model_reply({"verdict": "gap", "reasoning": "No oversight.", "confidence": "high"})
    judgement = llm_judge.judge(rule, "# Doc\n")

    assert judgement.verdict is Verdict.NEEDS_REVIEW
    assert judgement.criteria
    assert "SEPARATE CRITERIA" in sent[0]
