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
    field_total: dict[str, int] = dict.fromkeys(FIELDS, 0)

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


@dataclass
class BM25Index:
    """In-memory BM25F index loaded from ``bm25_index.json``."""

    n: int
    fields: tuple[str, ...]
    avg_field_len: dict[str, float]
    doc_field_len: dict[str, dict[str, int]]
    postings: dict[str, dict[str, dict[str, int]]]

    @classmethod
    def from_dict(cls, data: dict) -> "BM25Index":
        return cls(
            n=data["N"],
            fields=tuple(data["fields"]),
            avg_field_len=data["avg_field_len"],
            doc_field_len=data["doc_field_len"],
            postings=data["postings"],
        )

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def score(self, query: str, top_n: int | None = None) -> list[tuple[str, float]]:
        """Return ``(concept_name, score)`` pairs ranked by BM25F, best first.

        Ties are broken alphabetically by concept name for determinism.
        """
        scores: dict[str, float] = {}
        for term in set(tokenize(query)):
            plist = self.postings.get(term)
            if not plist:
                continue
            df = len(plist)
            idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
            for name, field_counts in plist.items():
                tf_prime = 0.0
                for field, cnt in field_counts.items():
                    avg = self.avg_field_len.get(field) or 1.0
                    length = self.doc_field_len[name].get(field, 0)
                    denom = 1.0 - FIELD_B[field] + FIELD_B[field] * (length / avg)
                    tf_prime += FIELD_BOOSTS[field] * cnt / denom
                scores[name] = scores.get(name, 0.0) + idf * tf_prime / (K1 + tf_prime)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:top_n] if top_n is not None else ranked


def assemble_docs(vault_dir: Path, concept_index_path: Path) -> list[dict]:
    """Build BM25 field documents from a vault and its concept index.

    Bodies come from ``<vault_dir>/concepts/*.md`` (frontmatter stripped);
    title/tags/aliases come from ``concept_index.json``.
    """
    vault_dir = Path(vault_dir)
    concept_index_path = Path(concept_index_path)
    index = json.loads(concept_index_path.read_text(encoding="utf-8"))
    concepts_dir = vault_dir / "concepts"
    if not concepts_dir.is_dir():
        return []
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
