"""Chunking is deterministic plumbing, so it is tested, not evaluated.

The properties pinned here are the ones a gap verdict later rests on: evidence must not straddle two
obligations' sections, and a quoted offset must actually point at the quoted text. Both are silent
failures if wrong — the checker would still produce confident verdicts, just against the wrong prose
or with citations that do not resolve.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aiact.retrieval.chunking import MAX_TOKENS, chunk_document, default_token_counter

ROOT = Path(__file__).resolve().parents[1]
CORPUS = [
    ROOT / "data" / "golden_set" / "cases" / "pristine__untouched.md",
    ROOT / "data" / "golden_set" / "cases-heldout" / "pristine__untouched.md",
]

DOC = """\
# Product File

Intro paragraph.

## Part A — Oversight

Panels may return a case.

Reviewers are trained annually.

## Part B — Accuracy

AUC is 0.81 on the validation set.
"""


def test_headings_become_the_path_and_are_not_content():
    chunks = chunk_document(DOC)
    paths = [c.heading_path for c in chunks]
    assert paths == [
        "Product File",
        "Product File > Part A — Oversight",
        "Product File > Part B — Accuracy",
    ]
    # The heading line itself is never part of a body — it is context, not evidence.
    assert all(not c.body.lstrip().startswith("#") for c in chunks)


def test_a_chunk_never_spans_two_sections():
    """The property the whole design exists for: evidence retrieved for Art. 14 must not arrive
    carrying half of Art. 15's section, or the model credits the wrong obligation."""
    chunks = chunk_document(DOC)
    oversight = next(c for c in chunks if "Oversight" in c.heading_path)
    assert "AUC" not in oversight.body
    assert "Panels may return a case." in oversight.body
    assert "Reviewers are trained annually." in oversight.body


def test_heading_path_is_prepended_to_the_embedded_text():
    """`body` is what the document says; `text` is what gets embedded. A passage read without its
    section heading is frequently meaningless."""
    chunk = next(c for c in chunk_document(DOC) if "Accuracy" in c.heading_path)
    assert chunk.text.startswith("Product File > Part B — Accuracy")
    assert chunk.body == "AUC is 0.81 on the validation set."


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.parent.name)
def test_offsets_point_at_the_text_they_claim(path: Path):
    """A verdict cites `chars N-M`. If that does not resolve to the quoted evidence, the citation
    is decoration — the exact failure the project refuses everywhere else."""
    text = path.read_text(encoding="utf-8")
    for chunk in chunk_document(text):
        assert text[chunk.char_start : chunk.char_end].strip() == chunk.body.strip()


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.parent.name)
def test_the_whole_corpus_chunks_into_bounded_sections(path: Path):
    text = path.read_text(encoding="utf-8")
    chunks = chunk_document(text)
    assert len(chunks) > 10, "a full technical file should not collapse into a handful of chunks"
    assert all(c.chunk_id for c in chunks)
    assert len({c.chunk_id for c in chunks}) == len(chunks), "chunk ids must be unique"


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.parent.name)
def test_chunking_covers_every_section_of_the_document(path: Path):
    """No section may be dropped. A silently unindexed section is an automatic false GAP for
    whatever obligation it evidenced."""
    text = path.read_text(encoding="utf-8")
    headings = {line.lstrip("#").strip() for line in text.splitlines() if line.startswith("## ")}
    covered = {part for c in chunk_document(text) for part in c.heading_path.split(" > ")}
    assert headings <= covered, f"sections missing from the index: {sorted(headings - covered)}"


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.parent.name)
def test_every_chunk_fits_the_embedding_window(path: Path):
    """The whole reason the budget is counted in tokens rather than characters.

    all-MiniLM-L6-v2 truncates at 128 tokens, configured in its own tokenizer.json. Text past that
    is dropped when the vector is computed, silently, so the chunk cannot be found by whatever its
    tail said. Chars-per-token swings from 2.16 to 10.9 across this corpus, which is why no
    character cap can make this assertion say EVERY.
    """
    count, exact = default_token_counter()
    if not exact:
        pytest.skip("embedding model not downloaded; the character estimate is not the real budget")
    for chunk in chunk_document(path.read_text(encoding="utf-8")):
        assert count(chunk.text) <= MAX_TOKENS, (
            f"{chunk.chunk_id} is {count(chunk.text)} tokens under "
            f"{chunk.heading_path!r} — its tail will be silently unsearchable"
        )


def test_the_budget_is_charged_against_the_embedded_text_not_the_body():
    """The heading path is embedded too, and costs 9-26 tokens on this corpus — a fifth of the
    window. A budget that measured only the body would overshoot on every single chunk."""
    count, exact = default_token_counter()
    if not exact:
        pytest.skip("embedding model not downloaded")
    long_heading = "A " + " > ".join(
        f"Section {i} with a deliberately wordy title" for i in range(4)
    )
    text = f"# {long_heading}\n\n" + "The provider documents its oversight measures. " * 20
    for chunk in chunk_document(text):
        assert count(chunk.text) <= MAX_TOKENS


def test_a_custom_counter_is_honoured():
    """Swapping the embedding model must not mean re-tuning the chunker — that is the payoff for
    counting tokens. A caller supplies the new model's counter and window; nothing here changes."""
    words = lambda s: len(s.split())  # noqa: E731 - a stand-in for another model's tokenizer
    text = CORPUS[0].read_text(encoding="utf-8")

    tiny = chunk_document(text, max_tokens=40, count_tokens=words)
    roomy = chunk_document(text, max_tokens=400, count_tokens=words)
    assert len(tiny) > len(roomy), "a smaller window must produce more, smaller chunks"

    # The budget is respected in the caller's units, not ours. Pieces that cannot be divided any
    # further (a table row, a single long sentence) are the documented exception.
    honoured = sum(1 for c in roomy if words(c.text) <= 400)
    assert honoured == len(roomy)


def test_an_overlong_paragraph_is_split_between_sentences():
    """An indivisible dense paragraph is mostly invisible to search, so it must be split — but
    never mid-sentence: a verdict quoting half a sentence is its own failure."""
    long_para = " ".join(f"Sentence number {i} states a concrete measure." for i in range(40))
    text = f"# Doc\n\n## Section\n\n{long_para}\n"
    chunks = chunk_document(text)
    assert len(chunks) > 1, "an over-long paragraph must be split, not embedded half-blind"
    for chunk in chunks:
        assert chunk.body.strip().endswith("."), f"{chunk.chunk_id} was cut mid-sentence"
        assert text[chunk.char_start : chunk.char_end].strip() == chunk.body.strip()


def test_chunking_is_deterministic():
    """Same bytes, same chunks — the content-addressed collection in store.py depends on it."""
    text = CORPUS[0].read_text(encoding="utf-8")
    assert chunk_document(text) == chunk_document(text)


def test_an_empty_document_produces_no_chunks():
    assert chunk_document("") == []
    assert chunk_document("\n\n   \n") == []
