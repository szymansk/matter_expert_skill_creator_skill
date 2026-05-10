from pathlib import Path

from runtime.memory import (
    MemoryPaths,
    load_query_cache,
    save_query_cache,
    load_path_frequency,
    save_path_frequency,
    load_user_preferences,
    save_user_preferences,
    load_learned_aliases,
    save_learned_aliases,
    load_session_log,
    save_session_log,
    DEFAULT_USER_PREFERENCES,
)


def test_memory_paths_resolution():
    paths = MemoryPaths(memory_dir=Path("/tmp/mem"))
    assert paths.query_cache == Path("/tmp/mem/query_cache.json")
    assert paths.path_frequency == Path("/tmp/mem/path_frequency.json")
    assert paths.user_preferences == Path("/tmp/mem/user_preferences.json")
    assert paths.learned_aliases == Path("/tmp/mem/learned_aliases.json")
    assert paths.session_log == Path("/tmp/mem/session_log.json")


def test_load_query_cache_missing_file_returns_empty(memory_dir: Path):
    assert load_query_cache(memory_dir / "query_cache.json") == {}


def test_query_cache_round_trip(memory_dir: Path):
    data = {
        "wie funktioniert oauth": {
            "matched_concepts": ["oauth2-flow", "jwt-tokens"],
            "last_used": "2026-05-10T14:32:00Z",
            "use_count": 3,
            "user_satisfied": True,
        },
    }
    save_query_cache(memory_dir / "query_cache.json", data)
    assert load_query_cache(memory_dir / "query_cache.json") == data


def test_load_path_frequency_missing_file_returns_empty(memory_dir: Path):
    assert load_path_frequency(memory_dir / "path_frequency.json") == {}


def test_path_frequency_round_trip(memory_dir: Path):
    data = {
        "oauth2-flow": {
            "co_accessed": {"jwt-tokens": 8, "session-management": 3},
            "total_accesses": 12,
        },
    }
    save_path_frequency(memory_dir / "path_frequency.json", data)
    assert load_path_frequency(memory_dir / "path_frequency.json") == data


def test_load_user_preferences_missing_file_returns_defaults(memory_dir: Path):
    prefs = load_user_preferences(memory_dir / "user_preferences.json")
    assert prefs == DEFAULT_USER_PREFERENCES


def test_default_user_preferences_keys():
    assert "response_language" in DEFAULT_USER_PREFERENCES
    assert "preferred_depth" in DEFAULT_USER_PREFERENCES
    assert "technical_terms" in DEFAULT_USER_PREFERENCES
    assert "always_show_sources" in DEFAULT_USER_PREFERENCES


def test_user_preferences_round_trip(memory_dir: Path):
    custom = {
        "response_language": "de",
        "preferred_depth": "detailed",
        "technical_terms": "keep_english",
        "always_show_sources": True,
    }
    save_user_preferences(memory_dir / "user_preferences.json", custom)
    assert load_user_preferences(memory_dir / "user_preferences.json") == custom


def test_load_learned_aliases_missing_file_returns_empty(memory_dir: Path):
    assert load_learned_aliases(memory_dir / "learned_aliases.json") == {}


def test_learned_aliases_round_trip(memory_dir: Path):
    data = {"unser Auth-Stack": "oauth2-flow", "der Token-Flow": "jwt-tokens"}
    save_learned_aliases(memory_dir / "learned_aliases.json", data)
    assert load_learned_aliases(memory_dir / "learned_aliases.json") == data


def test_load_session_log_missing_file_returns_empty_list(memory_dir: Path):
    assert load_session_log(memory_dir / "session_log.json") == []


def test_session_log_round_trip(memory_dir: Path):
    data = [
        {
            "session_id": "2026-05-10-auth-brainstorm",
            "topic": "Authentifizierung neue App",
            "hypotheses": [
                {
                    "id": "h1",
                    "proposition": "OAuth2 + JWT for Web+Mobile",
                    "initial_confidence": "high",
                    "user_status": "accepted_for_deeper_exploration",
                    "outcome": None,
                },
            ],
        },
    ]
    save_session_log(memory_dir / "session_log.json", data)
    assert load_session_log(memory_dir / "session_log.json") == data


def test_save_creates_parent_dirs(tmp_path: Path):
    """save_X creates the parent directory if it does not exist."""
    nested = tmp_path / "deep" / "nested" / "memory" / "query_cache.json"
    save_query_cache(nested, {"q": {"matched_concepts": []}})
    assert nested.exists()
