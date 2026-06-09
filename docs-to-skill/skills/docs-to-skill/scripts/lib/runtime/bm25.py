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


def strip_frontmatter(text: str) -> str:
    """Return only the Markdown body (content after a leading ``---`` block).

    The frontmatter block is the text between a leading line ``---`` and the
    next line that is exactly ``---``. If the file does not start with a
    ``---`` line, or the block is unterminated, the text is returned unchanged.
    """
    if not text.startswith("---\n"):
        return text
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i] == "---":
            return "\n".join(lines[i + 1:]).lstrip("\n")
    return text  # unterminated — treat whole file as body


def build_bm25_index(docs: list[dict]) -> dict:
    """Build a serializable BM25F index from per-concept field documents.

    ``docs`` is a list of dicts with keys ``name``, ``title``, ``aliases``
    (list[str]), ``tags`` (list[str]), and ``body`` (str). Returns a JSON-
    serializable index dict (see module docstring / plan for the shape).
    """
    postings: dict[str, dict[str, dict[str, int]]] = {}
    doc_field_len: dict[str, dict[str, int]] = {}
    field_total: dict[str, int] = {f: 0 for f in FIELDS}

    for doc in docs:
        name = doc["name"]
        field_tokens = {
            "title": tokenize(doc.get("title", "") or ""),
            "aliases": tokenize(" ".join(doc.get("aliases") or [])),
            "tags": tokenize(" ".join(doc.get("tags") or [])),
            "body": tokenize(doc.get("body", "") or ""),
        }
        doc_field_len[name] = {f: len(field_tokens[f]) for f in FIELDS}
        for f in FIELDS:
            field_total[f] += len(field_tokens[f])
            counts: dict[str, int] = {}
            for tok in field_tokens[f]:
                counts[tok] = counts.get(tok, 0) + 1
            for tok, cnt in counts.items():
                postings.setdefault(tok, {}).setdefault(name, {})[f] = cnt

    n = len(docs)
    avg_field_len = {f: (field_total[f] / n if n else 0.0) for f in FIELDS}
    return {
        "N": n,
        "fields": list(FIELDS),
        "avg_field_len": avg_field_len,
        "doc_field_len": doc_field_len,
        "postings": postings,
    }


def assemble_docs(vault_dir: Path, concept_index_path: Path) -> list[dict]:
    """Build BM25 field documents from a vault and its concept index.

    Bodies come from ``<vault_dir>/concepts/*.md`` (frontmatter stripped);
    title/tags/aliases come from ``concept_index.json``.
    """
    vault_dir = Path(vault_dir)
    concept_index_path = Path(concept_index_path)
    index = json.loads(concept_index_path.read_text(encoding="utf-8"))
    concepts_dir = vault_dir / "concepts"
    docs: list[dict] = []
    for md_file in sorted(concepts_dir.glob("*.md")):
        name = md_file.stem
        entry = index.get(name, {})
        docs.append({
            "name": name,
            "title": entry.get("title", ""),
            "aliases": list(entry.get("aliases", [])),
            "tags": list(entry.get("tags", [])),
            "body": strip_frontmatter(md_file.read_text(encoding="utf-8")),
        })
    return docs
