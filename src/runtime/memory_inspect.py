"""Inspect the current state of mutable memory.

Prints a human-readable summary: query cache size, most-accessed concepts,
count of learned aliases, etc. Useful for debugging and for the user to
audit what the runtime has learned.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from runtime.memory import (
    MemoryPaths,
    load_learned_aliases,
    load_path_frequency,
    load_query_cache,
    load_user_preferences,
)


def inspect_memory(memory_dir: Path) -> dict[str, Any]:
    """Build a structured summary of the memory state."""
    paths = MemoryPaths(memory_dir=memory_dir)

    cache = load_query_cache(paths.query_cache)
    freq = load_path_frequency(paths.path_frequency)
    aliases = load_learned_aliases(paths.learned_aliases)
    prefs = load_user_preferences(paths.user_preferences)

    most_used = sorted(
        ((name, info.get("total_accesses", 0)) for name, info in freq.items()),
        key=lambda x: x[1],
        reverse=True,
    )
    most_used = [list(pair) for pair in most_used[:10]]

    return {
        "query_cache_size": len(cache),
        "most_used_concepts": most_used,
        "learned_aliases_count": len(aliases),
        "user_preferences": prefs,
    }


def _format_human(report: dict[str, Any]) -> str:
    lines = [
        f"query_cache_size: {report['query_cache_size']}",
        f"learned_aliases_count: {report['learned_aliases_count']}",
        "most_used_concepts:",
    ]
    if not report["most_used_concepts"]:
        lines.append("  (none)")
    else:
        for name, count in report["most_used_concepts"]:
            lines.append(f"  {count:>4}  {name}")
    lines.append("user_preferences:")
    for k, v in report["user_preferences"].items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect runtime memory state.")
    parser.add_argument("--memory-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    report = inspect_memory(args.memory_dir)
    print(_format_human(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
