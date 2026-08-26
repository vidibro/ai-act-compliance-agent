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

from aiact.classify.graph import QUESTIONS
from aiact.config import get_settings
from aiact.gap import roles as role_questions
from aiact.policy_loader import (
    _PARAGRAPH_START,
    article_filename,
    load_policy_spec,
    resolve_requirement,
)
from aiact.schemas.enums import ActorRole, CheckType, ObligationStatus, RiskClass

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "data" / "policy" / "spec.yaml"
ARTICLES_ROOT = ROOT / "data" / "policy" / "articles"
ANNEXES_ROOT = ROOT / "data" / "policy" / "annexes"

# READ, never restated. The act version already lives in two places that must agree — the runtime
# setting and the spec header — and a literal here would be a third copy of a fact whose copies
# have already drifted once: a hard-coded date in the classification graph outlived a `.env` that
# said otherwise, and the cascade was set to read one version of the Act while citing another.
# A test that restates the pin cannot detect that; one that reads it is what makes the test agree
# with whatever is actually shipped, and `test_the_two_pins_agree` below turns the agreement itself
# into the assertion.
ACT_DATE = get_settings().act_version_date
VERSION = ACT_DATE.isoformat()
ARTICLES_DIR = ARTICLES_ROOT / VERSION
SCOPE_PATH = ROOT / "data" / "policy" / f"scope-{VERSION}.yaml"


def _spec():
    return load_policy_spec(SPEC_PATH, ARTICLES_ROOT)


def test_the_two_pins_agree():
    """The ruleset and the runtime must read the SAME version of the Act.

    Two independent pins select it: `spec.yaml`'s header decides which article store the
    obligations resolve their text from, and `settings.act_version_date` decides which one the
    classification cascade puts in front of the model. Nothing forces them to match, and when they
    do not, every failure is invisible from the output — a report whose classification was reasoned
    against one text and whose obligations were quoted from another, each half internally
    consistent and correctly cited to a different document.

    Untested until now, which is how the same divergence went unnoticed one layer down: a
    hard-coded date in `classify/graph.py` outlived a `.env` naming an older version."""
    assert _spec().act_version_date == get_settings().act_version_date


def test_shipped_spec_loads():
    spec = _spec()
    assert spec.spec_version == "0.8.0"
    # 7 Art.9-15 + 16 provider obligations + 1 Art.6(4) + Art.4 (provider AND deployer)
    # + 9 deployer (Arts. 26-27, 49(3), 86) + 3 supply-chain (Arts. 22-24) + 1 initial provider
    # (Art. 25(2)). Art. 43 is three rules and Art. 49 two, because both send different systems to
    # different law — see applies_to_route and applies_to_annex_iii_area. Art. 16 is three, one per
    # point that cross-references nothing. Plus 4 Art. 50 transparency rules, the only ones that
    # gate on a duty instead of a tier; Art. 75(1a), which redirects the Art. 73 report to the AI
    # Office; Art. 74(12) full access to the data sets; and Arts. 79 and 82, the two rules binding
    # five roles at once. Two more come from paragraphs whose surroundings bind someone else:
    # Art. 36(8), the one provider duty in Chapter III Section 4, and Art. 75c(3), whose second
    # sentence turns from the AI Office's power to the operator's report back.
    #
    # Seven more pay down articles_awaiting_rules, and each is the CONTENT of a duty another rule
    # only required the existence of: Art. 11(2) one documentation set for an Annex I product,
    # Art. 12(3) the four records a biometric identification log must hold, Art. 13(3) the six
    # items the instructions for use must contain, Art. 41(5) the justification for departing from
    # a common specification, Art. 47(2) what the declaration of conformity must say, Art. 48(2)
    # and (4) the digital marking and the notified body's number, and Arts. 71(2) and (3) what each
    # party enters in the EU database.
    #
    # NINETEEN ARE CHAPTER V, the general-purpose AI model regime, and they share nothing with the
    # rest: `applies_to_risk_class: [gpai_model]` puts them on the other side of the cascade's
    # Art. 3(63) question. Art. 52(1) notification, Art. 53(1)(a) to (d), 53(3) and 53(4),
    # Art. 54(1) to (5) split between the provider and its representative, Art. 55(1)(a) to (d) and
    # 55(2) for a model with systemic risk, and Arts. 91(5) and 92(5) — the two paragraphs of the
    # Commission's investigatory powers that turn and bind the provider, to supply the information
    # requested and to grant access to the model.
    #
    # ONE pays annexes_awaiting_rules: Art. 43(1)'s Annex VII branch, which says what the
    # notified-body route consists of where AIA-PO-A43-1 carries only the choice between it and
    # internal control.
    #
    # Several Articles are more than one rule because they hold more than one duty, and a single
    # rule would let a finding on the first hide a breach of the second: Art. 20, 21 and 47 are two
    # each (the standing duty and what follows it), Art. 22 is two by PARTY — the provider appoints,
    # the representative performs — Art. 27 is three (carry the assessment out, keep it current,
    # file it), Art. 43 is four (three initial routes plus re-assessment), and Art. 49 is three.
    #
    # ART. 26 IS SIX, and it is the widest split in the ruleset because the Article is the widest
    # duty set. Six of its twelve paragraphs bind every deployer alike and are AIA-DP-A26; the other
    # six narrow the duty-holder or the system, and a narrowing is only rendered where it sits on a
    # rule of its own — public-authority registration and the bar on using an unregistered system
    # (26(8)), the data protection impact assessment (26(9)), the post-remote biometric
    # identification regime (26(10)), informing the people subject to an Annex III system (26(11)),
    # and cooperation with authorities (26(12)).
    #
    # Art. 71(2) is TWO rules, one per tier, and they are the only pair split by nothing but the
    # area gate: Art. 49(1) excepts Annex III point 2 from the EU database and Art. 49(2), which
    # registers a system derogated under Art. 6(3), excepts nothing. One rule could not hold both
    # lists without demanding an entry the Act registers nationally or withholding one it does not.
    assert len(spec.rules) == 92


