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
from aiact.gap.rules import roles_with_rules, select_rules
from aiact.policy_loader import (
    article_filename,
    load_policy_spec,
    provision_text,
    resolve_requirement,
)
from aiact.provisions import all_provisions, annex_instruments, provision_labels
from aiact.schemas.classification import ClassificationEvidence, UseCaseClassification
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    DerogationCondition,
    HighRiskRoute,
    RiskClass,
)
from aiact.schemas.policy import LegalSource
from aiact.schemas.question import Answer

ROOT = Path(__file__).resolve().parents[1]
VERSION = get_settings().act_version_date.isoformat()
SPEC_PATH = ROOT / "data" / "policy" / "spec.yaml"
ARTICLES_ROOT = ROOT / "data" / "policy" / "articles"
ARTICLES_DIR = ARTICLES_ROOT / VERSION
ANNEXES_DIR = ROOT / "data" / "policy" / "annexes" / VERSION
SCOPE_PATH = ROOT / "data" / "policy" / f"scope-{VERSION}.yaml"
INSTRUMENT = "Regulation (EU) 2024/1689"

# Provisions covered by a ruling made about the whole article or annex around them, rather than by
# one written for them. ZERO: every address of the stored text is ruled on individually.
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
    # Both askers, and the gap layer's questions taken as a SET rather than named one by one. A
    # question added there is a node a ruling may hand a provision to, so a hand-written list is a
    # second opinion about which questions exist, kept in the one place least likely to be updated.
    nodes = set(QUESTIONS) | set(role_questions.QUESTIONS)
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

    # A Section chapeau names the list rather than an act, so it has no instrument to be checked
    # against. It is still an address and still ruled on; this comparison is about the items.
    rulings = {k: v for k, v in ledger["annex_rulings"]["I"].items() if "chapeau" not in str(k)}
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
            # EVERY rule the ruling names, not the first. A ruling may name several — Annex VII
            # point 5 is carried by AIA-PO-A43-1B on the Annex III route and AIA-PO-A43-3 on the
            # Annex I one — and reading only the head validates the claim for one of them while
            # the others go unchecked, which is the failure this test exists to catch.
            for rule_id in rule_ids(text):
                rule = by_id[rule_id]
                if rule.source.annex != str(annex) or not rule.annex_context:
                    unsupplied[f"Annex {annex}({item}) via {rule_id}"] = (
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
    annex, can some reader in scope reach one of them?

    IT TESTS THE ROUTE DIMENSION AND NOT THE AREA DIMENSION, and the difference is that only one of
    them is free of enacted exceptions. Art. 49(1) writes "with the exception of ... point 2 of
    Annex III" and Art. 49(5) registers those systems nationally, so an Annex VIII rule that omits
    `critical_infrastructure` is CORRECT and an area-completeness assertion would fire on it. No
    comparable exception runs along the route: where an annex is reached from the Annex I route and
    the Annex III route both, a rule must exist for each. Areas stay a reading job, and this
    docstring is where that limit is written down rather than assumed.

    "NO AREA GATE" IS NOT "REACHES EVERYTHING", which is the trap. A rule carrying
    `applies_to_route: annex_i` reaches no Annex III area at all, and one carrying
    `applies_to_risk_class: [gpai_model]` reaches no high-risk use case — so exempting an annex
    because some named rule lacks an area gate exempts it on rules that are narrower still. The
    exemption below therefore requires a rule unconditional on route AND area, and the assertion
    runs per risk class, because an annex reached only by Chapter V rules has no Annex III
    dimension to be complete over.

    AN AREA GATE IS A ROUTE GATE. `_area_matches` returns False when the use case has no area, and
    an Annex I system has none, so a rule naming Annex III areas is unreachable from the Annex I
    door however its `applies_to_route` reads. It is credited with `ANNEX_III` here for that
    reason; reading its `None` as "every route" is the trap above, inverted.

    WHICH ROUTES AN ANNEX OWES is the one thing neither the spec nor the rules record — Annex VII
    is reached from both doors, Annexes VI and VIII from Annex III alone. That is a reading of the
    Act, so it lives in the ledger under `annex_route_population`, and an annex absent from it owes
    both.

    PER ITEM, because that is how the ledger rules. Pooling an annex's rulings asks only whether a
    rule for each route is named SOMEWHERE under the annex, and Art. 43(3) is the case that shows
    the difference: it applies six named pieces of Annex VII to the Annex I route and not the rest,
    so the annex has rules for both doors while individual items have one. Ruled item by item, an
    item reached from a door no rule on it can fire for is visible; pooled, it is not.

    Which also makes the population entry itemisable — the routes an item is owed to are the
    routes the Act sends a reader to THAT ITEM by, and for Annex VII points 1 and 2 that is one
    door where the annex has two."""
    by_id = {rule.rule_id: rule for rule in spec.rules}
    population = ledger.get("annex_route_population") or {}
    for annex, items in (ledger.get("annex_rulings") or {}).items():
        declared = population.get(str(annex))
        per_item = declared if isinstance(declared, dict) else {}
        for division, value in _divisions(items):
            if not (isinstance(value, str) and value.startswith(RULE_PREFIX)):
                continue
            rules = [by_id[rule_id] for rule_id in rule_ids(value) if rule_id in by_id]
            if not rules:
                continue
            owed = _declared_routes(per_item.get(division, None if per_item else declared))
            where = f"Annex {annex}({division})"
            for risk_class in {c for rule in rules for c in rule.applies_to_risk_class}:
                tier = [r for r in rules if risk_class in r.applies_to_risk_class]
                # Unconditional on BOTH: such a rule really is reachable from every route and
                # area at this tier, and settles the item on its own.
                if any(
                    not r.applies_to_annex_iii_area and r.applies_to_route is None for r in tier
                ):
                    continue
                reached = {
                    HighRiskRoute.ANNEX_III if r.applies_to_annex_iii_area else r.applies_to_route
                    for r in tier
                }
                assert reached >= owed, (
                    f"{where} at {risk_class.value} is ruled only to gated rules, and between "
                    f"them they reach {sorted(r.value for r in reached if r)} of the "
                    f"{sorted(x.value for x in owed)} this item is owed to — a provider on the "
                    f"other route is told nothing about it. "
                    f"The ledger reads as covered because a named rule EXISTS; that reader never "
                    f"selects it."
                )


def _declared_routes(ruling: object) -> set[HighRiskRoute]:
    """The routes an annex's high-risk population comes through, read off its ledger entry.

    The entry is prose whose FIRST WORD is the route, in the ledger's usual shape: the machine-read
    part at the head, the reading behind it after the em-dash. No entry means both doors."""
    if not isinstance(ruling, str):
        return set(HighRiskRoute)
    return {HighRiskRoute(ruling.split("—")[0].strip())}


def _values(items: object) -> list[object]:
    """Every ruling under one annex key, whether the annex is itemised or ruled in one line."""
    if isinstance(items, dict):
        return list(items.values())
    return [items]


def _divisions(items: object) -> list[tuple[str, object]]:
    """The same rulings, each with the division it addresses.

    An annex ruled in one line addresses the whole of itself, and `""` is the division that names
    that. The distinction matters because a rule is named PER ITEM: two items of one annex can be
    ruled to rules with different gates, and an assertion that pools them reads the annex as
    covered on the strength of the item that is."""
    if isinstance(items, dict):
        return [(str(k), v) for k, v in items.items()]
    return [("", items)]


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


def test_a_rule_reaches_every_role_the_divisions_it_covers_bind(spec, ledger):
    """`RULE <id>` ON A DIVISION CLAIMS THE RULE REACHES THE PARTY THAT DIVISION BINDS.

    The partition checks that the rule EXISTS. It never asks whether that rule can be SELECTED for
    the party the division binds, so a duty ruled to a rule gated away from its own duty-holder
    reads as covered and reaches no report.

    Mechanical form: where a ruled division OPENS by naming a role as its subject, some rule named
    for that division must apply to that role. Twenty-six divisions are examined today.

    THE LIMIT, because a guard that overstates its reach is worse than none. A duty can attach to a
    party by CROSS-REFERENCE from another Article, and nothing here sees that. Art. 73(1) opens
    "Providers of high-risk AI systems" and its own words are satisfied by a provider-only rule;
    the deployer owes it through Art. 26(5)'s closing sentence — "If the deployer is not able to
    reach the provider, Article 73 shall apply mutatis mutandis" — which is in a different Article
    and invisible to any test that reads one division at a time. Those stay a reading job. What
    this catches is the simpler shape: a division naming its own duty-holder in its opening words,
    ruled to a rule that party cannot select. `_ROLE_OPENINGS` is how many of those it sees."""
    by_id = {rule.rule_id: rule for rule in spec.rules}
    wrong: list[str] = []
    for article, rulings in (ledger.get("article_rulings") or {}).items():
        if not isinstance(rulings, dict):
            continue
        for division, reason in rulings.items():
            text = str(reason)
            if not text.startswith(RULE_PREFIX):
                continue
            named = [by_id[r] for r in rule_ids(text) if r in by_id]
            if not named:
                continue
            roles = {role for rule in named for role in rule.applies_to_role}
            try:
                enacted, _ = resolve_requirement(ARTICLES_DIR, str(article), str(division))
            except (KeyError, ValueError):
                continue
            for word, role in _ROLE_OPENINGS:
                if enacted.startswith(word) and role not in roles:
                    wrong.append(
                        f"Art. {article}({division}) opens {word!r} but "
                        f"{sorted(r.rule_id for r in named)} reach {sorted(x.value for x in roles)}"
                    )
    assert not wrong, (
        f"divisions ruled to a rule that cannot be selected for the role the division binds: "
        f"{wrong}. The ledger reads as covered because the rule EXISTS; that reader never selects "
        f"it."
    )


# How the Act names a duty-holder as the subject of a division. Every opening the enacted text
# actually uses, so a paragraph is examined rather than skipped: the plural bare form, the plural
# with a narrowing ("Deployers of", "Deployers that"), and the singular with the article. An
# opening absent from this tuple is not a passing division, it is an unexamined one.
_ROLE_OPENINGS = (
    ("Deployers shall", ActorRole.DEPLOYER),
    ("Deployers of", ActorRole.DEPLOYER),
    ("Deployers that", ActorRole.DEPLOYER),
    ("The deployer shall", ActorRole.DEPLOYER),
    ("Providers shall", ActorRole.PROVIDER),
    ("Providers of", ActorRole.PROVIDER),
    ("Providers that", ActorRole.PROVIDER),
    ("The provider shall", ActorRole.PROVIDER),
    ("The provider of", ActorRole.PROVIDER),
    ("The providers of", ActorRole.PROVIDER),
    ("Importers shall", ActorRole.IMPORTER),
    ("The importer shall", ActorRole.IMPORTER),
    ("Distributors shall", ActorRole.DISTRIBUTOR),
    ("The distributor shall", ActorRole.DISTRIBUTOR),
    ("Authorised representatives", ActorRole.AUTHORISED_REPRESENTATIVE),
    ("The authorised representative", ActorRole.AUTHORISED_REPRESENTATIVE),
)


def test_every_role_has_rules_or_a_written_reason(spec, ledger):
    """THE PARTITION, OVER ROLES. Every `ActorRole` either carries rules in the spec or is listed in
    `roles_out_of_scope` with a reason, and this is what `roles_with_rules` means when it says a
    role missing from its list is a CI failure rather than a silent omission from every report.

    The failure it guards is silent by construction. A role added to `ActorRole` and never given a
    rule is selected for in every report and contributes an empty column; a role that loses its last
    rule disappears from `roles_with_rules` and no report mentions it again. Neither changes a
    count, and neither looks like an error from the outside.

    TWO KINDS OF ENTRY, and the difference is worth keeping. `product_manufacturer` IS an
    `ActorRole` and is dismissed because Art. 25(3) hands it the provider's duty set rather than one
    of its own. `third_party_supplier` is NOT an `ActorRole` at all — Art. 3(8)'s "operator" does
    not reach a component supplier — and its entry records a party the Act names in a bilateral duty
    that this tool reports from one side only. A reader is owed that second kind most, because
    nothing else in the output hints the other side exists."""
    named = set(roles_with_rules(spec))
    dismissed = ledger.get("roles_out_of_scope") or {}
    for role in ActorRole:
        assert role in named or role.value in dismissed, (
            f"{role.value} has no rule in the spec and no entry in roles_out_of_scope. It is "
            f"selected for in every report and contributes nothing, which reads as a party that "
            f"owes nothing rather than one nobody wrote rules for."
        )
    for role_name, reason in dismissed.items():
        assert role_name not in {r.value for r in named}, (
            f"{role_name} is both dismissed in roles_out_of_scope and carries rules in the spec."
        )
        assert len(str(reason).split()) >= 25, (
            f"roles_out_of_scope[{role_name}] is too short to be an argument. A dismissal is the "
            f"one status that admits a reader will be told nothing, so it states WHY."
        )


# How an annex section heading names the party that owes its items. The Act writes them as
# "Information to be submitted by providers of…" / "…by deployers of…", so the noun follows "by".
# "by all providers" is Annex XI Section 1's form and has to precede the bare one, or the shorter
# string matches first and the longer one is never reached.
_SECTION_OWNERS = (
    ("by all providers", ActorRole.PROVIDER),
    ("by providers", ActorRole.PROVIDER),
    ("by deployers", ActorRole.DEPLOYER),
)


def test_no_annex_section_is_carried_by_a_rule_its_own_heading_excludes(spec, ledger):
    """AN ANNEX SECTION NAMES ITS DUTY-HOLDER IN ITS HEADING, and a rule no such party can select
    leaves that section owed to nobody.

    Annex VIII splits three ways along the role and says so in its own words: Section A is
    "Information to be submitted BY PROVIDERS … in accordance with Article 49(1)", Section B is
    providers again under Art. 49(2), and Section C is "BY DEPLOYERS … in accordance with
    Article 49(3)". Three sections, two parties, one annex — so a rule that carries the right annex
    on the right route can still be the wrong party's rule.

    `test_no_annex_is_carried_only_by_rules_a_single_area_can_reach` reads the route dimension and
    the area dimension and stops there. Reattribute every Section A item to the deployer's
    registration rule and it stays green, because a rule reaching the Annex III route does exist —
    it is simply one no provider ever selects, and the provider's thirteen registration fields
    reach no report.

    IT READS THE HEADING AND NOT THE ITEMS, which is the whole of its reach. A section whose
    heading names no party is skipped rather than guessed at, and an item that binds someone the
    heading does not mention is invisible here. The sections that do name a party are the ones
    where a whole block of an annex can change hands in one edit."""
    by_id = {rule.rule_id: rule for rule in spec.rules}
    wrong: list[str] = []
    for annex, items in (ledger.get("annex_rulings") or {}).items():
        if not isinstance(items, dict):
            continue
        headings = _section_headings(ANNEXES_DIR / f"annex-{annex}.md")
        for key, ruling in items.items():
            section, _, _ = str(key).partition("/")
            heading = headings.get(section, "").lower()
            owner = next((r for text, r in _SECTION_OWNERS if text in heading), None)
            if owner is None or not str(ruling).startswith(RULE_PREFIX):
                continue
            named = [by_id[r] for r in rule_ids(str(ruling)) if r in by_id]
            reached = {role for rule in named for role in rule.applies_to_role}
            if named and owner not in reached:
                wrong.append(
                    f"Annex {annex}({key}) is submitted by {owner.value}s, but "
                    f"{sorted(r.rule_id for r in named)} reach "
                    f"{sorted(x.value for x in reached)}"
                )
    assert not wrong, (
        f"annex items ruled to a rule the section's own duty-holder cannot select: {wrong}. The "
        f"ledger reads as covered because a named rule EXISTS; that party never selects it."
    )


def _section_headings(path: Path) -> dict[str, str]:
    """Each `Section X` heading in an annex, keyed by the letter or number the ledger keys use.

    The stored annexes run a section's heading and its first item together on one line, so the
    heading is the line the marker opens rather than a block of its own.

    AND THEY RUN THE LABEL INTO THE HEADING TOO. Annex I and Annex VIII write "Section A. …", and
    Annex XI writes "Section 1Information to be provided by all providers…" with no separator at
    all, so the separator is optional here and the label is a number OR a letter rather than a run
    of either — "Section 1Information" offers `1I` to a pattern that takes both."""
    body = provision_text(path)
    headings: dict[str, str] = {}
    for match in re.finditer(r"^Section\s+(\d+|[A-Z])\s*[.:—-]?\s*(?=[A-Z])", body, re.M):
        end = body.find("\n", match.start())
        headings[match.group(1)] = body[match.start() : end if end != -1 else len(body)]
    return headings


# The five parties this ruleset writes obligations for. Matched in the enacted text as words, so
# "providers" and "provider" are one mention and "provider of a general-purpose AI model" is still
# a provider — narrowing by phrase would be a second opinion about who the Act is addressing.
_ROLE_WORD = re.compile(
    r"\b(provider|deployer|importer|distributor|authorised representative)s?\b", re.I
)
_ROLE_OF_WORD = {
    "provider": ActorRole.PROVIDER,
    "deployer": ActorRole.DEPLOYER,
    "importer": ActorRole.IMPORTER,
    "distributor": ActorRole.DISTRIBUTOR,
    "authorised representative": ActorRole.AUTHORISED_REPRESENTATIVE,
}


# An article divides into numbered PARAGRAPHS or into lettered POINTS, and the labels do not tell
# them apart: Art. 3's points are `1`, `2`, `3` exactly as Art. 5's paragraphs are. The Act writes
# points in brackets and paragraphs without, which is the test `provisions._with_unnumbered` uses
# to decide where an article's chapeau ends, and the same one here. Both shapes go into the same
# population: Art. 3 is entirely points and every definition of a party is in it, so a sweep that
# addressed paragraphs alone would step over the place the Act says who these parties ARE.
_BRACKETED = r"^[ \t]*\({label}\)"


def _division_text(article: str, division: str) -> str:
    """One division's enacted text, whichever shape its article is written in.

    A point is taken from the body directly rather than through `resolve_requirement`, which
    reaches points by label and refuses an ambiguous one — Art. 66 writes `(i)` at two depths. The
    span here is from this point's label to the next top-level label of the same article, which is
    what the address means whether or not the label is unique further down."""
    body = provision_text(ARTICLES_DIR / article_filename(article))
    opens = re.search(_BRACKETED.format(label=re.escape(division)), body, re.M)
    if opens is None:
        text, _url = resolve_requirement(ARTICLES_DIR, article, division)
        return text
    following = [
        m.start()
        for label in provision_labels(ARTICLES_DIR, article)
        for m in [re.search(_BRACKETED.format(label=re.escape(label)), body, re.M)]
        if m and m.start() > opens.start()
    ]
    return body[opens.start() : min(following) if following else len(body)]


def _roles_bound_at(spec) -> dict[tuple[str, str], set[ActorRole]]:
    """Which roles the rules citing each article address bind.

    A RULE CITING AN ARTICLE WHOLE BINDS EVERY DIVISION OF IT. `AIA-HR-A09` names Art. 9 with no
    paragraph and its `requirement` is all ten of them, so the party it binds is bound at 9(5) and
    9(9) as surely as a rule that cited those paragraphs by number. Reading the citation literally
    would put every paragraph of every whole-article rule into the sweep, which is not a population
    of unanswered questions but a population of answered ones filed one level up."""
    bound: dict[tuple[str, str], set[ActorRole]] = {}
    for rule in spec.rules:
        source = rule.source
        if source.article is None:
            continue
        article = str(source.article)
        division = source.paragraph if source.paragraph is not None else source.point
        divisions = (
            [str(division)]
            if division is not None
            else [str(d) for d in provision_labels(ARTICLES_DIR, article)]
        )
        for one in divisions:
            bound.setdefault((article, one), set()).update(rule.applies_to_role)
    return bound


def _unbound_role_mentions(spec) -> dict[str, list[str]]:
    """Every address naming a role that no rule citing it binds, and which roles those are.

    THE MENTION IS THE UNIT, not the paragraph and not the duty. Whether a mention creates an
    obligation is a reading, and the point of deriving the population this way is that the reading
    has somewhere it must be written down: a mention with no rule behind it and no entry in the
    ledger is a party the Act names and this ruleset says nothing about."""
    bound = _roles_bound_at(spec)
    unbound: dict[str, list[str]] = {}
    for provision in all_provisions(ARTICLES_DIR, ANNEXES_DIR):
        if provision.kind != "article" or provision.division in (None, "chapeau", "closing"):
            continue
        key = (provision.document, str(provision.division))
        text = _division_text(key[0], key[1])
        named = {_ROLE_OF_WORD[m.lower()] for m in _ROLE_WORD.findall(text)}
        missing = named - bound.get(key, set())
        if missing:
            unbound[f"{key[0]}({key[1]})"] = sorted(r.value for r in missing)
    return unbound


def test_every_role_mention_is_accounted_for(spec, ledger):
    """Where the Act names a party, this ruleset either binds it or says what the words do.

    `unaccounted` counts addresses with no ruling. It has nothing to say about a ruling that
    accounts for one of the parties its provision names, which is the failure this guards: a rule
    cites the address, the partition reads `checked`, and a duty on the other party reaches no
    reader.

    A MENTION IS NOT A DUTY. The Act names the party a duty is owed TO, the party an authority must
    inform, the party a definition classifies. This does not decide which — it requires that
    somebody has, and that the answer is written where the next reader finds it."""
    unbound = _unbound_role_mentions(spec)
    recorded = ledger.get("role_mentions") or {}
    missing = sorted(set(unbound) - set(recorded))
    stale = sorted(set(recorded) - set(unbound))
    assert not missing, (
        f"{len(missing)} addresses name a role no rule binds and carry no entry in "
        f"`role_mentions`: {missing}. Each needs a rule, or a line saying what the words do for "
        f"that role."
    )
    assert not stale, (
        f"`role_mentions` accounts for {stale}, where a rule now binds every role the text names. "
        f"The entry claims a reading nobody owes — delete it."
    )


def test_a_role_mention_entry_names_the_roles_it_accounts_for(spec, ledger):
    """An entry answers for the roles the address actually leaves unbound, and says so.

    Written as prose keyed by address, like every other ruling here, so the check is that the
    prose NAMES each unbound role rather than answering for the paragraph in general. An entry
    that explains the deployer mention and is silent on the importer accounts for half of what
    put the address in the population."""
    unbound = _unbound_role_mentions(spec)
    recorded = ledger.get("role_mentions") or {}
    for address, roles in unbound.items():
        if address not in recorded:
            continue  # `test_every_role_mention_is_accounted_for` owns the missing ones
        reason = str(recorded[address])
        unnamed = [r for r in roles if r.split("_")[0] not in reason.lower()]
        assert not unnamed, (
            f"role_mentions[{address}] does not name {unnamed}. The address names that party and "
            f"no rule citing it binds them; the entry has to say what the words do for THEM."
        )
        assert len(reason.split()) >= 12, (
            f"role_mentions[{address}] is too short to be a reading: {reason!r}"
        )




# The words a dismissal reaches for when it means "no rule stands here yet". Said about an article
# the ruleset covers, the claim is not a scope decision but a stale fact, and the next reader takes
# it as current. The exposure is a whole chapter: one ruling per definition, each pointing at the
# same area, all of them out of date the moment its first rule lands.
_STALE_CLAIM = re.compile(
    r"\b(still unwritten|not (?:yet )?(?:modelled|written|carried)|deferred|out of scope)\b", re.I
)


def test_no_ruling_says_a_chapter_is_unmodelled_while_its_rules_exist(spec):
    """A dismissal may say a duty is not owed. It may not say a rule does not exist when it does.

    THE TWO ARE DIFFERENT CLAIMS and only the first is a scope decision. A ruling that says an
    article is unmodelled turns false the moment a rule cites that article, and nothing else
    catches it: the article's own ruling is correct, so the coverage partition sees a covered
    provision either way. What the stale line costs is the next reader, told a whole area is
    unmodelled and stopping there.

    Asserted on the ARTICLES A RULING NAMES, not on its topic: a ruling that cites Art. 61 and
    calls it out of scope is checked against the rules citing Art. 61, whatever else it says."""
    cited = {str(r.source.article) for r in spec.rules if r.source.article is not None}
    scope = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))
    stale: list[str] = []
    for article, body in scope["article_rulings"].items():
        items = body.items() if isinstance(body, dict) else [(None, body)]
        for para, text in items:
            ruling = " ".join(str(text).split())
            if ruling.startswith(("RULE", "CASCADE")) or not _STALE_CLAIM.search(ruling):
                continue
            named = {m for m in re.findall(r"Arts?\. (\d+[a-z]?)", ruling) if m in cited}
            if named:
                where = f"Art. {article}({para})" if para is not None else f"Art. {article}"
                stale.append(f"{where} calls {sorted(named)} unmodelled, and rules cite them")
    assert not stale, "\n".join(stale)
