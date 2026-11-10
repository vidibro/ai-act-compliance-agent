"""The documents behind demo mode's case gallery — one click runs the demo review on one.

Demo mode only. Normal mode offers no stock documents: a reader writes their own system card with
`docs/system-card-guide.md`, and a sample loaded into a real review would read as a template of
what a complete card looks like, which none of these is.

The registry is `data/demo/samples.yaml`: one entry per document, in display order, each with the
risk class the demo stand-ins reach on it (`outcome`) so a reader can pick the case they want to
see. The documents themselves are already in the repository or written for the demo:

  - the golden set's REFERENCE technical files (`data/golden_set/reference/`);
  - SYSTEM CARDS written to `docs/system-card-guide.md` — the guide's own worked example, lifted
    out of the guide, and the cards under `data/demo/cards/` authored for the cases the golden set
    does not cover (Annex I, Art. 6(3), Art. 50, Chapter V, Art. 2, needs-review);
  - the smoke check's VENDOR PAGES (`data/golden_set/smoke/`).

The reference files carry authoring comments and `<!-- rule: ... -->` tags that never reach the
agent in the golden set; they are stripped here too. Paths are relative to the working directory,
like every other data path.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

REGISTRY = Path("data/demo/samples.yaml")

# The authoring note at the top of a reference file quotes a rule tag inside itself, so it ends at
# the first `-->` that starts a line — the same reading scripts/make_golden_set.py makes.
_LEADING_COMMENT = re.compile(r"\A<!--.*?^-->\n+", re.DOTALL | re.MULTILINE)
_COMMENT = re.compile(r"<!--.*?-->[ \t]*\n?", re.DOTALL)
_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_CARD_START = re.compile(r"^###\s+(.+?)\s+[—–-]\s+system card\s*$", re.MULTILINE | re.IGNORECASE)

SampleKind = Literal["reference", "system_card", "vendor_page", "model_card"]


class Sample(BaseModel):
    id: str
    title: str
    kind: SampleKind
    outcome: str
    """The risk class the demo review reaches on this document, e.g. "high_risk"."""
    label: str
    """The case in a few words, e.g. "Annex I · medical device, notified body"."""
    about: str
    """One or two sentences on what the document is and what to expect from it."""
    source: str
    """Where in the repository it comes from."""


class SampleDocument(Sample):
    text: str


class _Entry(BaseModel):
    """One registry entry, as authored."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    path: Path
    extract: Literal["guide_card"] | None = None
    kind: SampleKind
    outcome: str
    label: str
    about: str


class _Registry(BaseModel):
    samples: list[_Entry]


@lru_cache(maxsize=1)
def _entries() -> tuple[_Entry, ...]:
    if not REGISTRY.is_file():
        return ()
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    entries = _Registry(**payload).samples
    ids = [entry.id for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{REGISTRY}: sample ids are not unique.")
    return tuple(entries)


def _read(entry: _Entry) -> str | None:
    try:
        text = entry.path.read_text(encoding="utf-8")
    except OSError:
        return None
    if entry.extract == "guide_card":
        return _guide_card(text)
    return _COMMENT.sub("", _LEADING_COMMENT.sub("", text)).strip() + "\n"


def _guide_card(guide: str) -> str | None:
    """The guide's appendix card on its own, with its headings promoted to a document's."""
    start = _CARD_START.search(guide)
    if start is None:
        return None
    card = guide[start.start() :]
    # The appendix runs to the end of the guide; its headings are two levels deep in it.
    card = re.sub(r"^###", "#", card, flags=re.MULTILINE)
    return card.strip() + "\n"


def _title(text: str, fallback: str) -> str:
    match = _TITLE.search(text)
    return match.group(1).strip() if match else fallback


def _sample(entry: _Entry, text: str) -> Sample:
    return Sample(
        id=entry.id,
        title=_title(text, entry.id),
        kind=entry.kind,
        outcome=entry.outcome,
        label=entry.label,
        about=" ".join(entry.about.split()),
        source=entry.path.as_posix(),
    )


def list_samples() -> list[Sample]:
    """Every registered sample that can be read right now, in registry order."""
    out: list[Sample] = []
    for entry in _entries():
        text = _read(entry)
        if text is not None:
            out.append(_sample(entry, text))
    return out


def load_sample(sample_id: str) -> SampleDocument | None:
    for entry in _entries():
        if entry.id != sample_id:
            continue
        text = _read(entry)
        if text is None:
            return None
        return SampleDocument(**_sample(entry, text).model_dump(), text=text)
    return None