# How many articles each fetched version holds. KEYED BY VERSION EVEN WHILE ONE IS FETCHED, because
# the count is a fact about a particular text rather than about "the store" — the consolidation
# holds 119 where the original held 113, having inserted six articles (4a, 60a, 75a-75d). Keyed
# rather than derived so a truncated or half-written fetch fails here instead of quietly shipping a
# store missing the articles nobody happened to cite, and so the next refresh adds a line rather
# than reworking a number.
ARTICLE_COUNTS = {"2026-07-27": 119}


@pytest.mark.parametrize("version", sorted(ARTICLE_COUNTS))
def test_article_store_is_version_scoped(version):
    """Versions live side by side so a report pinned to an older act version stays reproducible.

    Checked for EVERY fetched version, not just the pinned one — the point of the store is that the
    older text remains intact and readable after a newer one lands, and only the older one can
    demonstrate that."""
    version_dir = ARTICLES_ROOT / version
    assert version_dir.is_dir(), f"expected a version-scoped store at {version_dir}"
    assert len(list(version_dir.glob("article-*.md"))) == ARTICLE_COUNTS[version]
    assert not list(ARTICLES_ROOT.glob("article-*.md")), "articles must not sit at the store root"


def test_every_fetched_version_has_a_declared_article_count():
    """A version fetched but not listed above would skip the count check entirely."""
    fetched = {p.name for p in ARTICLES_ROOT.iterdir() if p.is_dir()}
    undeclared = sorted(fetched ^ set(ARTICLE_COUNTS))
    assert fetched == set(ARTICLE_COUNTS), f"undeclared versions: {undeclared}"


# A fetched version that no ledger covers, listed with the reason it is not covered yet. Same
# discipline as the coverage ledger one level up: the store may hold a version the ruleset has not
# migrated to, but never silently.
UNTRIAGED_VERSIONS: dict[str, str] = {}
"""Empty, and the mechanism stays for the next refresh.

It is where a freshly fetched version sits: in the repo and reviewable, with no claim that the
ruleset has been checked against it. A version leaves this dict by gaining a ledger, and the
coverage guarantee below then holds it to the spec — so an entry here alongside a ledger is a
contradiction the test rejects rather than a redundancy it tolerates."""


