"""Split a technical-documentation file into retrievable chunks.

The unit of retrieval is a piece of the PROVIDER'S DOCUMENT, never a piece of the law — the law is
resolved verbatim from the article store (policy_loader) and goes into the prompt whole. What is
searched is the evidence: "where in this document, if anywhere, does the provider address Art. 14?"

Chunking is heading-aware because provider technical files are written in sections, and a section is
the natural evidence unit — a human reviewer answers "is Art. 14 satisfied?" by reading the
oversight section, not a sliding window. Two consequences are deliberate:

  - The heading path is PREPENDED to the text that gets embedded. A paragraph reading "the reviewer
    may return the case to the panel" is nearly meaningless alone and unambiguous under
    "Part E — Oversight by managers and panels".

  - Section order and numbering are never assumed. The two reference documents deliberately
    disagree (`## 2. Risk management system` vs `## Part C — Risk management`, and Part C comes
    AFTER the data section) precisely so a checker keyed to position breaks here, not in production.

Character offsets into the original document are carried through so a later verdict can locate its
evidence instead of paraphrasing it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from math import ceil
from pathlib import Path

# A markdown ATX heading: leading #s, then the title.
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")

# A SETEXT heading underline: `===` (level 1) or `---` (level 2) under the title text. Without it a
# document written this way yields no sections at all — empty heading paths, no outline, nothing for
# cross-references to resolve against.
#
# `---` is also a horizontal rule. A setext title must therefore be an ISOLATED line, preceded by a
# blank line, so a `---` following the last line of a paragraph stays a rule.
_SETEXT = re.compile(r"^(=+|-+)\s*$")

# Sentence end: .!? followed by whitespace. Split AFTER the punctuation so quotes stay whole.
# Deliberately crude — this only ever runs on paragraphs already too long to embed, where the cost
# of an odd split at "e.g. " is far below the cost of text no search can reach.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

# Zero-width position just after a newline — the fallback boundary for content with no sentences.
_LINE_END = re.compile(r"(?<=\n)")

# The budget is in TOKENS because the constraint is a token limit: all-MiniLM-L6-v2 truncates at 128
# (set in its own tokenizer.json, not the 512 its `max_position_embeddings` suggests). Text past the
# limit is dropped when the vector is computed, so the chunk cannot be found by whatever its tail
# said — silently, with no error.
#
# A character cap cannot express this. Chars-per-token across the corpus runs 2.16 (dense tables) to
# 10.9 (short list lines) against ~4.3 for prose, so any character constant is wrong by up to 5x
# depending on content — and would need retuning for every embedding model and language.
MAX_TOKENS = 128

# Fallback when the model's tokenizer is not on disk (fresh clone, CI without the download).
# Deliberately pessimistic — near the dense end of the observed range — so it over-counts prose and
# splits early: an undersized chunk costs a little context, an oversized one is silently truncated.
FALLBACK_CHARS_PER_TOKEN = 2.5


TokenCounter = Callable[[str], int]

# Path Chroma downloads its bundled model to. Read-only here; we borrow its tokenizer so the chunker
# counts with the SAME vocabulary the embedder will use. Approximating it would defeat the purpose.
_TOKENIZER_PATH = Path.home() / ".cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx/tokenizer.json"


@lru_cache(maxsize=1)
def default_token_counter() -> tuple[TokenCounter, bool]:
    """Return (counter, is_exact).

    Exact when the embedding model's tokenizer is on disk; otherwise a character estimate. The flag
    is returned rather than logged so callers and tests can SEE which one ran — a silent fallback
    that changes how documents are split is exactly the kind of invisible behaviour this project
    refuses elsewhere.

    Truncation and padding are switched off: both are fixed at 128 in the shipped config, so leaving
    them on makes every string measure exactly 128 tokens and the budget meaningless.
    """
    try:
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_file(str(_TOKENIZER_PATH))
        tokenizer.no_truncation()
        tokenizer.no_padding()
    except Exception:
        return (lambda text: ceil(len(text) / FALLBACK_CHARS_PER_TOKEN), False)

    return (lambda text: len(tokenizer.encode(text).ids), True)


@dataclass(frozen=True)
class Chunk:
    """One retrievable passage of a provider document."""

    chunk_id: str  # stable within a document: "c000", "c001", ...
    body: str  # the passage as it appears in the document
    heading_path: str  # "Part E — Oversight by managers and panels > E.2 Escalation"
    char_start: int  # offset into the original document, for locating the evidence
    char_end: int

    @property
    def text(self) -> str:
        """What gets embedded and shown to the model: the passage under its heading path.

        The heading is part of the evidence, not decoration — "we log every decision" means one
        thing under "Part F — Event records" and another under a marketing section.
        """
        return f"{self.heading_path}\n\n{self.body}" if self.heading_path else self.body


@dataclass(frozen=True)
class _Paragraph:
    body: str
    heading_path: str
    char_start: int
    char_end: int


def _paragraphs(text: str) -> list[_Paragraph]:
    """Walk the document once, emitting blank-line-separated paragraphs tagged with their heading
    path. A heading itself is never emitted as content — it lives in the path of what follows."""
    out: list[_Paragraph] = []
    stack: list[tuple[int, str]] = []  # (level, title), outermost first
    lines: list[str] = []
    start = end = 0
    offset = 0
    skip_underline = False

    def close() -> None:
        nonlocal lines
        if lines:
            out.append(
                _Paragraph(
                    body="\n".join(lines),
                    heading_path=" > ".join(t for _, t in stack),
                    char_start=start,
                    char_end=end,
                )
            )
            lines = []

    raw_lines = text.splitlines(keepends=True)
    for position, raw in enumerate(raw_lines):
        line_start, offset = offset, offset + len(raw)
        line = raw.rstrip("\n")

        # Setext: this line is the title, the next underlines it. Isolated titles only.
        if line.strip() and not lines and position + 1 < len(raw_lines):
            underline = _SETEXT.match(raw_lines[position + 1].rstrip("\n"))
            if underline and len(underline.group(1)) >= 3:
                close()
                level = 1 if underline.group(1).startswith("=") else 2
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, line.strip()))
                skip_underline = True
                continue

        if skip_underline:
            skip_underline = False
            if _SETEXT.match(line):
                continue

        if heading := _HEADING.match(line):
            close()
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading.group(2)))
            continue

        if not line.strip():
            close()
            continue

        if not lines:
            start = line_start
        lines.append(line)
        end = offset

    close()
    return out


def _slice(para: _Paragraph, begin: int, end: int) -> _Paragraph:
    """A sub-span of a paragraph, offsets shifted to stay true to the source."""
    return _Paragraph(
        body=para.body[begin:end],
        heading_path=para.heading_path,
        char_start=para.char_start + begin,
        char_end=para.char_start + end,
    )


def _split_to_fit(para: _Paragraph, fits: Callable[[str], bool]) -> list[_Paragraph]:
    """Break a paragraph that exceeds the budget into pieces that fit.

    Cuts fall BETWEEN sentences, so every quotable unit stays whole and every sentence stays
    findable.

    Sentences first, then LINES for whatever still does not fit — markdown tables are one paragraph
    with no sentence-ending punctuation, and a table row is its own record. Lines come second
    because in prose a line break is a soft wrap sitting mid-sentence.
    """
    if fits(para.body):
        return [para]
    pieces = _split_on(para, _SENTENCE_END, fits)
    return [
        out
        for piece in pieces
        for out in ([piece] if fits(piece.body) else _split_on(piece, _LINE_END, fits))
    ]


def _split_on(
    para: _Paragraph, boundary: re.Pattern[str], fits: Callable[[str], bool]
) -> list[_Paragraph]:
    """Greedily pack `para` into pieces cut at `boundary`, keeping offsets true to the source.

    Cuts are taken by INDEX into the original body, never by splitting and rejoining: a paragraph
    carries its own newlines, and reassembling it with spaces would rewrite the text while the
    offsets went on claiming otherwise.
    """
    bounds = [0, *(m.start() for m in boundary.finditer(para.body)), len(para.body)]
    if len(bounds) <= 2:
        return [para]  # no boundary to cut on; the caller's next pass (or truncation) handles it
    pieces: list[_Paragraph] = []
    begin = 0
    for i, cut in enumerate(bounds[1:], start=1):
        last = i == len(bounds) - 1
        # Close the piece just BEFORE the sentence that would overflow, so what we emit still fits.
        if not fits(para.body[begin:cut]) or last:
            stop = cut if (last and fits(para.body[begin:cut])) else bounds[i - 1]
            if stop <= begin:
                # One sentence alone exceeds the budget. Emit it anyway and let it truncate:
                # dropping documentation is never an option, and a partly-embedded sentence is
                # still better evidence than a missing one.
                stop = cut
            if para.body[begin:stop].strip():
                pieces.append(_slice(para, begin, stop))
            begin = stop
    if begin < len(para.body) and para.body[begin:].strip():
        pieces.append(_slice(para, begin, len(para.body)))
    return pieces or [para]


def chunk_document(
    text: str,
    max_tokens: int = MAX_TOKENS,
    count_tokens: TokenCounter | None = None,
) -> list[Chunk]:
    """Split a document into heading-scoped chunks that fit the embedding window.

    Paragraphs are the atom: a chunk grows paragraph by paragraph and closes when adding the next
    would exceed `max_tokens`. A heading change always closes the chunk, so evidence never straddles
    two sections — a passage retrieved for Art. 14 must not silently carry half of Art. 15's section
    with it, or the model would credit the wrong obligation.

    The budget is charged against `Chunk.text` — heading path INCLUDED — because that is the string
    the embedder actually sees. The path costs 9-26 tokens on this corpus, a fifth of the window, so
    a budget that ignored it would overshoot on every chunk.

    `count_tokens` defaults to the embedding model's own tokenizer, falling back to a character
    estimate when the model is not on disk. Pass one explicitly to chunk for a different model
    without touching this code — which is the point of counting tokens rather than characters.
    """
    counter = count_tokens or default_token_counter()[0]
    chunks: list[Chunk] = []
    open_paras: list[_Paragraph] = []

    def fits_under(heading_path: str) -> Callable[[str], bool]:
        prefix = f"{heading_path}\n\n" if heading_path else ""
        return lambda body: counter(prefix + body) <= max_tokens

    def flush() -> None:
        if not open_paras:
            return
        chunks.append(
            Chunk(
                chunk_id=f"c{len(chunks):03d}",
                body="\n\n".join(p.body for p in open_paras),
                heading_path=open_paras[0].heading_path,
                char_start=open_paras[0].char_start,
                char_end=open_paras[-1].char_end,
            )
        )
        open_paras.clear()

    for whole in _paragraphs(text):
        fits = fits_under(whole.heading_path)
        for para in _split_to_fit(whole, fits):
            same_section = bool(open_paras) and para.heading_path == open_paras[0].heading_path
            packed = "\n\n".join([*(p.body for p in open_paras), para.body])
            if open_paras and not (same_section and fits(packed)):
                flush()
            open_paras.append(para)

    flush()
    return chunks
