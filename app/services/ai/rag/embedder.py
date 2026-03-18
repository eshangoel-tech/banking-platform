"""
Embedding engine — uses ChromaDB's built-in ONNX embedding function.

Same model (all-MiniLM-L6-v2) as before but via onnxruntime instead of PyTorch.
This avoids the 2GB torch dependency, keeping the Docker image under 2GB.
"""
from __future__ import annotations

import logging

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

logger = logging.getLogger(__name__)

_ef: DefaultEmbeddingFunction | None = None


def _get_ef() -> DefaultEmbeddingFunction:
    global _ef
    if _ef is None:
        logger.info("Loading ONNX embedding function (all-MiniLM-L6-v2)...")
        _ef = DefaultEmbeddingFunction()
        logger.info("Embedding function ready.")
    return _ef


def embed_texts(texts: list[str]) -> list[list[float]]:
    return list(_get_ef()(texts))


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def get_embedding_function() -> DefaultEmbeddingFunction:
    """Return the singleton embedding function for use with ChromaDB collections."""
    return _get_ef()
