"""Where every piece of the enacted text stands: checked, asked, ruled out, owed, or unread.

ONE PARTITION over `provisions.all_provisions()`. Each address gets exactly one status, and the
statuses are exhaustive by construction — the last of them, UNACCOUNTED, is the failure state and
the reason the enum has six values rather than four.

    CHECKED      a rule tests documentation against it, and names the rule
    ASKED        the classification cascade decides it, and names the node
    NOT_OWED     it creates no duty for the roles this tool reports for, and says why
    OWED         it creates a duty this tool does not check yet, declared as a debt
    BLANKET      no one has ruled on this address; it inherits a ruling made about the whole
                 article or annex it sits in
    UNACCOUNTED  nothing covers it at all

BLANKET IS THE ONE THAT MATTERS. It is not an error — an article can be dismissed in one sentence
and be perfectly correctly dismissed — but it is an unexamined provision wearing a ruling made
about its neighbours, and the duties this ruleset has missed were all found inside one. So it is
counted rather than tolerated silently, and the count is meant to reach zero.

The four real statuses each carry a `detail` naming what backs them: a rule id, a node id, or the
written reason. A status with nothing behind it is not a claim anyone can check.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from aiact.provisions import Provision, all_provisions

CASCADE_PREFIX = "CASCADE "

# A division inside an article a rule cites WHOLE. The rule's requirement text already contains it
# and the judge sees it, so it is checked — but under a verdict shared with the article's other
# paragraphs, which says nothing about this one. Writing the ruling out is what turns "the rule
# covers the article" into "someone read this paragraph and confirmed the rule reaches it".
RULE_PREFIX = "RULE "


class Status(StrEnum):
    """How one provision is accounted for."""

    CHECKED = "checked"
    ASKED = "asked"
    NOT_OWED = "not_owed"
    OWED = "owed"
    BLANKET = "blanket"
    UNACCOUNTED = "unaccounted"


@dataclass(frozen=True)
class Coverage:
    """One provision and the single thing that accounts for it."""

    provision: Provision
    status: Status
    detail: str

    @property
    def is_individual(self) -> bool:
        """True where someone ruled on THIS provision rather than on the document around it."""
        return self.status in (Status.CHECKED, Status.ASKED, Status.NOT_OWED, Status.OWED)


def _cited_addresses(spec: Any) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    """Rules, split by how precisely they cite.

    A rule that names a paragraph or a point claims THAT division. A rule that names only the
    article claims the article as a whole, which covers its divisions without ruling on any of them
    — the difference between the two is the whole subject of this module.

    `source.annex` is deliberately NOT a claim on an annex division. A rule citing Art. 49(1) and
    referencing Annex III has Art. 49(1) as its subject; the Annex is context. Treating the
    reference as coverage would mark all eight Annex III areas as ruled on by one registration rule.
    """
    precise: dict[tuple[str, str], str] = {}
    whole: dict[str, str] = {}
    for rule in spec.rules:
        source = rule.source
        if source.article is None:
            continue
        article = str(source.article)
        division = source.paragraph if source.paragraph is not None else source.point
        if division is None:
            whole.setdefault(article, rule.rule_id)
        else:
            precise.setdefault((article, str(division)), rule.rule_id)
    return precise, whole


def _rulings(section: Any) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """A ledger section, split into whole-document reasons and per-division reasons."""
    whole: dict[str, str] = {}
    divisions: dict[tuple[str, str], str] = {}
    for document, value in (section or {}).items():
        if isinstance(value, dict):
            for division, reason in value.items():
                divisions[(str(document), str(division))] = str(reason)
        else:
            whole[str(document)] = str(value)
    return whole, divisions


def classify_coverage(
    spec: Any,
    ledger: dict[str, Any],
    articles_dir: Path,
    annexes_dir: Path,
    used_annexes: set[str] | None = None,
) -> list[Coverage]:
    """Account for every provision of the stored Act, in the Act's own order.

    Resolution runs most specific first: a ruling on the division beats one on the document, and a
    rule citing the division beats a rule citing the article. That ordering is what stops a broad
    dismissal from hiding a narrow ruling, and what lets a single paragraph be pulled out of an
    otherwise excluded article — which is how Art. 8(2) sits inside an Art. 8 that is otherwise the
    chapeau to rules modelled elsewhere.

    `used_annexes` names the annexes some part of the tool reads — cited by a rule, or supplied to
    the cascade as context. Their items come back BLANKET rather than CHECKED, and the distinction
    is the honest one: the tool reading Annex III is not the same as anyone having ruled on what
    Annex III(5)(b) requires. Passed in rather than imported so this module stays independent of the
    graph it is measuring.
    """
    precise, whole_cited = _cited_addresses(spec)
    art_whole, art_div = _rulings(ledger.get("article_rulings"))
    art_owed_whole, art_owed_div = _rulings(ledger.get("articles_awaiting_rules"))
    ann_whole, ann_div = _rulings(ledger.get("annex_rulings"))
    ann_owed_whole, ann_owed_div = _rulings(ledger.get("annexes_awaiting_rules"))

    covered: list[Coverage] = []
    for provision in all_provisions(articles_dir, annexes_dir):
        document = provision.document
        division = provision.division
        key = (document, division or "")

        if provision.kind == "article":
            reasons, owed = art_div, art_owed_div
            blanket_reasons, blanket_owed = art_whole, art_owed_whole
        else:
            reasons, owed = ann_div, ann_owed_div
            blanket_reasons, blanket_owed = ann_whole, ann_owed_whole

        status, detail = Status.UNACCOUNTED, ""
        if provision.kind == "article" and key in precise:
            status, detail = Status.CHECKED, precise[key]
        elif key in reasons:
            reason = reasons[key]
            if reason.startswith(CASCADE_PREFIX):
                node = reason[len(CASCADE_PREFIX) :].split()[0].rstrip(",:—")
                status, detail = Status.ASKED, node
            elif reason.startswith(RULE_PREFIX):
                status, detail = Status.CHECKED, reason[len(RULE_PREFIX) :].split()[0].rstrip(",:—")
            else:
                status, detail = Status.NOT_OWED, reason
        elif key in owed:
            status, detail = Status.OWED, owed[key]
        elif division is None and document in blanket_reasons:
            # An Article or Annex the text does not divide at all — Art. 32, Art. 39. There is one
            # provision, so a reason written about the document IS the reason for that provision.
            # Nothing is being covered by proxy, and calling it a blanket would report a debt that
            # cannot be paid: there is no finer address to write.
            status, detail = Status.NOT_OWED, blanket_reasons[document]
        elif provision.kind == "article" and document in whole_cited:
            by = whole_cited[document]
            status, detail = Status.BLANKET, f"inside {document}, cited whole by {by}"
        elif document in blanket_reasons:
            status, detail = Status.BLANKET, f"inside {document}, ruled out whole"
        elif document in blanket_owed:
            status, detail = Status.BLANKET, f"inside {document}, owed a rule as a whole"
        elif provision.kind == "annex" and document in (used_annexes or set()):
            status, detail = Status.BLANKET, f"inside Annex {document}, which the tool reads whole"

        covered.append(Coverage(provision, status, detail))
    return covered


def summarise(covered: list[Coverage]) -> dict[Status, int]:
    """How many provisions sit at each status, for a report or a budget."""
    return {status: sum(c.status is status for c in covered) for status in Status}
