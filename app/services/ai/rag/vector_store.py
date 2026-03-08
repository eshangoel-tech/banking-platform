"""
ChromaDB vector store — manages two collections: bank_rules and bank_policies.

On startup the application calls `initialize_vector_store()` which:
  1. Connects to (or creates) a persistent ChromaDB instance.
  2. Deletes and re-creates both collections (fresh embeddings every restart).
  3. Ingests and embeds all documents from the config directories.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb
from chromadb import Collection

from app.services.ai.rag.embedder import embed_texts
from app.services.ai.rag.ingester import (
    Document,
    load_bank_policies_documents,
    load_bank_rules_documents,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Persistent storage path (project root / chroma_data)
_CHROMA_PATH = str(Path(__file__).parents[5] / "chroma_data")

_COLLECTION_BANK_RULES = "bank_rules"
_COLLECTION_BANK_POLICIES = "bank_policies"

_client: chromadb.PersistentClient | None = None
_collections: dict[str, Collection] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        logger.info("Connecting to ChromaDB at %s", _CHROMA_PATH)
        _client = chromadb.PersistentClient(path=_CHROMA_PATH)
    return _client


def _ingest_documents(collection: Collection, docs: list[Document]) -> None:
    """Embed and upsert documents into a ChromaDB collection."""
    if not docs:
        logger.warning("No documents to ingest into collection '%s'", collection.name)
        return

    texts = [d.text for d in docs]
    ids = [d.doc_id for d in docs]
    metadatas = [{"source": d.source, "section": d.section} for d in docs]

    logger.info("Embedding %d chunks for collection '%s'...", len(docs), collection.name)
    embeddings = embed_texts(texts)

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    logger.info(
        "Ingested %d documents into collection '%s'.", len(docs), collection.name
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def initialize_vector_store() -> None:
    """
    Called once at server startup.

    Drops and recreates both collections, then ingests fresh embeddings
    from the config JSON files. Blocks until ingestion is complete.
    """
    client = _get_client()

    for name, loader in [
        (_COLLECTION_BANK_RULES, load_bank_rules_documents),
        (_COLLECTION_BANK_POLICIES, load_bank_policies_documents),
    ]:
        # Delete if exists → recreate (ensures fresh embeddings every restart)
        try:
            client.delete_collection(name)
            logger.info("Dropped existing collection '%s'.", name)
        except Exception:
            pass  # Collection didn't exist yet

        collection = client.create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        _collections[name] = collection
        _ingest_documents(collection, loader())

    logger.info("Vector store ready: %s", list(_collections.keys()))


def get_collection(name: str) -> Collection:
    """Return a loaded collection by name. Raises if not initialised."""
    if name not in _collections:
        # Lazy reconnect (e.g. tests that skip startup)
        client = _get_client()
        _collections[name] = client.get_collection(name)
    return _collections[name]
