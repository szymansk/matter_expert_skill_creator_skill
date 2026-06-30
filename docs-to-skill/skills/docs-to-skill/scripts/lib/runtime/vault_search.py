"""Layer 2 retrieval: tokenized, IDF-ranked keyword search (stdlib only).

The query is tokenized, light-stemmed, and synonym-expanded; each distinct
query token is substring-matched against a concept's strong fields
(title + aliases + tags) and weak fields (summary + body, frontmatter stripped).
Concepts are ranked by the sum of IDF(token) * field-weight, with a boost when
the whole normalized query appears verbatim. Pure Python — produced skills need
no system binaries.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if _HERE.name == "runtime":
    _scripts = _HERE.parent
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))

from runtime.index import load_concept_index
from runtime.text import (
    build_synonym_index, expand_token, load_synonym_groups, tokenize,
)

_STRONG_WEIGHT = 3.0   # title + aliases + tags
_WEAK_WEIGHT = 1.0     # summary + body
_PHRASE_BOOST = 5.0    # whole normalized query appears verbatim

# Word-run regex (mirrors runtime.text) used to build the phrase-boost key so
# punctuation in a natural-language question (",", "?") does not prevent the
# normalized query from ever matching a body.
_WORD_RE = re.compile(r"[a-z0-9äöüß]+")


def _strip_frontmatter(text: str) -> str:
    """Return only the body of a Markdown file (content after frontmatter).

    If the file starts with ``---``, the frontmatter block extends up to the
    next ``---`` line. Everything after that closing delimiter is returned.
    If no frontmatter is present the full text is returned unchanged.
    """
    if not text.startswith("---"):
        return text
    # Find the closing delimiter — must be on its own line after the opening.
    rest = text[3:]  # skip opening "---"
    close = rest.find("\n---")
    if close == -1:
        return text  # malformed — treat whole file as body
    # Return everything after the closing "---\n", stripping any leading newline.
    return rest[close + 4:].lstrip("\n")


def _matches_any(text: str, variants: set[str]) -> bool:
    return any(v and v in text for v in variants)


def search_vault(
    query: str,
    vault_dir: Path,
    concept_index_path: Path,
    tags: list[str] | None = None,
    synonyms_path: Path | None = None,
    limit: int | None = None,
) -> list[str]:
    """Return concept names ranked by relevance to `query` (best first).

    `tags`, if given, restricts results to concepts carrying one of those tags.
    `synonyms_path` (optional) enables synonym expansion. `limit` caps results.
    """
    index = load_concept_index(concept_index_path)
    concepts_dir = vault_dir / "concepts"

    bodies: dict[str, str] = {}
    if concepts_dir.exists():
        for md_file in concepts_dir.glob("*.md"):
            bodies[md_file.stem] = _strip_frontmatter(
                md_file.read_text(encoding="utf-8")
            ).lower()

    names = set(bodies) | set(index)
    strong_text: dict[str, str] = {}
    weak_text: dict[str, str] = {}
    combined: dict[str, str] = {}
    for name in names:
        entry = index.get(name, {})
        # `or ""` / `or []` coerce an explicit JSON null (e.g. a concept page
        # with a bare `title:`) to a safe empty value — `.get(k, default)` would
        # return None when the key is present with a null value, crashing join.
        strong_parts = [entry.get("title") or ""]
        strong_parts += list(entry.get("aliases") or [])
        strong_parts += list(entry.get("tags") or [])
        strong_text[name] = " ".join(strong_parts).lower()
        weak_text[name] = ((entry.get("summary") or "").lower()
                           + " " + bodies.get(name, ""))
        combined[name] = strong_text[name] + " " + weak_text[name]

    syn_index = build_synonym_index(load_synonym_groups(synonyms_path))
    q_tokens = tokenize(query)
    token_variants = {t: expand_token(t, syn_index) for t in q_tokens}

    n_docs = max(len(names), 1)
    doc_freq: dict[str, int] = {
        t: sum(1 for name in names if _matches_any(combined[name], variants))
        for t, variants in token_variants.items()
    }

    def idf(token: str) -> float:
        return math.log(1 + n_docs / (1 + doc_freq.get(token, 0)))

    norm_query = " ".join(_WORD_RE.findall(query.lower()))

    scores: dict[str, float] = {}
    for name in names:
        score = 0.0
        for token, variants in token_variants.items():
            if _matches_any(strong_text[name], variants):
                score += idf(token) * _STRONG_WEIGHT
            elif _matches_any(weak_text[name], variants):
                score += idf(token) * _WEAK_WEIGHT
        if score and norm_query and norm_query in combined[name]:
            score += _PHRASE_BOOST
        if score > 0:
            scores[name] = score

    ranked = sorted(scores, key=lambda name: (-scores[name], name))

    if tags:
        wanted = set(tags)
        ranked = [
            name for name in ranked
            if name in index and wanted.intersection(index[name].get("tags", []))
        ]

    if limit is not None:
        ranked = ranked[:limit]
    return ranked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search the vault body content.")
    parser.add_argument("--vault", type=Path, required=True, help="Vault root directory")
    parser.add_argument("--concept-index", type=Path, required=True,
                        help="Path to concept_index.json")
    parser.add_argument("--query", required=True,
                        help="The user's question or keywords")
    parser.add_argument("--tags", default="",
                        help="Comma-separated list of tags to filter by")
    parser.add_argument("--synonyms", type=Path, default=None,
                        help="Optional path to synonyms.json")
    parser.add_argument("--limit", type=int, default=20,
                        help="Maximum number of ranked results")
    args = parser.parse_args(argv)

    tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    matches = search_vault(
        query=args.query,
        vault_dir=args.vault,
        concept_index_path=args.concept_index,
        tags=tag_list or None,
        synonyms_path=args.synonyms,
        limit=args.limit,
    )
    json.dump(matches, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
