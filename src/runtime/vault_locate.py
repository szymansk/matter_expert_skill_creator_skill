"""Layer 1 entry-point identification.

Resolution strategy (first hit wins):
1. query_cache — exact match (normalized) → cached concepts
2. learned_aliases — substring of query → concept
3. alias_map — substring of query → concept
4. moc_map — MOC name appears in query → MOC's children
5. otherwise — no match
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# When this script is executed directly from a bundled plugin the runtime/
# directory sits inside scripts/.  Add scripts/ to sys.path so that
# `from runtime.xxx import` resolves regardless of the working directory.
_HERE = Path(__file__).resolve().parent
if _HERE.name == "runtime":
    _scripts = _HERE.parent
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))

from runtime.index import IndexPaths, load_alias_map, load_moc_map
from runtime.memory import (
    MemoryPaths,
    load_learned_aliases,
    load_query_cache,
)


def _normalize(s: str) -> str:
    return " ".join(s.lower().split())


def locate_entry_points(
    query: str,
    index_dir: Path,
    memory_dir: Path,
) -> dict[str, Any]:
    """Find candidate entry-point concepts for a query.

    Returns a dict with:
        matches: list[str]   — candidate concept names
        strategy: str        — which lookup hit:
            "query_cache" | "learned_alias" | "alias_match" | "moc_match" | "none"
    """
    index_paths = IndexPaths(index_dir=index_dir)
    memory_paths = MemoryPaths(memory_dir=memory_dir)

    normalized = _normalize(query)

    # Strategy 1: exact match in query_cache.
    cache = load_query_cache(memory_paths.query_cache)
    for cached_query, info in cache.items():
        if _normalize(cached_query) == normalized:
            return {
                "matches": list(info.get("matched_concepts", [])),
                "strategy": "query_cache",
            }

    # Strategy 2: substring match against learned_aliases (user-coined terms).
    learned = load_learned_aliases(memory_paths.learned_aliases)
    normalized_query = _normalize(query)
    for alias, concept in learned.items():
        if _normalize(alias) in normalized_query:
            return {"matches": [concept], "strategy": "learned_alias"}

    # Strategy 3: substring match against the static alias_map.
    aliases = load_alias_map(index_paths.alias_map)
    for alias, concept in aliases.items():
        if _normalize(alias) in normalized_query:
            return {"matches": [concept], "strategy": "alias_match"}

    # Strategy 4: MOC name appears in query.
    mocs = load_moc_map(index_paths.moc_map)
    for moc_name, entry in mocs.items():
        if _normalize(moc_name) in normalized_query:
            return {
                "matches": list(entry.get("children", [])),
                "strategy": "moc_match",
            }

    return {"matches": [], "strategy": "none"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Identify entry-point concepts for a query."
    )
    parser.add_argument("--index-dir", type=Path, required=True,
                        help="Path to the _index directory")
    parser.add_argument("--memory-dir", type=Path, required=True,
                        help="Path to the runtime memory directory")
    parser.add_argument("query", help="The user's query string")
    args = parser.parse_args(argv)

    result = locate_entry_points(
        query=args.query,
        index_dir=args.index_dir,
        memory_dir=args.memory_dir,
    )
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
