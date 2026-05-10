import subprocess
import sys
from pathlib import Path

from runtime.memory import (
    load_path_frequency,
    load_query_cache,
    save_query_cache,
)
from runtime.memory_update import QUERY_CACHE_MAX_ENTRIES, update_memory


def test_update_records_query_cache(memory_dir: Path):
    update_memory(
        memory_dir=memory_dir,
        query="how does OAuth work",
        used_concepts=["oauth2-flow", "jwt-tokens"],
    )
    cache = load_query_cache(memory_dir / "query_cache.json")
    assert "how does OAuth work" in cache
    entry = cache["how does OAuth work"]
    assert entry["matched_concepts"] == ["oauth2-flow", "jwt-tokens"]
    assert entry["use_count"] == 1
    assert "last_used" in entry


def test_update_increments_use_count_on_repeat_query(memory_dir: Path):
    update_memory(memory_dir=memory_dir, query="oauth", used_concepts=["oauth2-flow"])
    update_memory(memory_dir=memory_dir, query="oauth", used_concepts=["oauth2-flow"])
    cache = load_query_cache(memory_dir / "query_cache.json")
    assert cache["oauth"]["use_count"] == 2


def test_update_records_co_access_in_path_frequency(memory_dir: Path):
    update_memory(
        memory_dir=memory_dir,
        query="auth question",
        used_concepts=["oauth2-flow", "jwt-tokens", "session-management"],
    )
    freq = load_path_frequency(memory_dir / "path_frequency.json")

    assert freq["oauth2-flow"]["total_accesses"] == 1
    assert freq["oauth2-flow"]["co_accessed"]["jwt-tokens"] == 1
    assert freq["oauth2-flow"]["co_accessed"]["session-management"] == 1
    assert freq["jwt-tokens"]["co_accessed"]["oauth2-flow"] == 1


def test_update_lru_evicts_oldest_when_cache_full(memory_dir: Path):
    cache = {
        f"q{i}": {
            "matched_concepts": [],
            "last_used": f"2026-05-{i+1:02d}T00:00:00Z",
            "use_count": 1,
            "user_satisfied": True,
        }
        for i in range(QUERY_CACHE_MAX_ENTRIES)
    }
    save_query_cache(memory_dir / "query_cache.json", cache)

    update_memory(memory_dir=memory_dir, query="newest", used_concepts=["x"])

    after = load_query_cache(memory_dir / "query_cache.json")
    assert len(after) == QUERY_CACHE_MAX_ENTRIES
    assert "newest" in after
    assert "q0" not in after  # oldest evicted


def test_update_with_user_language_records_preference(memory_dir: Path):
    update_memory(
        memory_dir=memory_dir,
        query="oauth Frage",
        used_concepts=["oauth2-flow"],
        user_language="de",
    )
    from runtime.memory import load_user_preferences
    prefs = load_user_preferences(memory_dir / "user_preferences.json")
    assert prefs["response_language"] == "de"


def test_cli_runs(memory_dir: Path):
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.memory_update",
            "--memory-dir", str(memory_dir),
            "--query", "test",
            "--used-concepts", "oauth2-flow,jwt-tokens",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    cache = load_query_cache(memory_dir / "query_cache.json")
    assert "test" in cache