def test_every_fetched_version_is_covered_or_declared_untriaged():
    """A version in the store either has a coverage ledger or is named above with a reason.

    Fetching is not adopting. The store is version-scoped precisely so a newer text can sit beside
    the pinned one while its changes are reviewed — but an untriaged store looks exactly like a
    current one from the outside, and a reader who assumed the newer directory was in force would
    be reading law the ruleset never checked against."""
    fetched = {p.name for p in ARTICLES_ROOT.iterdir() if p.is_dir()}
    covered = {
        p.name.removeprefix("scope-").removesuffix(".yaml")
        for p in SPEC_PATH.parent.glob("scope-*.yaml")
    }

    overlap = covered & set(UNTRIAGED_VERSIONS)
    assert not overlap, f"versions both given a ledger and declared untriaged: {sorted(overlap)}"

    unclassified = fetched - covered - set(UNTRIAGED_VERSIONS)
    assert not unclassified, (
        f"Article-store versions with no coverage ledger and no untriaged entry: "
        f"{sorted(unclassified)}. Triage them or declare them."
    )
    assert VERSION in covered, "the version the spec pins must have a ledger"


@pytest.mark.parametrize(
    "version",
    sorted(p.name for p in ARTICLES_ROOT.iterdir() if p.is_dir() and p.name >= VERSION),
)
def test_every_article_is_classified_in_scope_or_out(version):
    """THE COVERAGE GUARANTEE. Every article is either cited by a rule or explicitly out of scope.
    A new article in a future Act version is neither -> this fails -> a human must rule on it.
    That is how a newly legislated obligation cannot silently go unchecked.

    Run against the pinned version and every version AFTER it, not only the pinned one. A version
    the ruleset has not adopted YET is exactly where an unruled article hides: it is in the repo, it
    looks authoritative and nothing else reads it. Checking it here is what makes repointing the pin
    a decision rather than a discovery. Article NUMBERS are version-independent, so the citations in
    spec.yaml are meaningful against a store the spec does not currently resolve from.

    A SUPERSEDED version is skipped, and that is the whole of the difference. Its ledger records how
    the ruleset stood against a text no longer in force, so holding it to today's spec makes every
    new rule a reason to edit a file nobody consults — the ledger's own claims stop being read and
    start being satisfied. A superseded store is therefore kept only while something else still
    pins it, and deleted when nothing does. Only the pinned version is in the store today, so the
    comparison selects everything; it earns its keep at the next refresh, when a newer text lands
    beside this one and must be ruled on before the pin moves.

    An entry's SHAPE says how much of the article it rules out: a string excludes the whole article,
    a mapping excludes named divisions of an article a rule does cite. The two are checked against
    opposite expectations — a cited article may not be excluded whole, and an uncited one has no
    divisions worth enumerating."""
    spec = _spec()
    scope_path = SPEC_PATH.parent / f"scope-{version}.yaml"
    ledger = yaml.safe_load(scope_path.read_text(encoding="utf-8"))
    assert str(ledger["act_version_date"]) == version

    # str, not int: a consolidation inserts LETTERED articles (4a, 60a, 75a-75d), and int() both
    # crashes on them and would collapse 4a onto 4. A rule's own label is already a string; the
    # ledger's keys come from YAML and are not.
    in_store = {p.stem.removeprefix("article-").lstrip("0") for p in
                (ARTICLES_ROOT / version).glob("article-*.md")}
    cited = {r.source.article for r in spec.rules}
    entries = {str(k): v for k, v in ledger["article_rulings"].items()}
    whole = {k for k, v in entries.items() if isinstance(v, str)}
    by_division = {k for k, v in entries.items() if isinstance(v, dict)}
    awaiting = {str(k) for k in ledger.get("articles_awaiting_rules", {})}

    overlap = cited & whole
    assert not overlap, f"articles both cited and marked out of scope whole: {sorted(overlap)}"

    contradiction = whole & awaiting
    assert not contradiction, (
        f"articles ruled out WHOLE and also awaiting a rule: {sorted(contradiction)}. If part of "
        f"an article is owed, the exclusion covers the rest of it division by division."
    )

    # ANY article may be broken down, cited or not. That is the direction of travel: a string entry
    # dismisses every paragraph inside an article on one line, and twice now a real duty has been
    # sitting in one — Art. 8(2), then Art. 41(5) and Art. 71(2)-(3). Itemising is how an entry
    # stops being a blanket, so nothing here discourages it; `test_the_blanket_only_shrinks` counts
    # what is left.
    unclassified = in_store - cited - whole - by_division
    assert not unclassified, (
        f"Articles present in the store but neither cited by a rule nor listed in "
        f"{scope_path.name}: {sorted(unclassified)}. Rule on them before shipping."
    )

    phantom = (whole | by_division) - in_store
    assert not phantom, f"classified articles that do not exist in the store: {sorted(phantom)}"


