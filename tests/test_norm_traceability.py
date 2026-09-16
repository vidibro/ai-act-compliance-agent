"""Norm-to-rule traceability for the Article 15 pilot, proved without a model.

Four links, each held here by a deterministic test: every enforced Article 15 compliance norm is an
explicit criterion of AIA-HR-A15; each criterion resolves to the canonical norm and is materialised
from it; each is judged and reported on its own; and the rule passes only when every mandatory
criterion does. A stub judge stands in for the model — whether a real model judges the fixture
well is an evaluation question, not what these tests prove.
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
from aiact.schemas.enums import AnnexIIIArea, RiskClass, Verdict
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

RULE = "AIA-HR-A15"
ARTICLE_10_RULE = "AIA-HR-A10"
ARTICLE_17_RULE = "AIA-PO-A17"
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
    """The spec with AIA-HR-A15's criteria replaced, unvalidated, to test the checker itself."""
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


def test_model_flaws_is_materialised_with_its_full_action_and_condition(spec):
    criterion = next(c for c in a15(spec).criteria if c.norm_id == MODEL_FLAWS)

    assert criterion.norm_text == "model flaws"
    assert criterion.subjects == ["provider"]
    assert criterion.mandatory
    for verb in ("prevent", "detect", "respond to", "resolve", "control"):
        assert verb in criterion.action
    assert "model flaws" in criterion.action
    assert criterion.conditions == [
        "measures addressing the AI-specific vulnerability are appropriate"
    ]
    assert criterion.source_spans == ["AIA-TEXT-A015-P009"]


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
                norm
                for norm in spec.report_norms
                if norm.norm_id != "AIA-NORM-A015-P4-REDUNDANCY"
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


def test_the_checker_names_each_broken_link(bundle, spec):
    criteria = a15(spec).criteria
    model_flaws = next(c for c in criteria if c.norm_id == MODEL_FLAWS)
    others = [c for c in criteria if c.norm_id != MODEL_FLAWS]
    stranger = model_flaws.model_copy(update={"norm_id": "AIA-NORM-A015-P9-NOT-A-NORM"})
    article_14 = next(
        n
        for n in bundle.norm_inventory.norms
        if n.norm_id.startswith("AIA-NORM-A014-") and RULE not in n.implementation_refs
    )
    unrelated = model_flaws.model_copy(update={"norm_id": article_14.norm_id})
    edited = model_flaws.model_copy(update={"action": "implement measures against model flaws"})

    def errors(new: list[RuleCriterion]) -> str:
        return "\n".join(traceability_errors(bundle, with_criteria(spec, new), LEDGER))

    assert f"{RULE} omits criterion {MODEL_FLAWS}" in errors(others)
    assert f"{RULE} lists criterion {MODEL_FLAWS} more than once" in errors(
        [*criteria, model_flaws]
    )
    assert f"{RULE} names missing norm AIA-NORM-A015-P9-NOT-A-NORM" in errors(
        [*criteria, stranger]
    )
    assert f"{RULE} names {article_14.norm_id}, which does not point back" in errors(
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
    assert "AIA-HR-A15" in allocation.target_rule_ids

    # Article 16 is the hard reference case. Every one of its twelve duties has exactly one
    # explicit handling path; none is an untracked duplicate of a rule-level finding.
    direct = {
        "AIA-NORM-A016-B-PROVIDER-IDENTIFICATION": "AIA-PO-A16-B",
        "AIA-NORM-A016-K-DEMONSTRATE-CONFORMITY": "AIA-PO-A16-K",
        "AIA-NORM-A016-L-ACCESSIBILITY": "AIA-PO-A16-L",
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
        "AIA-HR-A15 omits criterion AIA-NORM-A016-A-SECTION-2-COMPLIANCE, which names it"
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
        criterion.kind.value == "obligation" and criterion.subjects == ["provider"]
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
    assert "only where: measures addressing the AI-specific vulnerability are appropriate" in prompt
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


def test_a_rule_without_criteria_keeps_its_prompt_and_contract(spec, llm_judge, model_reply):
    rule = next(r for r in spec.rules if r.rule_id == "AIA-HR-A14")
    sent = model_reply(
        {"verdict": "gap", "reasoning": "No oversight.", "confidence": "high"}
    )
    judgement = llm_judge.judge(rule, "# Doc\n")

    assert judgement.verdict is Verdict.GAP
    assert judgement.criteria == ()
    assert "SEPARATE CRITERIA" not in sent[0]
