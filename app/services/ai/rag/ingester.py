"""
Data ingester — reads bank_rules and bank_policies JSON files,
parses them into flat text chunks with metadata for embedding.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parents[4] / "config"
_BANK_RULES_DIR = _CONFIG_DIR / "bank_rules"
_BANK_POLICIES_DIR = _CONFIG_DIR / "bank_policies"


@dataclass
class Document:
    """A single embeddable text chunk with provenance metadata."""

    text: str
    doc_id: str          # unique id for chromadb
    collection: str      # "bank_rules" | "bank_policies"
    source: str          # filename (e.g. "loan_policy.json")
    section: str         # top-level JSON key (e.g. "eligibility")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _flatten_value(value: Any) -> str:
    """Recursively flatten a JSON value to a human-readable string."""
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            parts.append(f"{k.replace('_', ' ')}: {_flatten_value(v)}")
        return ". ".join(parts)
    if isinstance(value, list):
        return ", ".join(_flatten_value(item) for item in value)
    return str(value)


def _parse_json_file(path: Path, collection: str) -> list[Document]:
    """
    Parse a single JSON file into a list of Documents — one per top-level key.

    Keys starting with '_' (e.g. '_comment', '_source') are treated as metadata
    and prepended to every chunk from that file rather than being their own chunk.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to parse %s", path)
        return []

    source = path.name
    # Pull out meta keys
    meta_parts: list[str] = []
    for k, v in raw.items():
        if k.startswith("_"):
            meta_parts.append(_flatten_value(v))

    meta_prefix = f"{'. '.join(meta_parts)}. " if meta_parts else ""

    docs: list[Document] = []
    for idx, (section, content) in enumerate(raw.items()):
        if section.startswith("_"):
            continue

        body = _flatten_value(content)
        text = f"{meta_prefix}Section — {section.replace('_', ' ')}: {body}"

        docs.append(
            Document(
                text=text,
                doc_id=f"{collection}::{source}::{section}::{idx}",
                collection=collection,
                source=source,
                section=section,
            )
        )

    return docs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_bank_rules_documents() -> list[Document]:
    """Return all text chunks from the bank_rules directory."""
    docs: list[Document] = []
    for json_file in sorted(_BANK_RULES_DIR.glob("*.json")):
        chunks = _parse_json_file(json_file, collection="bank_rules")
        docs.extend(chunks)
        logger.debug("Ingested %d chunks from %s", len(chunks), json_file.name)
    logger.info("Bank rules: %d total chunks", len(docs))
    return docs


def load_bank_policies_documents() -> list[Document]:
    """Return all text chunks from the bank_policies directory."""
    docs: list[Document] = []
    for json_file in sorted(_BANK_POLICIES_DIR.glob("*.json")):
        chunks = _parse_json_file(json_file, collection="bank_policies")
        docs.extend(chunks)
        logger.debug("Ingested %d chunks from %s", len(chunks), json_file.name)
    logger.info("Bank policies: %d total chunks", len(docs))
    return docs
