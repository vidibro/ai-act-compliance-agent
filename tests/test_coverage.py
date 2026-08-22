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
    summarise,
)
from aiact.gap import roles as role_questions
from aiact.policy_loader import load_policy_spec, resolve_requirement
from aiact.provisions import all_provisions, annex_instruments, provision_labels

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
            assert entry.detail in rules, (
                f"{where} cites rule {entry.detail!r}, which does not exist"
            )
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
        text, _url = resolve_requirement(ARTICLES_DIR, 3, None, point=point)
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
    for point in provision_labels(ARTICLES_DIR, 3):
        text, _url = resolve_requirement(ARTICLES_DIR, 3, None, point=point)
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
    """"RULE <id>" ON AN ANNEX ITEM MUST MEAN THE JUDGE IS SHOWN THE ANNEX.

    The sibling of `test_every_definition_the_ledger_hands_to_a_node_reaches_it`, for the
    obligation layer. `requirement` resolves from `source.article`/`paragraph`/`point` only, so an
    Article that POINTS AT an annex — Art. 11(1): documentation containing "at a minimum, the
    elements set out in Annex IV" — resolves to the pointer and not the list. A `completeness`
    verdict reached that way asks a judge to find every element of something nobody showed it.

    `source.annex` is what closes it: the loader injects that Annex verbatim into `annex_context`
    and the judge prompt carries it. So a ledger entry claiming a rule checks an annex item is only
    true where the rule cites THAT annex."""
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
