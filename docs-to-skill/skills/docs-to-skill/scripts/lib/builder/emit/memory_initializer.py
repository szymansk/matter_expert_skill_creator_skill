"""Write the initial mutable memory files for a freshly generated expert skill."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Default preferences mirror runtime.memory.DEFAULT_USER_PREFERENCES.
DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    "response_language": "auto",
    "preferred_depth": "balanced",
    "technical_terms": "keep_english",
    "always_show_sources": True,
}


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def _synthesize_path_frequency(link_graph: dict[str, dict]) -> dict[str, dict]:
    """Seed path_frequency from the typed-link graph: linked concepts get
    an initial co_accessed count of 1 (in both directions for symmetric links).
    """
    freq: dict[str, dict] = {}

    def ensure(name: str) -> None:
        if name not in freq:
            freq[name] = {"co_accessed": {}, "total_accesses": 0}

    for name, entry in link_graph.items():
        ensure(name)
        for link_type in ("related", "prerequisites", "examples",
                          "contrasts", "refines"):
            for neighbor in entry.get(link_type, []):
                ensure(neighbor)
                # Use max(existing, 1) so that if the link already exists
                # from the reverse direction we don't double-count.
                freq[name]["co_accessed"][neighbor] = max(
                    freq[name]["co_accessed"].get(neighbor, 0), 1
                )
                # Symmetric seeding so memory_update finds co-accesses immediately.
                freq[neighbor]["co_accessed"][name] = max(
                    freq[neighbor]["co_accessed"].get(name, 0), 1
                )
    return freq


def initialize_memory(memory_dir: Path,
                      link_graph: dict[str, dict] | None = None) -> None:
    """Write the 5 initial memory files."""
    _save_json(memory_dir / "query_cache.json", {})
    _save_json(
        memory_dir / "path_frequency.json",
        _synthesize_path_frequency(link_graph or {}),
    )
    _save_json(memory_dir / "user_preferences.json",
               dict(DEFAULT_USER_PREFERENCES))
    _save_json(memory_dir / "learned_aliases.json", {})
    _save_json(memory_dir / "session_log.json", [])
