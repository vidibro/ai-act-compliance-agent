"""Fill a question's `context` with the VERBATIM enacted text it must be answered against.

The rule this module exists to enforce: no question about the law is ever put to a model without
the law beside it. Asking "which Annex III area is this?" without supplying Annex III is exactly
the unanchored guessing this project exists to avoid, and the same discipline governs the
obligation `requirement` fields — see policy_loader.

It lives OUTSIDE both graphs because both ask questions about a document, and neither may import
the other. The classification cascade asks what the system IS; the gap layer asks who the reader
is (Art. 25). Duplicating the loading in the second one would mean two copies of the integrity
check that guards the trust boundary described in SECURITY.md — and a copy is exactly where a
verification step goes missing.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

from aiact.config import get_settings
from aiact.guidance import load_snippet
from aiact.policy_loader import _FRONT_FIELD, _FRONT_MATTER, verify_integrity
from aiact.schemas.policy import GuidanceSource
from aiact.schemas.question import Question

# Which verbatim provisions one question must be answered against: article numbers, and Annexes by
# their roman numeral.
Provisions = tuple[tuple[int, ...], tuple[str, ...]]


def provision_text(path: Path) -> str:
    """Read a stored article/annex file, verify its integrity, and strip the YAML front matter.

    This text goes STRAIGHT INTO THE PROMPT as "the enacted text you must answer against", so it is
    the single most important place to check that the stored law is the law: a tampered or corrupted
    file here would be presented to the model as the Official Journal, and the verdict's citation
    would point at wording that was never enacted. Verified on every load — see
    `policy_loader.verify_integrity` and SECURITY.md.
    """
    raw = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(raw)
    if match is None:
        raise ValueError(f"{path} is missing YAML front matter — regenerate it.")
    front = dict(_FRONT_FIELD.findall(match.group(1)))
    body = raw[match.end() :]
    verify_integrity(path, raw, front, body)
    return body.strip()


def anchor_questions(
    questions: dict[str, Question],
    provisions: dict[str, Provisions],
    guidance: dict[str, tuple[str, ...]] | None = None,
    version: str | date | None = None,
    articles_root: str | Path | None = None,
    annexes_root: str | Path | None = None,
    guidance_root: str | Path | None = None,
) -> dict[str, Question]:
    """`questions` with each `context` filled from the verbatim article/annex store, and
    `guidance_context` filled where `guidance` names a snippet.

    A question with no entry in `provisions` gets empty context rather than an error: that is a
    deliberate authoring choice for the few questions answerable from the description alone, and
    the caller's own tests are where it belongs — this function does not know which those are.
    """
    settings = get_settings()
    v = version or settings.act_version_date
    v_str = v.isoformat() if isinstance(v, date) else str(v)
    art_dir = Path(articles_root or settings.policy_articles_path) / v_str
    ann_dir = Path(annexes_root or settings.policy_annexes_path) / v_str

    resolved: dict[str, Question] = {}
    for node_id, question in questions.items():
        articles, annexes = provisions.get(node_id, ((), ()))
        chunks: list[str] = []
        for n in articles:
            p = art_dir / f"article-{n:03d}.md"
            if not p.is_file():
                raise FileNotFoundError(
                    f"{node_id}: no stored text for Article {n} at {p}. Run: "
                    f"python scripts/fetch_articles.py --version-date {v_str}"
                )
            chunks.append(provision_text(p))
        for roman in annexes:
            p = ann_dir / f"annex-{roman}.md"
            if not p.is_file():
                raise FileNotFoundError(
                    f"{node_id}: no stored text for Annex {roman} at {p}. Run: "
                    f"python scripts/fetch_articles.py --version-date {v_str}"
                )
            chunks.append(provision_text(p))

        # Non-binding guidance, where the enacted text leaves the question open.
        g_chunks: list[str] = []
        g_sources: list[GuidanceSource] = []
        for ref in (guidance or {}).get(node_id, ()):
            snippet = load_snippet(ref, guidance_root)
            g_chunks.append(f"[{snippet.document}, {snippet.locator}]\n{snippet.body}")
            g_sources.append(snippet.to_source())

        resolved[node_id] = replace(
            question,
            context="\n\n".join(chunks),
            guidance_context="\n\n".join(g_chunks),
            guidance_sources=tuple(g_sources),
        )
    return resolved
