"""
Embedding engine — singleton wrapper around sentence-transformers/all-MiniLM-L6-v2.

The model is loaded once on first use (lazy) to avoid slowing down import time.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model: "SentenceTransformer | None" = None


def get_model() -> "SentenceTransformer":
    """Return the singleton embedding model, loading it on first call."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", _MODEL_NAME)
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("Embedding model loaded.")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Encode a list of strings and return their embedding vectors."""
    model = get_model()
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """Encode a single query string."""
    return embed_texts([text])[0]
