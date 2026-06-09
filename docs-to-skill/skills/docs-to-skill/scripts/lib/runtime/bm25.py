"""Pure-Python BM25F core: tokenizer, index builder, and scorer.

Shared by the Builder's Emit phase (which writes ``_index/bm25_index.json``)
and the runtime query path (``runtime/vault_search.py``). Stdlib only — this
module is bundled into produced skills and must never import third-party code.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

# --- Field-weighting configuration (single source of truth) --------------
FIELDS: tuple[str, ...] = ("title", "aliases", "tags", "body")
FIELD_BOOSTS: dict[str, float] = {"title": 3.0, "aliases": 2.5, "tags": 2.0, "body": 1.0}
FIELD_B: dict[str, float] = {"title": 0.5, "aliases": 0.5, "tags": 0.5, "body": 0.75}
K1: float = 1.2

# Word characters except underscore: keeps letters and digits, splits the rest.
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lowercase and split text into alphanumeric tokens (digits kept)."""
    return _TOKEN_RE.findall(text.lower())
