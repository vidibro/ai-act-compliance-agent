"""A deliberately dumb keyword checker — the strawman the real agent must beat.

This is not a component of the product. It exists so the eval has something to measure before any
LLM does, and so the project's central claim is stated as a NUMBER rather than an opinion: that
distinguishing GAP from INADEQUATE is the hard part, and that matching words cannot do it.

Keywords are derived mechanically from the cited article's TITLE (e.g. Article 14 -> "Human
oversight" -> {human, oversight}), so the baseline is not hand-tuned per case to look good or bad.
It answers exactly one question — "does the document mention this topic?" — and therefore can only
ever emit PASS or GAP. It has no way to express INADEQUATE, which is the whole point.
"""

from __future__ import annotations

import re

from aiact.schemas.enums import Verdict
from aiact.schemas.policy import PolicyRule

_STOP = {
    "and", "the", "for", "with", "from", "této", "provision", "of", "to", "in", "on",
    "rules", "system", "systems", "certain", "provided", "information",
}
_WORD = re.compile(r"[a-z]+")


def keywords_from_title(title: str) -> set[str]:
    """Topic words from an article title. Mechanical: no per-rule tuning."""
    return {w for w in _WORD.findall(title.lower()) if len(w) > 3 and w not in _STOP}


class KeywordBaseline:
    """Says PASS if the document mentions the article's topic at all, else GAP."""

    name = "keyword-baseline"

    def __init__(self, titles: dict[str, str]) -> None:
        # rule_id -> keyword set, derived from the cited article's title
        self.keywords = {rid: keywords_from_title(t) for rid, t in titles.items()}

    def check(self, rule: PolicyRule, document: str) -> Verdict:
        doc = document.lower()
        hits = [k for k in self.keywords.get(rule.rule_id, set()) if k in doc]
        return Verdict.PASS if hits else Verdict.GAP