# A paragraph ruling that hands the provision to the classification cascade rather than to a rule
# names the node that consumes it, so the claim is checkable instead of decorative.
_CASCADE_PREFIX = "CASCADE "


def _cascade_nodes() -> set[str]:
    return set(QUESTIONS) | {role_questions.NODE_ID, role_questions.DEPLOYER_NODE_ID}


def _assert_reasons(section: dict) -> None:
    """Nothing is dismissed by bare assertion, at either depth.

    Handles both entry shapes: a string ruling out a whole article, and a mapping ruling out named
    divisions of one."""
    for article, value in section.items():
        divisions = value.items() if isinstance(value, dict) else [(None, value)]
        for division, reason in divisions:
            where = f"Article {article}" + (f"({division})" if division is not None else "")
            assert isinstance(reason, str) and len(reason.strip()) > 15, (
                f"{where} is dismissed without a real reason"
            )


def test_articles_awaiting_rules_have_reasons():
    """The same discipline over the bucket that admits a duty is going unreported."""
    ledger = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
    _assert_reasons(ledger["articles_awaiting_rules"])


@pytest.mark.parametrize("key", ["annex_rulings", "annexes_awaiting_rules"])
def test_annex_rulings_have_reasons(key):
    """And over the annex buckets, at both depths — an annex ruled on whole, and one ruled on item
    by item. Annex II is the only one left in the first shape; the text does not divide it."""
    ledger = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
    _assert_reasons(ledger[key])


@pytest.mark.parametrize("version", sorted(p.name for p in ARTICLES_ROOT.iterdir() if p.is_dir()))
def test_article_rulings_entries_have_reasons(version):
    """Both ledgers, and both shapes of entry. A reason copied forward onto an amended article
    without being re-read is the failure this file already caught once, when "employment
    self-assesses, so no notified body" survived Art. 43(1) landing."""
    scope_path = SPEC_PATH.parent / f"scope-{version}.yaml"
    ledger = yaml.safe_load(scope_path.read_text(encoding="utf-8"))
    _assert_reasons(ledger["article_rulings"])


def test_every_requirement_is_literal_article_text():
    """Each rule's requirement must be the verbatim text of the cited provision, as stored in the
    article files. This is the guarantee against paraphrase creeping back in."""
    spec = _spec()
    for r in spec.rules:
        article_file = ARTICLES_DIR / article_filename(r.source.article)
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
    whole, _ = resolve_requirement(ARTICLES_DIR, "43", None)
    para2, _ = resolve_requirement(ARTICLES_DIR, "43", "2")
    assert para2.startswith("For high-risk AI systems referred to in points 2 to 8 of Annex III")
    assert para2 in re.sub(r"\s+", " ", whole) or para2 in whole
    assert len(para2) < len(whole)


def test_resolve_point_of_an_article_without_paragraphs():
    """Art. 16 is a chapeau plus points (a)-(l) and has no numbered paragraphs, so a rule that
    wants one duty out of it has to cite the point. Citing the article resolves to all twelve."""
    point_b, _ = resolve_requirement(ARTICLES_DIR, "16", None, point="b")
    whole, _ = resolve_requirement(ARTICLES_DIR, "16", None)
    assert point_b.startswith("(b) indicate on the high-risk AI system")
    assert point_b.endswith("the address at which they can be contacted;")
    assert point_b in whole
    assert "(c) have a quality management system" not in point_b


def test_resolve_point_within_a_paragraph():
    para, _ = resolve_requirement(ARTICLES_DIR, "9", "2")
    point_a, _ = resolve_requirement(ARTICLES_DIR, "9", "2", point="a")
    assert point_a in para
    assert len(point_a) < len(para)


def test_resolve_ambiguous_point_raises():
    """Art. 9 has an (a) under paragraph 2 and another under paragraph 5. Resolving to the first
    would cite one duty and quote another, which is the failure this whole loader exists to stop."""
    with pytest.raises(ValueError, match=r"2 points labelled \(a\)"):
        resolve_requirement(ARTICLES_DIR, "9", None, point="a")


def test_resolve_unknown_point_raises():
    with pytest.raises(ValueError, match=r"no point \(z\)"):
        resolve_requirement(ARTICLES_DIR, "16", None, point="z")


