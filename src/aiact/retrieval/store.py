"""Index one provider document in Chroma and search it.

Scope, stated up front because it is the load-bearing decision: **one collection per document,
named by the sha256 of that document's text.** Consequences, both intended:

  - No cross-document leakage, by construction. A gap checker that retrieved a paragraph from a
    DIFFERENT provider's file and credited this provider with it would be the worst bug this project
    could ship — it would certify compliance from evidence that does not exist. Collection-per-
    document makes that unreachable rather than merely unlikely; there is no shared index to leak
    from, and no metadata filter to forget.

  - Idempotent and cheap to re-run. The collection name IS the content hash, so re-indexing the same
    document is a no-op. Change one character and it is a different collection, so a stale index
    cannot be served for edited text.

**The index is IN-MEMORY by default and nothing is written to disk.** The tool's job is one-shot:
ingest a document, ask each obligation where its evidence is, emit a report. Nothing needs to
outlive the process, and the document being indexed is a provider's confidential technical file —
so the default posture is to keep no copy of it. Re-embedding costs ~300 ms for a 22k-character
document, which is nothing beside the LLM calls that follow.

Persistence is opt-in (`persistent_client()`), for the eval, where re-embedding the same 38 corpus
documents on every run is pure waste. A persisted index is a CACHE of a document we already have on
disk in the repo, never a store of user data — and `DocumentIndex.drop()` exists so a caller that
opts in can also clean up.

A note that shapes everything built on top: **a vector search always returns k results.** There is
no "nothing found" — ask an empty-ish document about Art. 14 and it hands back its k least-unrelated
paragraphs with confident-looking ranks. Retrieval therefore cannot decide GAP; it can only put
candidate evidence in front of a judge. `distance` is exposed on every hit so the judge can see how
weak a match actually was.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiact.config import get_settings
from aiact.retrieval.chunking import MAX_TOKENS, Chunk, chunk_document

if TYPE_CHECKING:  # pragma: no cover - typing only
    from chromadb.api import ClientAPI


@dataclass(frozen=True)
class Hit:
    """One retrieved passage and how well it matched."""

    chunk: Chunk
    distance: float
    """Cosine distance — LOWER is closer. Never a probability and never a verdict: the top hit in a
    document that says nothing about the obligation is still the top hit. Carried so a checker can
    weigh weak evidence as weak."""

    @property
    def locator(self) -> str:
        """Human-checkable pointer to where the evidence sits, for a verdict to cite."""
        return f"{self.chunk.heading_path} [chars {self.chunk.char_start}-{self.chunk.char_end}]"


def document_id(text: str) -> str:
    """Content address of a document. Same bytes, same collection — that is the whole caching and
    isolation story in one function."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _collection_name(doc_id: str) -> str:
    # Chroma requires 3-512 chars from [a-zA-Z0-9._-], starting and ending alphanumeric.
    return f"doc-{doc_id[:32]}"


def ephemeral_client() -> ClientAPI:
    """An in-memory Chroma client — the default. Its index lives in this process and dies with it.

    Same HNSW index and same API as the persistent client; it simply never touches disk. That is the
    whole difference, and it is why "store nothing" costs nothing here but a re-embed.
    """
    import chromadb

    return chromadb.EphemeralClient()


def persistent_client(path: str | Path | None = None) -> ClientAPI:
    """An on-disk Chroma client. OPT-IN — see the module docstring.

    Intended for the eval, whose 38 corpus documents are already in the repo and re-embedding them
    on every run buys nothing. Do not reach for this to index a user's document: an index that
    outlives the run is a copy of their confidential file that nobody asked us to keep.
    """
    import chromadb

    return chromadb.PersistentClient(path=str(path or get_settings().chroma_path))


class DocumentIndex:
    """A single provider document, chunked and searchable.

    Built via `DocumentIndex.build(...)`, which is idempotent: if the collection for this document's
    hash already holds the expected number of chunks, nothing is re-embedded.
    """

    def __init__(self, doc_id: str, chunks: list[Chunk], collection: Any, client: Any) -> None:
        self.doc_id = doc_id
        self.chunks = {c.chunk_id: c for c in chunks}
        self._collection = collection
        self._client = client

    @classmethod
    def build(
        cls,
        text: str,
        *,
        client: ClientAPI | None = None,
        max_tokens: int = MAX_TOKENS,
        embedding_function: Any = None,
    ) -> DocumentIndex:
        """Chunk `text` and index it, reusing an existing index for identical text.

        With no `client`, the index is in-memory and disappears when the process does. Pass
        `persistent_client()` explicitly to keep it — and see the module docstring for when that is
        and is not appropriate.
        """
        doc_id = document_id(text)
        chunks = chunk_document(text, max_tokens=max_tokens)
        if not chunks:
            raise ValueError("Refusing to index an empty document — nothing to retrieve against.")

        chroma = client if client is not None else ephemeral_client()
        kwargs: dict[str, Any] = {"name": _collection_name(doc_id)}
        if embedding_function is not None:
            kwargs["embedding_function"] = embedding_function
        collection = chroma.get_or_create_collection(**kwargs)

        if collection.count() != len(chunks):
            # Either brand new, or a partial write from an interrupted run. Re-add rather than
            # trust it: `add` with existing ids is an upsert-by-id here, and a half-indexed document
            # would silently hide whole sections from every search made against it.
            collection.add(
                ids=[c.chunk_id for c in chunks],
                documents=[c.text for c in chunks],
                metadatas=[
                    {
                        "heading_path": c.heading_path,
                        "char_start": c.char_start,
                        "char_end": c.char_end,
                    }
                    for c in chunks
                ],
            )
        return cls(doc_id, chunks, collection, chroma)

    def drop(self) -> None:
        """Delete this document's index.

        A no-op worth having for the ephemeral default (the process exit does it anyway), and the
        only cleanup path for a caller that opted into persistence. Without it, "we store nothing"
        would be true only until someone passed a persistent client.
        """
        self._client.delete_collection(_collection_name(self.doc_id))

    def search(self, query: str, k: int = 4) -> list[Hit]:
        """The k passages closest to `query`, nearest first.

        `k` is capped at the chunk count so a short document does not produce padded or duplicated
        hits — a checker counting evidence should never see the same paragraph twice.
        """
        if not query.strip():
            raise ValueError("Empty retrieval query — a rule must say what evidence it is after.")
        n = min(k, len(self.chunks))
        result = self._collection.query(query_texts=[query], n_results=n)
        ids = result["ids"][0]
        distances = result["distances"][0] if result.get("distances") else [float("nan")] * len(ids)
        return [
            Hit(chunk=self.chunks[chunk_id], distance=float(distance))
            for chunk_id, distance in zip(ids, distances, strict=True)
        ]
