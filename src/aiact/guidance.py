"""Resolve Commission-guidance snippet references.

A guidance ref is ``"<doc-ref>/<slug>"`` — e.g. ``"C-2025-5052/workplace-covers-recruitment"`` —
and points at a hand-verified snippet in the guidance store (``data/policy/guidance/``). Snippets
are the citable unit: a golden case, a ``PolicyRule``, or a classification question references one
by this stable id, and many may cite the same one (see data/policy/guidance/README.md).

Kept deliberately separate from ``LegalSource``. Guidance is the Commission's **non-binding**
interpretation, not enacted law, so a resolved snippet carries ``binding=False`` and anything that
rests on it must say so. The resolver also verifies the stored ``sha256`` against the snippet body,
so a citation cannot silently drift from the text it was checked against.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_GUIDANCE_ROOT = Path("data/policy/guidance")

_FRONT_SHA = re.compile(r"^sha256:\s*([0-9a-f]{64})\s*$", re.M)
_FRONT_BINDING = re.compile(r"^binding:\s*(true|false)\s*$", re.M)
_FRONT_LOCATOR = re.compile(r"^locator:\s*(.+?)\s*$", re.M)


@dataclass(frozen=True)
class GuidanceSnippet:
    """One verbatim, hand-verified passage of Commission guidance."""

    ref: str
    path: Path
    body: str
    binding: bool
    locator: str


def snippet_path(ref: str, root: str | Path | None = None) -> Path:
    """Map ``"<doc>/<slug>"`` to ``<root>/<doc>/snippets/<slug>.md``."""
    doc, sep, slug = ref.partition("/")
    if not sep or not doc or not slug or "/" in slug:
        raise ValueError(
            f"guidance ref must be '<doc-ref>/<slug>' (got {ref!r}), "
            f"e.g. 'C-2025-5052/workplace-covers-recruitment'"
        )
    return Path(root or DEFAULT_GUIDANCE_ROOT) / doc / "snippets" / f"{slug}.md"


def _body_of(raw: str) -> str:
    """The snippet text — everything after the front matter's closing delimiter. This is the exact
    span the stored sha256 covers, so extraction and hashing use one rule."""
    _, sep, body = raw.partition("\n---\n")
    return (body if sep else raw).lstrip("\n")


def load_snippet(ref: str, root: str | Path | None = None) -> GuidanceSnippet:
    """Load and integrity-check one snippet. Raises if it is missing or its body no longer matches
    the stored sha256 (a citation that drifted from its checked text is not usable)."""
    path = snippet_path(ref, root)
    if not path.is_file():
        raise FileNotFoundError(f"guidance snippet {ref!r} not found at {path}")
    raw = path.read_text(encoding="utf-8")
    body = _body_of(raw)

    declared = _FRONT_SHA.search(raw)
    if declared is None:
        raise ValueError(f"guidance snippet {ref!r} has no sha256 in its front matter")
    actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if actual != declared.group(1):
        raise ValueError(
            f"guidance snippet {ref!r} body does not match its stored sha256 "
            f"(declared {declared.group(1)[:12]}…, got {actual[:12]}…) — the quote was edited "
            f"without re-verifying it against the source PDF."
        )

    binding_m = _FRONT_BINDING.search(raw)
    locator_m = _FRONT_LOCATOR.search(raw)
    return GuidanceSnippet(
        ref=ref,
        path=path,
        body=body,
        binding=bool(binding_m and binding_m.group(1) == "true"),
        locator=locator_m.group(1) if locator_m else "",
    )
