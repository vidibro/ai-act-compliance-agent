"""Loader tests + sanity checks on the shipped policy spec.

The load-bearing test here is `test_every_requirement_is_literal_article_text`: it proves the
`requirement` of every rule is the verbatim enacted text of the provision it cites, taken from
data/policy/articles/. That is what makes the ruleset trustworthy — no reviewer has to take
anyone's word that a requirement summarises its article correctly.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
import yaml

from aiact.gap.rules import roles_with_rules
from aiact.policy_loader import load_policy_spec, resolve_requirement
from aiact.schemas.enums import ActorRole, CheckType, ObligationStatus, RiskClass

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "data" / "policy" / "spec.yaml"
ARTICLES_ROOT = ROOT / "data" / "policy" / "articles"
ACT_DATE = date(2024, 7, 12)
VERSION = ACT_DATE.isoformat()
ARTICLES_DIR = ARTICLES_ROOT / VERSION
SCOPE_PATH = ROOT / "data" / "policy" / f"scope-{VERSION}.yaml"


def _spec():
    return load_policy_spec(SPEC_PATH, ARTICLES_ROOT)


def test_shipped_spec_loads():
    spec = _spec()
    assert spec.spec_version == "0.7.0"
    assert spec.act_version_date == ACT_DATE
    # 7 Art.9-15 + 11 provider obligations + 1 Art.6(4) + Art.4 (provider AND deployer)
    # + 3 deployer (Arts. 26-27, 86) + 3 supply-chain (Arts. 22-24)
    assert len(spec.rules) == 26


def test_article_store_is_version_scoped():
    """Versions live side by side so a report pinned to an older act version stays reproducible."""
    assert ARTICLES_DIR.is_dir(), f"expected a version-scoped store at {ARTICLES_DIR}"
    assert len(list(ARTICLES_DIR.glob("article-*.md"))) == 113
    assert not list(ARTICLES_ROOT.glob("article-*.md")), "articles must not sit at the store root"


def test_every_article_is_classified_in_scope_or_out():
    """THE COVERAGE GUARANTEE. Every article is either cited by a rule or explicitly out of scope.
    A new article in a future Act version is neither -> this fails -> a human must rule on it.
    That is how a newly legislated obligation cannot silently go unchecked."""
    spec = _spec()
    ledger = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
    assert ledger["act_version_date"] == ACT_DATE

    in_store = {int(p.stem.split("-")[1]) for p in ARTICLES_DIR.glob("article-*.md")}
    cited = {r.source.article for r in spec.rules}
    out_of_scope = set(ledger["out_of_scope"])

    overlap = cited & out_of_scope
    assert not overlap, f"articles both cited and marked out of scope: {sorted(overlap)}"

    unclassified = in_store - cited - out_of_scope
    assert not unclassified, (
        f"Articles present in the store but neither cited by a rule nor listed in "
        f"{SCOPE_PATH.name}: {sorted(unclassified)}. Rule on them before shipping."
    )

    phantom = (cited | out_of_scope) - in_store
    assert not phantom, f"classified articles that do not exist in the store: {sorted(phantom)}"


def test_every_role_is_classified_in_scope_or_out():
    """THE SAME COVERAGE GUARANTEE, over ActorRole. A role either has rules or is listed in the
    ledger with a reason; a role that is neither fails here. That is what stops a duty-holder
    silently vanishing from every report — an omitted role reads as a role that owes nothing, and
    no role the Act names owes nothing."""
    spec = _spec()
    ledger = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
    covered = set(roles_with_rules(spec))
    excluded = {ActorRole(r) for r in ledger["roles_out_of_scope"]}

    overlap = covered & excluded
    assert not overlap, f"roles both given rules and marked out of scope: {sorted(overlap)}"

    unclassified = set(ActorRole) - covered - excluded
    assert not unclassified, (
        f"Roles in ActorRole that neither have rules nor appear in {SCOPE_PATH.name}: "
        f"{sorted(unclassified)}. Rule on them before shipping."
    )


def test_roles_out_of_scope_entries_have_reasons():
    ledger = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
    for role, reason in ledger["roles_out_of_scope"].items():
        assert isinstance(reason, str) and len(reason.strip()) > 15, (
            f"Role {role} is dismissed without a real reason"
        )


def test_out_of_scope_entries_have_reasons():
    ledger = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
    for article, reason in ledger["out_of_scope"].items():
        assert isinstance(reason, str) and len(reason.strip()) > 15, (
            f"Article {article} is dismissed without a real reason"
        )


def test_every_requirement_is_literal_article_text():
    """Each rule's requirement must be the verbatim text of the cited provision, as stored in the
    article files. This is the guarantee against paraphrase creeping back in."""
    spec = _spec()
    for r in spec.rules:
        article_file = ARTICLES_DIR / f"article-{r.source.article:03d}.md"
        body = re.sub(r"\s+", " ", article_file.read_text(encoding="utf-8"))
        req = re.sub(r"\s+", " ", r.requirement).strip()
        assert req, f"{r.rule_id} resolved to empty requirement"
        assert req in body, (
            f"{r.rule_id}: requirement is not literal text of Article {r.source.article}"
        )


def test_spec_contains_no_legal_text():
    """spec.yaml must not hand-write requirement — legal text lives only in the article store."""
    raw = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    for rule in raw["rules"]:
        assert "requirement" not in rule, f"{rule['rule_id']} hand-writes requirement in the spec"


def test_loader_rejects_hand_written_requirement(tmp_path):
    raw = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    raw["rules"][0]["requirement"] = "A risk management system shall be established."
    bad = tmp_path / "handwritten.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="hand-writes"):
        load_policy_spec(bad, ARTICLES_ROOT)


def test_resolve_paragraph_vs_whole_article():
    """A citation with a paragraph resolves to that paragraph; without one, to the whole article."""
    whole, _ = resolve_requirement(ARTICLES_DIR, 43, None)
    para2, _ = resolve_requirement(ARTICLES_DIR, 43, 2)
    assert para2.startswith("For high-risk AI systems referred to in points 2 to 8 of Annex III")
    assert para2 in re.sub(r"\s+", " ", whole) or para2 in whole
    assert len(para2) < len(whole)


def test_resolve_unknown_paragraph_raises():
    with pytest.raises(ValueError, match="no paragraph 99"):
        resolve_requirement(ARTICLES_DIR, 9, 99)


def test_resolve_missing_article_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="No article file"):
        resolve_requirement(tmp_path, 9, None)


def test_resolve_rejects_version_mismatch():
    """Closes the silent-drift hole: resolving a rule against an article fetched for a DIFFERENT
    act version would swap the requirement's meaning while the spec still claims the old pin."""
    with pytest.raises(ValueError, match="Refusing to resolve requirement text across versions"):
        resolve_requirement(ARTICLES_DIR, 9, None, expected_version="2026-08-02")


