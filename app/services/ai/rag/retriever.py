"""
Retriever — semantic search over ChromaDB collections.

Usage:
    from app.services.ai.rag.retriever import retrieve_bank_rules, retrieve_bank_policies

    chunks = retrieve_bank_rules("What is the maximum loan amount?", top_k=3)
    # Returns list of plain text strings, highest relevance first.
"""
from __future__ import annotations

import logging

from app.services.ai.rag.embedder import embed_query
from app.services.ai.rag.vector_store import get_collection

logger = logging.getLogger(__name__)


def _retrieve(collection_name: str, query: str, top_k: int = 3) -> list[str]:
    """
    Embed `query`, query the given collection, and return the top-k document texts.

    Returns an empty list if the collection has no documents or the query fails.
    """
    try:
        collection = get_collection(collection_name)
        query_embedding = embed_query(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        chunks: list[str] = []
        for doc, meta, dist in zip(docs, metadatas, distances):
            source = meta.get("source", "unknown")
            section = meta.get("section", "")
            similarity = round(1 - dist, 4)  # cosine distance → similarity
            chunks.append(
                f"[source: {source} | section: {section} | similarity: {similarity}]\n{doc}"
            )

        logger.debug(
            "Retrieved %d chunks from '%s' for query: %.60s…",
            len(chunks),
            collection_name,
            query,
        )
        return chunks

    except Exception:
        logger.exception("Retrieval failed for collection '%s'", collection_name)
        return []


def retrieve_bank_rules(query: str, top_k: int = 3) -> list[str]:
    """Return top-k bank rules chunks most relevant to the query."""
    return _retrieve("bank_rules", query, top_k=top_k)


def retrieve_bank_policies(query: str, top_k: int = 3) -> list[str]:
    """Return top-k bank policy chunks most relevant to the query."""
    return _retrieve("bank_policies", query, top_k=top_k)