def test_resolve_unknown_paragraph_raises():
    with pytest.raises(ValueError, match="no paragraph 99"):
        resolve_requirement(ARTICLES_DIR, "9", "99")


def test_resolve_missing_article_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="No article file"):
        resolve_requirement(tmp_path, "9", None)


def test_resolve_rejects_version_mismatch():
    """Closes the silent-drift hole: resolving a rule against an article fetched for a DIFFERENT
    act version would swap the requirement's meaning while the spec still claims the old pin."""
    with pytest.raises(ValueError, match="Refusing to resolve requirement text across versions"):
        resolve_requirement(ARTICLES_DIR, "9", None, expected_version="2026-08-02")


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
    """The Art. 16+ family is confirm-separately, never silently flagged as gaps — with one
    exception, named here so adding another has to be argued for rather than typed.

    Art. 16(b) is document-verifiable because the Act says so: the provider's identification may be
    discharged on the accompanying documentation, which is the file under review. Every other rule
    in this family is a process at the provider or a duty under law this tool does not read, and
    checking a document for it would manufacture gaps out of a scope limit."""
    spec = _spec()
    process = [r for r in spec.rules if r.rule_id.startswith("AIA-PO-")]
    assert process, "expected provider process obligations in the spec"
    checkable = {r.rule_id for r in process if r.document_verifiable}
    assert checkable == {"AIA-PO-A16-B"}


def test_high_risk_requirements_are_document_verifiable():
    spec = _spec()
    # Ten: Arts. 9 to 15 whole, plus the three paragraphs a whole-article citation does not reach —
    # Art. 11(2)'s single documentation set, Art. 12(3)'s biometric logging minimum and Art. 13(3)'s
    # instructions-for-use contents, each judged on its own terms.
    reqs = [r for r in spec.rules if r.rule_id.startswith("AIA-HR-")]
    assert len(reqs) == 10
    assert all(r.document_verifiable for r in reqs)


# A term the Act coined for itself, in the shape it coins them: a parenthesis naming the thing the
# sentence before it just described. `(feedback loops)`, `(automation bias)`, `(data poisoning)`.
# Two or more words, so a bare point label `(a)` and a cross-reference `(EU)` are not terms.
_COINED = re.compile(r"\((?:‘)?([a-z][a-z]*(?: [a-z-]+)+)(?:’)?\)")

# A NAME IS A NOUN PHRASE. Past this length the parenthesis is not a name for what precedes it but
# an expansion of it — Art. 12(3)(a)'s "(start date and time and end date and time of each use)"
# spells out the period the same sentence already required, and demanding it verbatim would ask a
# rule to quote the Act rather than describe the documentation. The longest name in the stored Act
# is Art. 15(5)'s "adversarial examples or model evasion".
_NAME_WORDS = 5


def test_a_term_the_act_coins_reaches_the_judge_that_searches_for_it():
    """Where the Act names a risk, the rule judging that article must name it too.

    `tools.evidence.query_for` returns `evidence_expected`, so that text is not only the
    instruction to the judge — it is the RETRIEVAL QUERY. A term missing from it is missing twice:
    the judge is not told to look for the thing, and the passages that would show it are not among
    the ones retrieved. The second loss is the worse one, because the prompt tells the judge to
    read absence from the excerpts as absence from the document.

    THE ACT'S OWN PARENTHESES ARE THE DERIVATION, not a list anyone maintains. Where the drafter
    put a name in brackets after describing something — "the risk of possibly biased outputs
    influencing input for future operations (feedback loops)" — that name is what a technical file
    will call it, which makes it exactly the token the query needs and the one a compressed
    evidence text drops first. Only judged rules: an unjudged rule's evidence text is rendered to a
    reader and searches for nothing.

    Silent on terms the Act does not bracket, and that limit is real — Art. 14(5)'s "two natural
    persons" is a hard requirement written in plain prose and no test derives it. This catches the
    class the text marks for itself."""
    for rule in _spec().rules:
        if not rule.document_verifiable:
            continue
        expected = rule.evidence_expected.lower()
        missing = sorted(
            {
                t
                for t in _COINED.findall(rule.requirement)
                if len(t.split()) <= _NAME_WORDS and t.lower() not in expected
            }
        )
        assert not missing, (
            f"{rule.rule_id} is judged on Art. {rule.source.article}, which coins {missing}, and "
            f"its evidence_expected names none of them. That text is the retrieval query: "
            f"documentation breaching the named risk is not retrieved, and the judge is told to "
            f"treat what it was not shown as absent from the document."
        )


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


