import subprocess
import sys
from pathlib import Path

from runtime.memory import (
    save_learned_aliases,
    save_path_frequency,
    save_query_cache,
)
from runtime.memory_inspect import inspect_memory


def test_inspect_empty_memory_dir(memory_dir: Path):
    report = inspect_memory(memory_dir)
    assert report["query_cache_size"] == 0
    assert report["most_used_concepts"] == []
    assert report["learned_aliases_count"] == 0


def test_inspect_reports_query_cache_size(memory_dir: Path):
    save_query_cache(
        memory_dir / "query_cache.json",
        {
            "q1": {"matched_concepts": ["a"], "last_used": "2026-05-10T00:00:00Z",
                   "use_count": 1, "user_satisfied": True},
            "q2": {"matched_concepts": ["b"], "last_used": "2026-05-10T00:00:00Z",
                   "use_count": 1, "user_satisfied": True},
        },
    )
    report = inspect_memory(memory_dir)
    assert report["query_cache_size"] == 2


def test_inspect_reports_top_used_concepts(memory_dir: Path):
    save_path_frequency(
        memory_dir / "path_frequency.json",
        {
            "oauth2-flow": {"co_accessed": {}, "total_accesses": 12},
            "jwt-tokens": {"co_accessed": {}, "total_accesses": 8},
            "session-management": {"co_accessed": {}, "total_accesses": 3},
        },
    )
    report = inspect_memory(memory_dir)
    assert report["most_used_concepts"][0] == ["oauth2-flow", 12]
    assert report["most_used_concepts"][1] == ["jwt-tokens", 8]
    assert report["most_used_concepts"][2] == ["session-management", 3]


def test_inspect_counts_learned_aliases(memory_dir: Path):
    save_learned_aliases(
        memory_dir / "learned_aliases.json",
        {"a1": "c1", "a2": "c2", "a3": "c3"},
    )
    report = inspect_memory(memory_dir)
    assert report["learned_aliases_count"] == 3


def test_cli_outputs_human_readable(memory_dir: Path):
    save_query_cache(
        memory_dir / "query_cache.json",
        {"q1": {"matched_concepts": [], "last_used": "2026-05-10T00:00:00Z",
                "use_count": 1, "user_satisfied": True}},
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.memory_inspect",
            "--memory-dir", str(memory_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "query_cache_size" in result.stdout.lower() or "cache" in result.stdout.lower()
    assert "1" in result.stdout
