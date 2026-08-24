"""THE PARTITION. Every piece of the enacted text, and the one thing that accounts for it.

This is the file that answers "is anything in the Act unaccounted for?" — not by anyone's
assurance, but by enumerating the stored text and requiring each address to resolve to a rule, a
cascade node, a written reason, or a declared debt.

The number that matters is BLANKET: a provision nobody ruled on, wearing a ruling made about the
article or annex around it. It is not an error and it is not coverage either, and every duty this
ruleset has been found to miss was sitting inside one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from aiact.classify.graph import _QUESTION_CONTEXT, QUESTIONS, load_questions
from aiact.config import get_settings
from aiact.coverage import (
    CASCADE_PREFIX,
    RULE_PREFIX,
    Status,
    cascade_nodes,
    classify_coverage,
    rule_ids,
    summarise,
)
from aiact.gap import roles as role_questions
from aiact.gap.rules import select_rules
from aiact.policy_loader import load_policy_spec, resolve_requirement
from aiact.provisions import all_provisions, annex_instruments, provision_labels
from aiact.schemas.classification import ClassificationEvidence, UseCaseClassification
from aiact.schemas.enums import ActorRole, AnnexIIIArea, DerogationCondition, RiskClass
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Answer

ROOT = Path(__file__).resolve().parents[1]
VERSION = get_settings().act_version_date.isoformat()
SPEC_PATH = ROOT / "data" / "policy" / "spec.yaml"
ARTICLES_ROOT = ROOT / "data" / "policy" / "articles"
ARTICLES_DIR = ARTICLES_ROOT / VERSION
ANNEXES_DIR = ROOT / "data" / "policy" / "annexes" / VERSION
SCOPE_PATH = ROOT / "data" / "policy" / f"scope-{VERSION}.yaml"

# Provisions covered by a ruling made about the whole article or annex around them, rather than by
# one written for them. ZERO: all 789 addresses of the stored text are ruled on individually.
# Declared as a constant rather than asserted as zero so the failure reads as a number that moved —
# new text arriving, a parser fix making a division visible, or an itemised article collapsed back
# to a one-line dismissal — and so paying it down again is one edit.
BLANKET_PROVISIONS = 0

# Provisions a party owes and no report mentions, declared as a debt in `articles_awaiting_rules`
# or `annexes_awaiting_rules`. ZERO: every duty the Act puts on a role this tool reports for is
# carried by a rule, on the Art. 6 track and in Chapter V alike.
#
# Held as a constant for the reason the blanket count is, and the reason is stronger here: an
# UNPAID debt is the one status that admits a reader will be told nothing about a duty they have.
# Going up means a new duty was found, or new text arrived — both worth a decision rather than a
# silent entry in a file nobody re-reads.
OWED_PROVISIONS = 0


@pytest.fixture(scope="module")
def spec():
    return load_policy_spec(SPEC_PATH, ARTICLES_ROOT)


@pytest.fixture(scope="module")
def ledger():
    return yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))


def _comment_above(key: object) -> str:
    """The comment block written immediately above `key:` in the ledger, or "" if there is none.

    The ledger argues a whole-annex debt in a heading comment and describes the individual items
    in the values, so a test asking what the ledger SAYS about an annex has to read both.
    `yaml.safe_load` drops comments, which is why this reads the file rather than the mapping."""
    lines = SCOPE_PATH.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith(f"{key}:"):
            block = []
            cursor = index - 1
            while cursor >= 0 and lines[cursor].strip().startswith("#"):
                block.append(lines[cursor])
                cursor -= 1
            return "\n".join(reversed(block))
    return ""


@pytest.fixture(scope="module")
def used_annexes(spec):
    """Annexes some part of the tool reads — cited by a rule, or supplied to the cascade."""
    annexes = {r.source.annex for r in spec.rules if r.source.annex}
    return annexes | {a for _articles, ann in _QUESTION_CONTEXT.values() for a in ann}


@pytest.fixture(scope="module")
def covered(spec, ledger, used_annexes):
    return classify_coverage(spec, ledger, ARTICLES_DIR, ANNEXES_DIR, used_annexes)


def test_nothing_in_the_act_is_unaccounted_for(covered):
    """Every address resolves to something. UNACCOUNTED is the failure state of the partition.

    It fires when a provision is neither ruled on nor inherits a ruling — a new annex item, an
    article the ledger forgot, a division a parser fix has just made visible for the first time.
    None of those should reach a report without a human deciding what they mean."""
    orphans = [str(c.provision) for c in covered if c.status is Status.UNACCOUNTED]
    assert not orphans, (
        f"{len(orphans)} provisions nothing accounts for: {orphans[:20]}. "
        f"Rule on each, or record the article/annex they sit in."
    )


def test_the_blanket_only_shrinks(covered):
    """THE ANSWER TO "how do I know every paragraph was actually read?"

    By counting the ones that were not. A blanket is a ruling written about a document and applied
    to every provision inside it, so it says nothing about any of them individually — and a duty
    hiding under one is invisible to every other check here.

    Going DOWN means a chapter was read; lower the constant. Going UP means an itemised article was
    collapsed back to a one-line dismissal, or new text arrived that nobody has read."""
    actual = summarise(covered)[Status.BLANKET]
    assert actual == BLANKET_PROVISIONS, (
        f"{actual} provisions are covered by a blanket, declared {BLANKET_PROVISIONS}. "
        f"Down means progress — lower the constant. Up needs explaining."
    )


def test_the_declared_debt_only_shrinks(covered):
    """What is owed and unreported, counted rather than described.

    `articles_awaiting_rules` and `annexes_awaiting_rules` are the honest half of the ledger: an
    entry says a party owes something and this tool's report is silent about it. That is a stronger
    claim than a dismissal, which is why the sections are separate from the rulings — and why
    emptying them is work rather than editing.

    Down means a rule was written; lower the constant. UP MEANS A READER IS NOW BEING TOLD NOTHING
    about a duty they have, which is the failure this whole partition exists to surface."""
    owed = [str(c.provision) for c in covered if c.status is Status.OWED]
    assert len(owed) == OWED_PROVISIONS, (
        f"{len(owed)} provisions are owed a rule, declared {OWED_PROVISIONS}: {owed[:20]}. "
        f"Down means progress — lower the constant. Up needs a rule, or an argument."
    )


def test_every_ruling_names_something_that_exists(covered, spec):
    """A status with nothing behind it is not a claim anyone can check.

    CHECKED must name a rule in the shipped spec. ASKED must name a node in the graph that actually
    runs — "the cascade handles it" is only an answer if some node does, and nothing reads
    Art. 6(1c). NOT_OWED and OWED must carry a reason long enough to be an argument."""
    rules = {r.rule_id for r in spec.rules}
    nodes = set(QUESTIONS) | {role_questions.NODE_ID, role_questions.DEPLOYER_NODE_ID}
    for entry in covered:
        where = str(entry.provision)
        if entry.status is Status.CHECKED:
            # Every rule named, because a ruling may name several and each is its own claim.
            unknown = [rule_id for rule_id in entry.detail.split() if rule_id not in rules]
            assert not unknown, f"{where} cites rule(s) {unknown}, which do not exist"
        elif entry.status is Status.ASKED:
            # Every node named, because a ruling may name several and each is its own claim.
            unknown = [node for node in entry.detail.split() if node not in nodes]
            assert not unknown, (
                f"{where} is handed to cascade node(s) {unknown}, which do not exist. "
                f"Known nodes: {sorted(nodes)}"
            )
        elif entry.is_individual:
            assert len(entry.detail.strip()) > 15, f"{where} is ruled on without a real reason"


def test_a_provision_is_never_ruled_on_twice(ledger):
    """The two ledger sections mean different things, so an address in both is a contradiction.

    `article_rulings` says how a provision is accounted for — checked by a rule, asked by a node, or
    not owed. `articles_awaiting_rules` says a party owes it and no report mentions it. Whichever
    the partition happened to resolve first would silently win."""
    for ruled_key, owed_key in (
        ("article_rulings", "articles_awaiting_rules"),
        ("annex_rulings", "annexes_awaiting_rules"),
    ):
        ruled, owed = ledger[ruled_key], ledger[owed_key]
        for document, value in (owed or {}).items():
            other = (ruled or {}).get(document)
            if isinstance(value, dict) and isinstance(other, dict):
                clash = {str(k) for k in value} & {str(k) for k in other}
                assert not clash, (
                    f"{ruled_key} {document}: divisions ruled on AND owed: {sorted(clash)}"
                )
            elif other is not None and not isinstance(value, dict):
                pytest.fail(f"{document} is both ruled on in {ruled_key} and owed a rule")


def test_the_ledger_rules_on_nothing_that_does_not_exist(ledger):
    """A ruling addressed to a provision the text does not contain is dead weight that reads as
    coverage. It happens when an amendment renumbers, or when an address is mistyped."""
    real = {(c.kind, c.document, c.division) for c in all_provisions(ARTICLES_DIR, ANNEXES_DIR)}
    documents = {(kind, document) for kind, document, _division in real}
    sections = (
        ("article", "article_rulings"),
        ("article", "articles_awaiting_rules"),
        ("annex", "annex_rulings"),
        ("annex", "annexes_awaiting_rules"),
    )
    for kind, section in sections:
        for document, value in (ledger.get(section) or {}).items():
            assert (kind, str(document)) in documents, (
                f"{section} rules on {kind} {document}, which is not in the store"
            )
            for division in value if isinstance(value, dict) else ():
                assert (kind, str(document), str(division)) in real, (
                    f"{section} rules on {kind} {document}({division}), which does not exist"
                )


def test_a_provision_a_rule_checks_is_not_also_ruled_out(covered):
    """CHECKED wins the resolution order, so a contradiction here would resolve silently in favour
    of the rule and leave a written dismissal standing for a duty the tool does report."""
    checked = {str(c.provision) for c in covered if c.status is Status.CHECKED}
    dismissed = {str(c.provision) for c in covered if c.status is Status.NOT_OWED}
    assert not (checked & dismissed)


def test_the_partition_covers_the_whole_store(covered):
    """Sanity on the join itself: one entry per provision, no more and no fewer."""
    provisions = all_provisions(ARTICLES_DIR, ANNEXES_DIR)
    assert len(covered) == len(provisions)
    assert [c.provision for c in covered] == provisions


def test_the_ledger_defines_nothing_twice():
    """A DUPLICATE KEY IS SILENT, and that is what makes it dangerous here.

    PyYAML keeps the last definition and discards the earlier one without a word, so a ledger can
    carry two contradictory rulings for the same provision while every other test in this file
    passes — they all read the parsed mapping, which by then holds only one of them. The ruling a
    reviewer reads and the ruling the partition applies would be different sentences.

    Parsed from the TEXT rather than from the loaded mapping, because the loaded mapping is exactly
    what cannot show the problem."""
    key = re.compile(r"^  ([\"']?[0-9A-Za-z]+[\"']?):")
    section, seen, clashes = None, {}, []
    for line in SCOPE_PATH.read_text(encoding="utf-8").splitlines():
        if re.match(r"^[a-z_]+:", line):
            section = line.split(":")[0]
            seen[section] = set()
            continue
        match = key.match(line)
        if match and section:
            name = match.group(1).strip("\"'")
            if name in seen[section]:
                clashes.append(f"{section}: {name}")
            seen[section].add(name)
    assert not clashes, f"the ledger defines these twice, and YAML keeps only the last: {clashes}"


def test_the_annex_i_rulings_name_the_instrument_the_annex_names(ledger):
    """THE ONE CHECK ON THE PROSE BESIDE A KEY, rather than on the key.

    Every other check in this file compares ADDRESSES: `test_the_ledger_rules_on_nothing_that_does_
    not_exist` matches keys against the store, `_assert_reasons` measures a reason's length, and
    `test_every_annex_i_instrument_has_a_name_in_the_code` compares item keys to enum members. A
    ruling can name the wrong law entirely and satisfy all three — and Annex I is where that costs
    something, because two adjacent items (B/14, B/15) govern different vehicle Regulations and two
    more (A/1, B/21) govern machinery under instruments on opposite sides of Art. 2(2).

    So the instrument is DERIVED: the first OJ citation inside an Annex I item is the act that item
    enacts, and the ruling written for that item must name it."""
    instruments = annex_instruments(ANNEXES_DIR, "I")

    rulings = ledger["annex_rulings"]["I"]
    assert set(rulings) == set(instruments), (
        f"the ledger and the Annex disagree on which items exist: "
        f"{sorted(set(rulings) ^ set(instruments))}"
    )
    wrong = {
        item: (instrument, rulings[item])
        for item, instrument in instruments.items()
        if instrument not in str(rulings[item])
    }
    assert not wrong, (
        f"Annex I rulings naming an instrument the Annex does not put at that item: "
        f"{ {k: v[0] for k, v in wrong.items()} }. The Annex is authoritative."
    )


def test_every_definition_the_ledger_hands_to_a_node_reaches_it(ledger):
    """"CASCADE <node>" MUST MEAN THE NODE IS GIVEN THE PROVISION, not merely that the node exists.

    `test_every_ruling_names_something_that_exists` checks the node id resolves. That is the weaker
    half of the claim: a definition can be ruled `CASCADE prohibited` while the `prohibited` node is
    handed Art. 5 and nothing else, leaving the question to be answered from a paraphrase in the
    prompt. Art. 3's definitions are where that costs something, because each carries a qualifier a
    paraphrase drops — 3(42)'s "limited short delays", 3(44)'s "publicly OR PRIVATELY owned",
    3(40)'s "ancillary to another commercial service" exception.

    So the ledger's own claim is read back against what `load_questions` actually builds: for every
    Art. 3 point ruled to a node, that node's context must contain the definition's text.

    EVERY node the ruling names, not the first. A term can decide more than one question — 3(14)
    settles Art. 6(1)(a) at `annex_i` and Annex III(2) at `annex_iii` — and a ruling that lists two
    nodes while only one holds the text is the same defect as a ruling that lists one node holding
    none."""
    questions = load_questions()
    definitions = {
        str(division): str(reason)
        for division, reason in (ledger["article_rulings"].get(3) or {}).items()
    }
    assert definitions, "Art. 3 is no longer itemised in the ledger — re-derive this test"

    missing: dict[str, list[str]] = {}
    for point, reason in definitions.items():
        if not reason.startswith(CASCADE_PREFIX):
            continue
        nodes = cascade_nodes(reason)
        text, _url = resolve_requirement(ARTICLES_DIR, "3", None, point=point)
        # A node id that does not resolve is `test_every_ruling_names_something_that_exists`'s
        # claim, and reporting it here as well would say the supply is missing when the address is.
        absent = [n for n in nodes if n in questions and text.strip() not in questions[n].context]
        if absent:
            missing[f"Art. 3({point})"] = absent
    assert not missing, (
        f"definitions the ledger hands to a node that never sees them: {missing}. Supply the point "
        f"in _QUESTION_DEFINITIONS, or rule the definition on some other ground."
    )


def test_every_borrowed_definition_names_the_instrument_it_is_borrowed_from(ledger):
    """A CROSS-REFERENCE IS NOT A MEANING, and the ledger must say which of the two it ruled on.

    Six of Art. 3's definitions define nothing themselves: 3(52) is "profiling as defined in
    Article 4, point (4), of Regulation (EU) 2016/679", and that is the whole point. None of those
    instruments is in `data/policy/`, so a node handed such a point receives a pointer — the
    operative words are still whatever gloss the question happens to carry, which nothing here can
    check against a stored document.

    `test_every_definition_the_ledger_hands_to_a_node_reaches_it` counts these as supplied, and on
    its own terms it is right: the Act's text does reach the node. This test bounds that claim.
    Making a borrowed meaning checkable needs the instrument in the corpus; what this does instead
    is put the borrowing in the ruling, so a reader of the ledger can tell a definition that was
    read from one that was pointed at.

    DERIVED: the borrowings are found by reading Art. 3, not listed here."""
    borrowed = re.compile(
        r"as (?:defined|referred to) in [^;]*?((?:Regulation|Directive)[^;,]*?)(?:[;,]|$)"
    )
    rulings = {
        str(division): str(reason)
        for division, reason in (ledger["article_rulings"].get(3) or {}).items()
    }
    silent: dict[str, str] = {}
    found = 0
    for point in provision_labels(ARTICLES_DIR, "3"):
        text, _url = resolve_requirement(ARTICLES_DIR, "3", None, point=point)
        body = text.split("\n")[0]
        match = borrowed.search(body)
        # A long body defines the term itself and merely cites an instrument in passing; only a
        # definition that is ALL cross-reference borrows its meaning whole.
        if match is None or len(body) >= 420:
            continue
        found += 1
        instrument = match.group(1).strip()
        if instrument not in rulings.get(point, ""):
            silent[f"Art. 3({point})"] = instrument
    assert found >= 5, f"Art. 3's borrowed definitions no longer parse ({found}) — re-derive this"
    assert not silent, (
        f"definitions that borrow their meaning from an instrument this corpus does not hold, "
        f"ruled on without naming it: {silent}. Name the instrument in the ruling — a reader of "
        f"the ledger cannot otherwise tell a definition that was read from one that was pointed at."
    )


def test_every_annex_item_a_rule_checks_is_supplied_to_that_rule(ledger, spec):
    """"RULE <id>" ON AN ANNEX ITEM MUST MEAN THE RULE CARRIES THAT ANNEX.

    The sibling of `test_every_definition_the_ledger_hands_to_a_node_reaches_it`, for the
    obligation layer. `requirement` resolves from `source.article`/`paragraph`/`point` only, so an
    Article that POINTS AT an annex — Art. 11(1): documentation containing "at a minimum, the
    elements set out in Annex IV" — resolves to the pointer and not the list. A `completeness`
    verdict reached that way asks a judge to find every element of something nobody showed it.

    `source.annex` is what closes it: the loader injects that Annex verbatim into `annex_context`.
    So a ledger entry claiming a rule checks an annex item is only true where the rule cites THAT
    annex.

    WHAT THIS DOES NOT PROVE: that a judge reads the annex, which is a separate and narrower
    claim. `annex_context` reaches a prompt only for a `document_verifiable` rule —
    otherwise the judge returns NOT_APPLICABLE before building one. Annex IV, through AIA-HR-A11,
    is the only annex any judge is shown. Annexes V and VI and VIII are ruled on by rules that are
    not verifiable, because a declaration of conformity, a conformity assessment procedure and a
    database entry are none of them the file under review — so for those items the claim this test
    enforces is that the rule carries the annex and states what the item requires, not that
    anything has read it against a document."""
    by_id = {r.rule_id: r for r in spec.rules}
    unsupplied: dict[str, str] = {}
    for annex, value in (ledger["annex_rulings"] or {}).items():
        for item, reason in (value if isinstance(value, dict) else {}).items():
            text = str(reason)
            if not text.startswith(RULE_PREFIX):
                continue
            rule_id = text[len(RULE_PREFIX) :].split()[0].rstrip(",:—")
            rule = by_id[rule_id]
            if rule.source.annex != str(annex) or not rule.annex_context:
                unsupplied[f"Annex {annex}({item})"] = (
                    f"{rule_id} cites annex {rule.source.annex!r}"
                )
    assert not unsupplied, (
        f"annex items claimed as checked by a rule that is never shown that annex: {unsupplied}. "
        f"Cite the annex on the rule, or declare the items in annexes_awaiting_rules."
    )


def test_every_provision_a_rule_is_qualified_by_reaches_that_rule(ledger, spec):
    """A QUALIFIER RULED ON MUST BE ONE THE JUDGE IS SHOWN, not one a rule merely points near.

    The third of the supply guards, after the cascade definitions and the annex items. A provision
    can be ruled CHECKED by rules that do not cite it at all — Art. 50(5) is checked by the four
    Art. 50 rules, none of which has 5 as its `source.paragraph`, and Art. 4a(1) by a rule for a
    different Article entirely. `qualified_by` is what makes those rulings true: it resolves the
    provision at load and the judge prompt carries it in its own block. Without it the ruling names
    a rule whose prompt has never contained the text.

    So for every division ruled `RULE <ids>` where no named rule CITES it, each of those rules must
    name it in `qualified_by` and carry a non-empty `qualifier_context`."""
    by_id = {r.rule_id: r for r in spec.rules}
    unsupplied: dict[str, str] = {}
    checked = 0
    for article, value in (ledger["article_rulings"] or {}).items():
        for division, reason in (value if isinstance(value, dict) else {}).items():
            text = str(reason)
            if not text.startswith(RULE_PREFIX):
                continue
            for rule_id in rule_ids(text):
                rule = by_id[rule_id]
                # `str()` on the LEDGER side only: its keys come from YAML and are integers,
                # while a rule's labels are strings by construction — see LegalSource.article.
                cites = rule.source.article == str(article) and (
                    rule.source.paragraph is None or rule.source.paragraph == str(division)
                )
                if cites:
                    continue
                checked += 1
                qualifies = any(
                    q.get("article") == str(article) and q.get("paragraph") == str(division)
                    for q in rule.qualified_by
                )
                if not qualifies or not rule.qualifier_context:
                    unsupplied[f"Art. {article}({division}) via {rule_id}"] = (
                        f"qualified_by={rule.qualified_by}"
                    )
    assert checked >= 5, f"no cross-article rulings left to check ({checked}) — re-derive this"
    assert not unsupplied, (
        f"provisions ruled as checked by a rule that neither cites nor is qualified by them: "
        f"{unsupplied}. Add the provision to that rule's `qualified_by`, or rule it on some other "
        f"ground."
    )


def test_an_annex_declared_owed_engages_with_any_rule_that_cites_it(ledger, spec):
    """THE OTHER DIRECTION, and it is the one that misreports a debt rather than a coverage.

    Its sibling above reads ledger claims forward: an item claiming a rule must be shown that
    rule's annex. It cannot see the inverse — an annex declared unchecked while a rule in the spec
    does cite it, and does carry it into the judge prompt. That reads as "nobody looked" when
    somebody did, and it sends the next person to write a rule that partly exists.

    A citing rule does not on its own make the debt wrong: Art. 49(4) narrows its rule to two
    Annex III areas, so Annex VIII is genuinely unchecked for every other high-risk system. What is
    wrong is a reason that does not know the rule is there. So the requirement is engagement, not
    removal — the reason must name the rule and say what it leaves uncovered."""
    citing: dict[str, list[str]] = {}
    for rule in spec.rules:
        if rule.source.annex and rule.annex_context:
            citing.setdefault(str(rule.source.annex), []).append(rule.rule_id)

    silent: dict[str, list[str]] = {}
    for annex, value in (ledger["annexes_awaiting_rules"] or {}).items():
        rule_ids = citing.get(str(annex), [])
        if not rule_ids:
            continue
        # The Annex's own heading comment is where the debt is argued; the per-item reasons are
        # descriptions of the items. Either may carry the engagement, so both are read.
        written = str(value) + _comment_above(annex)
        unnamed = [rule_id for rule_id in rule_ids if rule_id not in written]
        if unnamed:
            silent[str(annex)] = unnamed
    assert not silent, (
        f"annexes declared as awaiting a rule while a rule already cites them and shows them to a "
        f"judge: {silent}. Say in the reason what that rule covers and what it leaves — or move "
        f"the items it does reach into annex_rulings."
    )


# A prose claim in the ledger that points somewhere else. Round 3 found five made false by the
# commit that paid the debts they described, and round 4 found seven more; nothing tested any of
# them, because the existing guards read the RULE/CASCADE head of a ruling and stop.
_DEBT_CLAIM = re.compile(r"await[s]? a rule|awaiting_rules")
# "Art 43" and "43(4)" are different claims, and the paragraph is the one that matters — so the
# article-only branch declines to match where a paragraph follows, leaving the next position to
# the branch that reads both.
_ADDRESS = re.compile(r"\bArts? (\d+[a-z]*)\b(?!\()|\b(\d+[a-z]*)\((\d+[a-z]*)\)")
_RULE_ID = re.compile(r"\bAIA-[A-Z]+-A[0-9A-Za-z]+(?:-[0-9A-Za-z]+)*")


def _prose(path: Path) -> list[str]:
    """The ledger read as sentences, comments included.

    Comments are half the ledger's argument — the chapter headers that say how a chapter sorts, and
    the annex headers that say what a debt costs — and two of round 4's stale claims were in one.
    So the raw file is read rather than the parsed mapping. "Art." is unpunctuated first because a
    sentence split would otherwise cut every citation off from the claim that names it, and the
    split is on the full stop alone: "Art 43(4); the second awaits a rule" is one claim, and
    breaking it at the semicolon leaves the half that makes the claim with no address in it."""
    text = path.read_text(encoding="utf-8")
    # A top-level key ENDS a sentence. Without this the key `annexes_awaiting_rules:` joins the
    # comment beneath it and the section's own name reads as a claim about whatever that comment
    # cites first — a debt about an Annex reported as a false claim about an Article.
    text = re.sub(r"^(\w[\w-]*:)", r"\1 .", text, flags=re.M)
    raw = re.sub(r"^\s*#\s?", " ", text, flags=re.M)
    raw = re.sub(r"\s+", " ", raw).replace("Art. ", "Art ").replace("Arts. ", "Arts ")
    return re.split(r"(?<=\.)\s+", raw)


def test_every_rule_the_ledger_names_in_prose_exists():
    """A ruling's prose names rules the partition never parses — "modelled as AIA-PO-A17", "which
    AIA-PO-A47 checks". Renaming a rule leaves every one of those pointing at nothing, and the
    partition passes, because it only reads the identifiers at the head of a RULE ruling."""
    known = {rule.rule_id for rule in load_policy_spec(SPEC_PATH, ARTICLES_ROOT).rules}
    for sentence in _prose(SCOPE_PATH):
        unknown = sorted({m.group(0) for m in _RULE_ID.finditer(sentence)} - known)
        assert not unknown, f"the ledger names {unknown}, which no rule has: {sentence.strip()!r}"


def test_a_debt_the_ledger_claims_in_prose_is_a_debt_it_actually_holds():
    """"Declared in articles_awaiting_rules" has to still be true of the address it names.

    This is the claim that goes stale, and it goes stale in one direction: the commit that writes
    the rule pays the debt and leaves the sentence behind, so the ledger tells the next reader a
    provision is unchecked when a rule now checks it. Seven of nine such claims were false at one
    point, all made false by the same commit.

    A sentence naming no address is not checked — "the duties it defers are declared in
    articles_awaiting_rules" is about a set the sentence does not enumerate, and inventing an
    address for it would be the guess this test exists to stop."""
    ledger = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
    divisions, documents = set(), set()
    for document, value in (ledger["articles_awaiting_rules"] or {}).items():
        documents.add(str(document))
        divisions.update(
            (str(document), str(d)) for d in (value if isinstance(value, dict) else {"": value})
        )

    for sentence in _prose(SCOPE_PATH):
        if not _DEBT_CLAIM.search(sentence):
            continue
        named = [
            (m.group(1), None) if m.group(1) else (m.group(2), m.group(3))
            for m in _ADDRESS.finditer(sentence)
        ]
        if not named:
            continue
        owed = [
            a for a in named if (a in divisions) or (a[1] is None and a[0] in documents)
        ]
        assert owed, (
            f"the ledger calls {named} a debt, and none of them is in articles_awaiting_rules — "
            f"a rule was written and the sentence pointing at the gap was left behind: "
            f"{sentence.strip()!r}"
        )


def test_a_ruling_written_where_a_rule_cites_names_that_rule(ledger, spec):
    """A rule citing a division wins the partition outright, so a reason written at the same
    address is never read again — it is not overruled, it is invisible.

    That is how Art. 74(12) came to carry both a rule and a sentence saying the duty was recorded
    elsewhere and there was nothing to write here. The partition was right and the ledger, which is
    what anyone reads to check the partition, said the opposite. Silence is fine: most cited
    divisions have no ruling at all, because the rule is the record. A ruling that contradicts one
    is not."""
    written = {
        (str(document), str(division)): str(reason)
        for document, value in (ledger["article_rulings"] or {}).items()
        if isinstance(value, dict)
        for division, reason in value.items()
    }
    for rule in spec.rules:
        division = rule.source.paragraph if rule.source.paragraph is not None else rule.source.point
        if rule.source.article is None or division is None:
            continue
        reason = written.get((rule.source.article, division))
        assert reason is None or rule.rule_id in reason, (
            f"Art. {rule.source.article}({division}) is cited by {rule.rule_id} and separately "
            f"ruled on: {reason!r}. The rule wins and the reason is never read — rewrite it to "
            f"record the rule, or delete it."
        )


def test_no_annex_is_carried_only_by_rules_a_single_area_can_reach(spec, ledger):
    """A COVERAGE RULING IS SATISFIED BY A RULE THAT EXISTS. It does not ask whether that rule can
    fire for the party the provision binds, and the partition cannot see the difference.

    That is how an annex comes to be ruled `RULE ...` at every item and reach nobody. Art. 43 is
    where both halves of it live: AIA-PO-A43-1B is gated to biometrics while Art. 43(3) applies six
    Annex VII points to an ANNEX I Section A provider, and AIA-PO-A43-2 is gated to Annex III
    points 2 to 8 while Art. 43(1)(a) lets a point 1 provider elect Annex VI. Rule one of those
    annexes to one of those rules alone and the ledger reads as covered, `owed` stays at zero, and
    the provider on the route the annex applies to is told the route exists and never told what it
    consists of.

    So this asks the question the partition does not: taking the rules the ledger names for an
    annex, is there any use case at all that cannot reach ONE of them? An annex reached only through
    `applies_to_annex_iii_area` gates is reachable only from the areas those gates name between
    them, and an annex the Act applies more widely than that is an annex some reader is missing. An
    ungated rule — no area condition — settles it, which is the ordinary case and why this is not
    noisy."""
    every_area = {area.value for area in AnnexIIIArea}
    by_id = {rule.rule_id: rule for rule in spec.rules}
    for annex, items in (ledger.get("annex_rulings") or {}).items():
        named = {
            rule_id
            for value in _values(items)
            if isinstance(value, str) and value.startswith(RULE_PREFIX)
            for rule_id in rule_ids(value)
        }
        rules = [by_id[rule_id] for rule_id in named if rule_id in by_id]
        if not rules:
            continue
        if any(not rule.applies_to_annex_iii_area for rule in rules):
            continue  # an ungated rule reaches every area; nothing to prove
        reached = {
            area.value for rule in rules for area in rule.applies_to_annex_iii_area
        }
        assert reached == every_area, (
            f"Annex {annex} is ruled only to area-gated rules, and between them they reach "
            f"{sorted(reached)} — a use case in {sorted(every_area - reached)} is told nothing "
            f"about it. The ledger reads as covered because a named rule EXISTS; the reader never "
            f"selects it."
        )


def _values(items: object) -> list[object]:
    """Every ruling under one annex key, whether the annex is itemised or ruled in one line."""
    if isinstance(items, dict):
        return list(items.values())
    return [items]


def test_a_provider_that_registers_a_derogated_system_is_told_what_to_enter(spec):
    """Art. 49(2) enacts NO AREA EXCEPTION, and Arts. 49(1) and 49(3) both do.

    "with the exception of high-risk AI systems referred to in point 2 of Annex III" appears in
    49(1) and 49(3) and not in 49(2), and Art. 49(5) registers the excepted systems nationally
    instead. So the seven-area gate that is right for a high-risk provider's EU database entry is
    wrong for a provider that concluded under Art. 6(3) that its critical-infrastructure system is
    NOT high-risk: that provider registers like any other and owes the Annex VIII Section B items,
    B/6 and B/7 above all — which of the Art. 6(3) conditions it relies on, and the grounds.

    DERIVED over every area, so an area added to the enum is covered without anyone remembering."""
    for area in AnnexIIIArea:
        rules = select_rules(
            spec, _derogated_use_case(area), ActorRole.PROVIDER
        ).all_rules
        assert any(rule.source.annex == "VIII" for rule in rules), (
            f"a provider derogating a {area.value} system under Art. 6(3) is told to register and "
            f"never told what to enter — no selected rule cites Annex VIII"
        )


def _derogated_use_case(area: AnnexIIIArea) -> UseCaseClassification:
    """A system inside an Annex III area whose provider concluded under Art. 6(3) it is not
    high-risk — the reader Art. 49(2) and Annex VIII Section B are written for."""
    source = LegalSource(
        instrument="Regulation (EU) 2024/1689",
        article="6",
        act_version_date=get_settings().act_version_date,
    )
    return UseCaseClassification(
        use_case_id="uc",
        description="a derogated system",
        risk_class=RiskClass.NOT_HIGH_RISK,
        annex_iii_area=area,
        poses_significant_risk=Answer(
            value=False, reasoning="fixture", confidence="high", source=source
        ),
        derogation=Answer(
            value=DerogationCondition.NARROW_PROCEDURAL_TASK,
            reasoning="fixture",
            confidence="high",
            source=source,
        ),
        reasoning="fixture",
        confidence="high",
        triggered_by=[ClassificationEvidence(source=source, reasoning="fixture")],
    )
