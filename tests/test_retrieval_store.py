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
import re
from pathlib import Path

import chromadb
import pytest
from chromadb.api.types import EmbeddingFunction

from aiact.policy_loader import load_policy_spec
from aiact.retrieval.chunking import chunk_document
from aiact.retrieval.store import Chunk, DocumentIndex, Hit, document_id
from aiact.tools.evidence import find_evidence, queries_for, query_for

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
    before = client.get_collection(first.collection_name).count()
    second = _index(DOC_A, client)
    assert second.doc_id == first.doc_id
    assert client.get_collection(second.collection_name).count() == before


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
    name = index.collection_name
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
    assert client.get_collection(index.collection_name).count() == len(index.chunks)


# ==================================================================================================
# The tool the checker calls per rule
# ==================================================================================================
@pytest.fixture(scope="module")
def spec():
    return load_policy_spec()


def test_the_query_is_the_evidence_hint_not_the_enacted_text(spec):
    """Legislative register retrieves badly against product prose. `evidence_expected` was written
    in the register of documentation, which is what is being searched."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-HR-A14")
    assert query_for(rule) == rule.evidence_expected
    assert query_for(rule) != rule.requirement


def test_process_obligations_are_never_searched_for(spec):
    """Art. 17's quality management system cannot be evidenced by a technical file. Retrieval would
    still return four paragraphs, and a checker would have every chance to talk itself into PASS."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-PO-A17")
    assert not rule.document_verifiable
    with pytest.raises(ValueError, match="not document-verifiable"):
        find_evidence(object(), rule)  # type: ignore[arg-type]  # never reaches the index


def test_find_evidence_returns_passages_for_a_document_verifiable_rule(client, spec):
    """k is a FLOOR. Art. 14 names more duties than the k asked for, and each takes a slot, so the
    result is as long as the facet count — the alternative is duties the judge rules on without
    being shown anything."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-HR-A14")
    index = _index(DEV_DOC.read_text(encoding="utf-8"), client)
    hits = find_evidence(index, rule, k=3)
    assert len(hits) == len(queries_for(rule))
    assert all(h.chunk.chunk_id in index.chunks for h in hits)


def test_a_rule_with_few_duties_still_gets_the_whole_budget(client, spec):
    """The floor cuts one way only: a rule naming fewer duties than k asked for keeps k passages,
    because k answers a different question — how much of the document the judge needs to see to
    read a section in context."""
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-PO-A16-B")
    assert len(queries_for(rule)) < 6
    index = _index(DEV_DOC.read_text(encoding="utf-8"), client)
    assert len(find_evidence(index, rule, k=6)) == 6


def test_every_duty_the_evidence_text_names_gets_a_passage_of_its_own(spec):
    """The retrieval budget is spent per duty, not per ranking.

    `evidence_expected` is the query, and a rule that names several duties embeds to a point near
    whichever of them most of the text is about. The passage that BREACHES one of the others is
    then outside the result set entirely — and `judge` tells the model to read absence from the
    excerpts as absence from the document, so an unretrieved breach becomes a PASS.

    Asserted on the ALLOCATION and not on an embedding: what has to hold is that each facet takes
    its best unclaimed passage before any facet takes a second, and that is a property of the
    round-robin rather than of how MiniLM ranks a paragraph. A fake index gives each query its own
    ranking, so a merge by distance and a merge by facet produce visibly different sets.
    """
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-HR-A15")
    facets = queries_for(rule)
    assert len(facets) > 3, "Art. 15 names accuracy, robustness, feedback loops and five attacks"

    class OneRankingPerQuery:
        """Every query ranks a chunk of its own first, then falls back to a shared tail."""

        def search(self, query: str, k: int) -> list[Hit]:
            own = f"own-{facets.index(query)}"
            return [_fake_hit(own)] + [_fake_hit(f"tail-{i}") for i in range(k)]

    # k deliberately BELOW the facet count: the guarantee under test is that `find_evidence`
    # raises its own budget to fit the duties, not that a caller happened to ask for enough.
    hits = find_evidence(OneRankingPerQuery(), rule, k=3)  # type: ignore[arg-type]
    assert [h.chunk.chunk_id for h in hits] == [f"own-{i}" for i in range(len(facets))], (
        "a facet was crowded out of its own budget: the duties a rule names after the first "
        "reach the judge only if each is searched for in its own right"
    )


def _fake_hit(chunk_id: str) -> Hit:
    chunk = Chunk(
        chunk_id=chunk_id, body=chunk_id, heading_path=chunk_id, char_start=0, char_end=0
    )
    return Hit(chunk=chunk, distance=1.0)


def test_a_different_embedder_gets_a_different_index(client):
    """Vectors from two models are not comparable, so an index built by one is meaningless to
    another however identical the document is. Keying on the document hash alone would serve stale
    vectors after an embedding-model swap."""
    stub = DocumentIndex.build(DOC_A, client=client, embedding_function=StubEmbedding())

    class OtherStub(StubEmbedding):
        @staticmethod
        def name() -> str:
            return "other"

    other = DocumentIndex.build(DOC_A, client=client, embedding_function=OtherStub())
    assert other.doc_id == stub.doc_id, "same document"
    assert other.collection_name != stub.collection_name, "but not the same index"


def test_no_facet_is_a_citation_the_splitter_cut_in_half(spec):
    """A query that begins mid-citation names no duty and spends a slot on nothing.

    Evidence texts cite the Act in the middle of clauses — "under Art. 15(4) however strong its
    accuracy figures are" — and the full stop in `Art.` is the same character that ends a sentence.
    Cut there, the tail starts with the paragraph number and reads as a fragment: too long for the
    word-count filter to drop, too incoherent to retrieve the passage the clause was about. Each
    one displaces a real duty from the budget."""
    for rule in spec.rules:
        if not rule.document_verifiable:
            continue
        for facet in queries_for(rule):
            assert not re.match(r"^\d+[(.]", facet), (
                f"{rule.rule_id} has a retrieval query starting {facet[:40]!r} — the splitter cut "
                f"a citation. Add the abbreviation to `_SENTENCE_END`."
            )
