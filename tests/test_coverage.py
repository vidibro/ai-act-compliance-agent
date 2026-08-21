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

from aiact.classify.graph import _QUESTION_CONTEXT, QUESTIONS
from aiact.config import get_settings
from aiact.coverage import Status, classify_coverage, summarise
from aiact.gap import roles as role_questions
from aiact.policy_loader import load_policy_spec
from aiact.provisions import all_provisions, annex_instruments

ROOT = Path(__file__).resolve().parents[1]
VERSION = get_settings().act_version_date.isoformat()
SPEC_PATH = ROOT / "data" / "policy" / "spec.yaml"
ARTICLES_ROOT = ROOT / "data" / "policy" / "articles"
ARTICLES_DIR = ARTICLES_ROOT / VERSION
ANNEXES_DIR = ROOT / "data" / "policy" / "annexes" / VERSION
SCOPE_PATH = ROOT / "data" / "policy" / f"scope-{VERSION}.yaml"

# Provisions covered by a ruling made about the whole article or annex around them, rather than by
# one written for them. ZERO: all 787 addresses of the stored text are ruled on individually.
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
            assert entry.detail in nodes, (
                f"{where} is handed to cascade node {entry.detail!r}, which does not exist. "
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
