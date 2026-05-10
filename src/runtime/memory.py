"""Mutable memory for the runtime expert skill.

Five JSON files persisted under ~/.claude/projects/<id>/memory/<expert>/:

- query_cache.json     : recent queries → matched concepts (TTL/LRU)
- path_frequency.json  : co-access counter per concept
- user_preferences.json: language, depth, term-handling, etc.
- learned_aliases.json : alias → canonical concept name (additive)
- session_log.json     : list of brainstorming sessions w/ hypotheses

All read functions return a sensible default when the file is missing,
so first-run code never has to special-case a fresh memory directory.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    "response_language": "auto",       # "auto" | "en" | "de" | ...
    "preferred_depth": "balanced",     # "concise" | "balanced" | "detailed"
    "technical_terms": "keep_english", # "keep_english" | "translate"
    "always_show_sources": True,
}


@dataclass(frozen=True)
class MemoryPaths:
    """Resolves the 5 mutable memory file paths."""

    memory_dir: Path

    @property
    def query_cache(self) -> Path:
        return self.memory_dir / "query_cache.json"

    @property
    def path_frequency(self) -> Path:
        return self.memory_dir / "path_frequency.json"

    @property
    def user_preferences(self) -> Path:
        return self.memory_dir / "user_preferences.json"

    @property
    def learned_aliases(self) -> Path:
        return self.memory_dir / "learned_aliases.json"

    @property
    def session_log(self) -> Path:
        return self.memory_dir / "session_log.json"


def _load_json_or_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def load_query_cache(path: Path) -> dict[str, dict[str, Any]]:
    return _load_json_or_default(path, {})


def save_query_cache(path: Path, data: dict[str, dict[str, Any]]) -> None:
    _save_json(path, data)


def load_path_frequency(path: Path) -> dict[str, dict[str, Any]]:
    return _load_json_or_default(path, {})


def save_path_frequency(path: Path, data: dict[str, dict[str, Any]]) -> None:
    _save_json(path, data)


def load_user_preferences(path: Path) -> dict[str, Any]:
    return _load_json_or_default(path, dict(DEFAULT_USER_PREFERENCES))


def save_user_preferences(path: Path, data: dict[str, Any]) -> None:
    _save_json(path, data)


def load_learned_aliases(path: Path) -> dict[str, str]:
    return _load_json_or_default(path, {})


def save_learned_aliases(path: Path, data: dict[str, str]) -> None:
    _save_json(path, data)


def load_session_log(path: Path) -> list[dict[str, Any]]:
    return _load_json_or_default(path, [])


def save_session_log(path: Path, data: list[dict[str, Any]]) -> None:
    _save_json(path, data)
