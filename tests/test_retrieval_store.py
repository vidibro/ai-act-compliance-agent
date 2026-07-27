"""The Chroma layer, tested with a stub embedder.

Deliberately NOT tested against the real embedding model. What is pinned here is the store's
plumbing — isolation between documents, idempotent indexing, id-to-chunk mapping, k handling — and
none of that should depend on a downloaded ONNX model being present, or on how well MiniLM happens
to rank a paragraph. Retrieval QUALITY is an eval question (M5), not a test question: it has no
correct answer to assert, only a score to report.

The stub is a deterministic bag-of-words vector, so "similar" here means "shares vocabulary". That
is enough to prove the wiring carries a query to the right chunk and back.
"""

from __future__ import annotations

import math
from pathlib import Path

import chromadb
import pytest
from chromadb.api.types import EmbeddingFunction

from aiact.policy_loader import load_policy_spec
from aiact.retrieval.chunking import chunk_document
from aiact.retrieval.store import DocumentIndex, document_id
from aiact.tools.evidence import find_evidence, query_for

ROOT = Path(__file__).resolve().parents[1]
DEV_DOC = ROOT / "data" / "golden_set" / "cases" / "pristine__untouched.md"
HELDOUT_DOC = ROOT / "data" / "golden_set" / "cases-heldout" / "pristine__untouched.md"

_VOCAB = [
    "oversight",
    "accuracy",
    "logging",
    "data",
    "risk",
    "instructions",
    "documentation",
    "panel",
]


class StubEmbedding(EmbeddingFunction):
    """Deterministic, offline, and dependency-free: one dimension per vocabulary word.

    Subclasses Chroma's base class rather than duck-typing it — the base supplies `embed_query`,
    `get_config` and the rest of the protocol Chroma 1.x calls into.
    """

    def __init__(self) -> None:  # required by Chroma's config round-trip
        pass

    @staticmethod
    def name() -> str:
        return "stub"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> StubEmbedding:
        return StubEmbedding()

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002 - Chroma's signature
        vectors = []
        for text in input:
            lower = text.lower()
            raw = [float(lower.count(word)) for word in _VOCAB]
            norm = math.sqrt(sum(v * v for v in raw)) or 1.0
            vectors.append([v / norm for v in raw])
        return vectors


@pytest.fixture
def client():
    return chromadb.EphemeralClient()


def _index(text: str, client) -> DocumentIndex:
    return DocumentIndex.build(text, client=client, embedding_function=StubEmbedding())


DOC_A = """\
# Alpha System

## Human oversight
A panel reviews every decision and may override it. Oversight is continuous.

## Accuracy
Accuracy is measured as AUC.
"""

DOC_B = """\
# Beta System

## Logging
Events are logged automatically.
"""


def test_a_document_is_searchable_by_topic(client):
    index = _index(DOC_A, client)
    hits = index.search("oversight by a human panel", k=1)
    assert len(hits) == 1
    assert "Human oversight" in hits[0].chunk.heading_path
    assert "panel reviews every decision" in hits[0].chunk.body


def test_hits_carry_a_locator_that_points_into_the_source(client):
    """A verdict cites this string. It must name the section AND resolve to the quoted text."""
    index = _index(DOC_A, client)
    hit = index.search("oversight", k=1)[0]
    assert "Human oversight" in hit.locator
    assert DOC_A[hit.chunk.char_start : hit.chunk.char_end].strip() == hit.chunk.body.strip()


def test_documents_cannot_leak_into_each_others_results(client):
    """The failure this design exists to prevent: crediting one provider with another's evidence.

    Both documents live in the same Chroma client. Beta's file says nothing about oversight; asking
    it must never surface Alpha's oversight section, no matter how good a match that is."""
    _index(DOC_A, client)
    beta = _index(DOC_B, client)
    hits = beta.search("oversight by a human panel", k=5)
    assert hits, "a search always returns something — that is the point of the next assertion"
    assert all("panel reviews every decision" not in h.chunk.body for h in hits)
    assert {h.chunk.chunk_id for h in hits} <= set(beta.chunks)


def test_search_always_returns_results_even_when_the_topic_is_absent(client):
    """Pinned because everything built on top must assume it. Vector search has no 'no match': the
    document with nothing to say about oversight still returns its least-unrelated paragraph. So
    retrieval alone can never conclude GAP — only a judge reading the passages can."""
    index = _index(DOC_B, client)
    hits = index.search("human oversight measures and the competencies of the overseer", k=1)
    assert len(hits) == 1
    assert "oversight" not in hits[0].chunk.body.lower()