def test_load_rejects_spec_with_no_article_store(tmp_path):
    """A spec pinned to a version we have not fetched must fail loudly, never fall back."""
    raw = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    raw["act_version_date"] = date(2099, 1, 1)
    for rule in raw["rules"]:
        rule["source"]["act_version_date"] = date(2099, 1, 1)
    bad = tmp_path / "future.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="No article store for act version 2099-01-01"):
        load_policy_spec(bad, ARTICLES_ROOT)


def test_source_url_resolved_from_article_store():
    """Rules don't author a URL; the loader fills it from the article's own provenance."""
    spec = _spec()
    for r in spec.rules:
        assert r.source.url and r.source.url.startswith("http"), f"{r.rule_id} has no source.url"


def test_rule_ids_unique_and_well_formed():
    spec = _spec()
    ids = [r.rule_id for r in spec.rules]
    assert len(ids) == len(set(ids))
    assert all(r.rule_id.startswith("AIA-") for r in spec.rules)


def test_every_rule_pinned_to_spec_version_date():
    spec = _spec()
    assert all(r.source.act_version_date == spec.act_version_date for r in spec.rules)


def test_provider_process_obligations_are_not_document_verifiable():
    """The Art. 16+ family must be confirm-separately, never silently flagged as gaps."""
    spec = _spec()
    process = [r for r in spec.rules if r.rule_id.startswith("AIA-PO-")]
    assert process, "expected provider process obligations in the spec"
    assert all(not r.document_verifiable for r in process)


def test_high_risk_requirements_are_document_verifiable():
    spec = _spec()
    reqs = [r for r in spec.rules if r.rule_id.startswith("AIA-HR-")]
    assert len(reqs) == 7
    assert all(r.document_verifiable for r in reqs)


def test_every_rule_is_mandatory_and_names_a_duty_holder():
    """`recommended` rules are reported but never counted as gaps, so a spec of only mandatory ones
    keeps the tally meaningful. Each must also name at least one role: an obligation nobody owes
    would activate for nobody and sit in the spec looking covered."""
    spec = _spec()
    for r in spec.rules:
        assert r.obligation_status == ObligationStatus.MANDATORY
        assert r.applies_to_role, f"{r.rule_id} names no duty-holder"


def test_both_duty_holders_are_covered():
    """Obligations attach to the ROLE. A spec carrying only provider rules cannot produce a
    deployer section, and a report that silently omits one is misleading rather than narrower."""
    spec = _spec()
    by_role = {
        role: [r.rule_id for r in spec.rules if role in r.applies_to_role]
        for role in (ActorRole.PROVIDER, ActorRole.DEPLOYER)
    }
    assert "AIA-DP-A26" in by_role[ActorRole.DEPLOYER]
    assert "AIA-DP-A27" in by_role[ActorRole.DEPLOYER]
    # Art. 4 binds both — the only rule here that does.
    assert "AIA-ALL-A04" in by_role[ActorRole.PROVIDER]
    assert "AIA-ALL-A04" in by_role[ActorRole.DEPLOYER]


def test_substance_rules_are_document_verifiable():
    spec = _spec()
    for r in spec.rules:
        if r.check_type == CheckType.SUBSTANCE:
            assert r.document_verifiable, f"{r.rule_id} is substance but not document_verifiable"


def test_derogation_rule_targets_not_high_risk():
    spec = _spec()
    art6 = next(r for r in spec.rules if r.rule_id == "AIA-NHR-A06-4")
    assert art6.applies_to_risk_class == [RiskClass.NOT_HIGH_RISK]


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_policy_spec(SPEC_PATH.parent / "does_not_exist.yaml", ARTICLES_ROOT)


def test_duplicate_rule_id_rejected(tmp_path):
    raw = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    raw["rules"].append(raw["rules"][0])  # duplicate the first rule_id
    dup_file = tmp_path / "dup.yaml"
    dup_file.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate rule_id"):
        load_policy_spec(dup_file, ARTICLES_ROOT)


def test_act_version_date_mismatch_rejected(tmp_path):
    raw = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    raw["rules"][0]["source"]["act_version_date"] = date(2025, 1, 1)
    bad_file = tmp_path / "mismatch.yaml"
    bad_file.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="different act_version_date"):
        load_policy_spec(bad_file, ARTICLES_ROOT)