# A PARAGRAPH that names one of the roles this tool reports for and states an obligation. Scoped to
# the paragraph rather than the sentence, and deliberately crude in both halves.
#
# Sentence scope was the first attempt and it under-matched: splitting on ". " breaks at "Art. 5"
# and "No 300/2008", so a duty whose subject and verb land either side of a citation went unseen.
# It missed Art. 41(5) and Art. 71(2)-(3), all three real duties. Paragraph scope over-matches
# instead, which is the right direction — a false positive costs one line of writing here, a miss
# costs a false PASS in a report.
_DUTY_ROLE = re.compile(
    r"\b(provider|deployer|importer|distributor|authorised representative"
    r"|operator|product manufacturer)s?\b",
    re.I,
)
_DUTY_VERB = re.compile(r"\b(shall|must|required to|obliged to|responsible for)\b", re.I)

# Articles ruled out WHOLE whose text nevertheless names a role this tool reports for beside an
# obligation, each with the reason no rule follows. THIS IS THE LIST THE SCREEN BELOW FREEZES: an
# article that starts bearing a duty and is not named here fails, and a human rules on it.
#
# ONE ENTRY LEFT, because the screen is a substitute for reading and the ledger now rules on every
# article paragraph by paragraph — a stronger claim than a whole-article dismissal a regex agreed
# with. Art. 94 stays because the text gives it no divisions to itemise. The screen stays because
# the failure it guards against is an itemised article collapsed back to one line: the ledger's
# blanket count would notice, and so would the stale half of this test.
DUTY_BEARING_EXCLUSIONS: dict[str, str] = {
    "94": "Procedural rights of GPAI economic operators. Rights against the enforcing body, not "
          "duties owed under the Regulation. The Article has no divisions to itemise.",
}


def test_a_wholly_excluded_article_holds_no_unacknowledged_duty():
    """THE GUARANTEE THE PARAGRAPH PARTITION CANNOT GIVE.

    Divisions are enumerated only for articles a rule cites. An article ruled out WHOLE is dismissed
    in one sentence and never itemised, so a duty inside one is invisible to every other check here
    — several hundred paragraphs sit inside the articles excluded that way.

    This screens all of them: any paragraph naming a role this tool reports for beside an obligation
    verb. Every hit must be named above with the reason no rule follows from it.

    Stale entries fail too. An article that stops bearing a duty — the legislator amends it, or the
    ruleset starts citing it — should lose its entry rather than keep a dismissal for text that is
    no longer there. That half is what caught Arts. 41 and 71 being split off."""
    ledger = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
    whole = [str(k) for k, v in ledger["article_rulings"].items() if isinstance(v, str)]

    flagged = set()
    for article in whole:
        number = int(re.match(r"\d+", article).group())
        suffix = article[len(str(number)):]
        path = ARTICLES_DIR / f"article-{number:03d}{suffix}.md"
        body = path.read_text(encoding="utf-8").split("---", 2)[2]
        bounds = [m.start() for m in _PARAGRAPH_START.finditer(body)] or [0]
        bounds.append(len(body))
        for i in range(len(bounds) - 1):
            paragraph = body[bounds[i]:bounds[i + 1]].replace("\n", " ")
            if _DUTY_ROLE.search(paragraph) and _DUTY_VERB.search(paragraph):
                flagged.add(article)
                break

    undeclared = flagged - set(DUTY_BEARING_EXCLUSIONS)
    assert not undeclared, (
        f"Articles ruled out WHOLE that name a role this tool reports for beside an obligation, "
        f"with no reason recorded: {sorted(undeclared)}. Rule on each — either the duty needs a "
        f"rule, or say in DUTY_BEARING_EXCLUSIONS why it does not."
    )

    stale = set(DUTY_BEARING_EXCLUSIONS) - flagged
    assert not stale, (
        f"Declared as duty-bearing but no longer are: {sorted(stale)}. Drop the entry rather than "
        f"leave a dismissal standing for text that is not there."
    )

    for article, reason in DUTY_BEARING_EXCLUSIONS.items():
        assert len(reason.strip()) > 15, f"Article {article} is dismissed without a real reason"