def test_indexing_the_same_document_twice_reuses_the_collection(client):
    """The eval re-runs constantly; re-embedding an unchanged document each time is pure waste."""
    first = _index(DOC_A, client)
    before = client.get_collection(f"doc-{first.doc_id[:32]}").count()
    second = _index(DOC_A, client)
    assert second.doc_id == first.doc_id
    assert client.get_collection(f"doc-{second.doc_id[:32]}").count() == before


def test_a_changed_document_gets_a_different_index(client):
    """One character of difference must not be served from the old index."""
    edited = DOC_A.replace("may override it", "may not override it")
    assert _index(DOC_A, client).doc_id != _index(edited, client).doc_id


def test_document_id_is_the_content_hash():
    assert document_id(DOC_A) == document_id(DOC_A)
    assert document_id(DOC_A) != document_id(DOC_B)


def test_k_is_capped_at_the_number_of_chunks(client):
    """Asking for more passages than exist must not pad or repeat — a judge counting evidence would
    read a duplicate as corroboration."""
    index = _index(DOC_B, client)
    hits = index.search("logging", k=50)
    assert len(hits) == len(index.chunks)
    assert len({h.chunk.chunk_id for h in hits}) == len(hits)


def test_the_default_index_writes_nothing_to_disk(tmp_path, monkeypatch):
    """The privacy default, pinned. The indexed text is a provider's confidential technical file;
    with no client passed, it must live in memory and leave nothing behind. This is the assertion
    that keeps SECURITY.md's "no stored user data" true — a future convenience change that flips
    the default back to persistence breaks here rather than in production."""
    monkeypatch.setenv("AIACT_CHROMA_PATH", str(tmp_path / "chroma"))
    index = DocumentIndex.build(DOC_A, embedding_function=StubEmbedding())
    assert index.search("oversight", k=1), "the in-memory index must be fully usable"
    assert not (tmp_path / "chroma").exists(), "the default index touched the disk"


def test_a_persisted_index_can_be_dropped(tmp_path):
    """The only cleanup path for a caller that opts into persistence."""
    from aiact.retrieval.store import persistent_client

    chroma = persistent_client(tmp_path / "chroma")
    index = DocumentIndex.build(DOC_A, client=chroma, embedding_function=StubEmbedding())
    name = f"doc-{index.doc_id[:32]}"
    assert name in [c.name for c in chroma.list_collections()]
    index.drop()
    assert name not in [c.name for c in chroma.list_collections()]


def test_an_empty_query_is_refused(client):
    index = _index(DOC_A, client)
    with pytest.raises(ValueError, match="Empty retrieval query"):
        index.search("   ")


def test_an_empty_document_is_refused(client):
    with pytest.raises(ValueError, match="empty document"):
        DocumentIndex.build("\n\n", client=client, embedding_function=StubEmbedding())


def test_every_chunk_of_a_real_document_is_indexed(client):
    text = DEV_DOC.read_text(encoding="utf-8")
    index = _index(text, client)
    assert len(index.chunks) == len(chunk_document(text))
    assert client.get_collection(f"doc-{index.doc_id[:32]}").count() == len(index.chunks)


# ==================================================================================================
# The tool the checker calls per rule
# ==================================================================================================
@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


def test_the_query_is_the_evidence_hint_not_the_enacted_text(spec):
    """Legislative register retrieves badly against product prose. `evidence_expected` was written
    in the register of documentation, which is what is being searched."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-HR-A14")
    assert query_for(rule) == rule.evidence_expected
    assert query_for(rule) != rule.requirement


def test_process_obligations_are_never_searched_for(spec):
    """Art. 17's quality management system cannot be evidenced by a technical file. Retrieval would
    still return four paragraphs, and a checker would have every chance to talk itself into PASS."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-PO-A17")
    assert not rule.document_verifiable
    with pytest.raises(ValueError, match="not document-verifiable"):
        find_evidence(object(), rule)  # type: ignore[arg-type]  # never reaches the index


def test_find_evidence_returns_passages_for_a_document_verifiable_rule(client, spec):
    rule = next(r for r in spec.rules if r.rule_id == "AIA-HR-A14")
    index = _index(DEV_DOC.read_text(encoding="utf-8"), client)
    hits = find_evidence(index, rule, k=3)
    assert len(hits) == 3
    assert all(h.chunk.chunk_id in index.chunks for h in hits)
