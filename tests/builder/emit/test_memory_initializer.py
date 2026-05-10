import json
from pathlib import Path

from builder.emit.memory_initializer import initialize_memory


def test_initialize_memory_creates_all_5_files(tmp_path: Path):
    memory_dir = tmp_path / "memory"
    initialize_memory(memory_dir=memory_dir, link_graph={})

    assert (memory_dir / "query_cache.json").exists()
    assert (memory_dir / "path_frequency.json").exists()
    assert (memory_dir / "user_preferences.json").exists()
    assert (memory_dir / "learned_aliases.json").exists()
    assert (memory_dir / "session_log.json").exists()


def test_initial_query_cache_empty(tmp_path: Path):
    memory_dir = tmp_path / "memory"
    initialize_memory(memory_dir=memory_dir, link_graph={})

    data = json.loads((memory_dir / "query_cache.json").read_text())
    assert data == {}


def test_initial_user_preferences_has_defaults(tmp_path: Path):
    memory_dir = tmp_path / "memory"
    initialize_memory(memory_dir=memory_dir, link_graph={})

    data = json.loads((memory_dir / "user_preferences.json").read_text())
    assert "response_language" in data
    assert "preferred_depth" in data


def test_initial_session_log_is_empty_list(tmp_path: Path):
    memory_dir = tmp_path / "memory"
    initialize_memory(memory_dir=memory_dir, link_graph={})

    data = json.loads((memory_dir / "session_log.json").read_text())
    assert data == []


def test_path_frequency_synthesized_from_link_graph(tmp_path: Path):
    """Concepts that are linked in the graph get an initial co-access count of 1."""
    memory_dir = tmp_path / "memory"
    link_graph = {
        "oauth2-flow": {
            "related": ["jwt-tokens"],
            "prerequisites": [], "examples": [],
            "contrasts": [], "refines": [],
            "leads_to": [], "instances": [], "refined_by": [],
        },
        "jwt-tokens": {
            "related": ["oauth2-flow"],
            "prerequisites": [], "examples": [],
            "contrasts": [], "refines": [],
            "leads_to": [], "instances": [], "refined_by": [],
        },
    }
    initialize_memory(memory_dir=memory_dir, link_graph=link_graph)

    freq = json.loads((memory_dir / "path_frequency.json").read_text())
    assert freq["oauth2-flow"]["co_accessed"]["jwt-tokens"] == 1
    assert freq["jwt-tokens"]["co_accessed"]["oauth2-flow"] == 1
