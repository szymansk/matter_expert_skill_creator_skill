import json
import subprocess
import sys
from pathlib import Path

from runtime.memory import save_learned_aliases, save_query_cache
from runtime.vault_locate import locate_entry_points


def test_locate_returns_empty_for_unknown_query(built_indexes, memory_dir: Path):
    result = locate_entry_points(
        query="completely unrelated query",
        index_dir=built_indexes.index_dir,
        memory_dir=memory_dir,
    )
    assert result["matches"] == []
    assert result["strategy"] == "none"


def test_locate_resolves_via_alias_map(built_indexes, memory_dir: Path):
    """If the alias_map maps a token in the query to a concept, return it."""
    custom_alias_map = built_indexes.index_dir / "alias_map.json"
    custom_alias_map.write_text(
        json.dumps({"OAuth": "oauth2-flow"}, indent=2),
        encoding="utf-8",
    )

    result = locate_entry_points(
        query="how does OAuth work",
        index_dir=built_indexes.index_dir,
        memory_dir=memory_dir,
    )
    assert "oauth2-flow" in result["matches"]
    assert result["strategy"] == "alias_match"


def test_locate_resolves_via_learned_aliases(built_indexes, memory_dir: Path):
    save_learned_aliases(
        memory_dir / "learned_aliases.json",
        {"unser Auth-System": "oauth2-flow"},
    )

    result = locate_entry_points(
        query="erkläre unser Auth-System",
        index_dir=built_indexes.index_dir,
        memory_dir=memory_dir,
    )
    assert "oauth2-flow" in result["matches"]
    assert result["strategy"] == "learned_alias"


def test_locate_resolves_via_moc_name(built_indexes, memory_dir: Path):
    """A query containing a MOC name should return the MOC's children."""
    result = locate_entry_points(
        query="tell me about authentication",
        index_dir=built_indexes.index_dir,
        memory_dir=memory_dir,
    )
    assert "oauth2-flow" in result["matches"]
    assert result["strategy"] == "moc_match"


def test_locate_returns_cache_hit(built_indexes, memory_dir: Path):
    save_query_cache(
        memory_dir / "query_cache.json",
        {
            "wie funktioniert oauth": {
                "matched_concepts": ["oauth2-flow", "jwt-tokens"],
                "last_used": "2026-05-10T14:32:00Z",
                "use_count": 3,
                "user_satisfied": True,
            },
        },
    )

    result = locate_entry_points(
        query="wie funktioniert oauth",
        index_dir=built_indexes.index_dir,
        memory_dir=memory_dir,
    )
    assert result["matches"] == ["oauth2-flow", "jwt-tokens"]
    assert result["strategy"] == "query_cache"


def test_locate_query_cache_is_normalized(built_indexes, memory_dir: Path):
    """Query cache lookup is case-insensitive and whitespace-trimmed."""
    save_query_cache(
        memory_dir / "query_cache.json",
        {
            "wie funktioniert oauth": {
                "matched_concepts": ["oauth2-flow"],
                "last_used": "2026-05-10T14:32:00Z",
                "use_count": 1,
                "user_satisfied": True,
            },
        },
    )

    result = locate_entry_points(
        query="  Wie funktioniert OAuth  ",
        index_dir=built_indexes.index_dir,
        memory_dir=memory_dir,
    )
    assert result["matches"] == ["oauth2-flow"]
    assert result["strategy"] == "query_cache"


def test_cli_outputs_json(built_indexes, memory_dir: Path):
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_locate",
            "--index-dir", str(built_indexes.index_dir),
            "--memory-dir", str(memory_dir),
            "tell me about authentication",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert "matches" in parsed
    assert "strategy" in parsed
