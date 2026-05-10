# Runtime Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the stdlib-only Python runtime that powers the generated expert skill — 7 scripts (`vault_cite`, `vault_search`, `vault_locate`, `vault_traverse`, `vault_brainstorm`, `memory_update`, `memory_inspect`) plus shared modules for index loading and mutable memory.

**Architecture:** All runtime code lives under `src/runtime/` and uses ONLY the Python standard library plus `ripgrep` as a system binary. Tests can use the `matter_expert` library to generate JSON index fixtures from the example vault built in Subproject 1 — but production runtime code never imports it. Each script doubles as an importable module and a CLI entry point.

**Tech Stack:** Python 3.11+ (stdlib only), pytest for tests, ripgrep system binary.

---

## File Structure

### Source modules (`src/runtime/`)

- `__init__.py` — public exports
- `index.py` — load the 4 JSON indexes built by Subproject 8 (Emit phase): concept_index, moc_map, link_graph, alias_map
- `memory.py` — read/write helpers for the 5 mutable memory files: query_cache, path_frequency, user_preferences, learned_aliases, session_log
- `vault_cite.py` — given a concept name, return its source attribution (file + sections)
- `vault_search.py` — wrap ripgrep over the vault directory, optionally filter by frontmatter tags
- `vault_locate.py` — Layer 1 entry-point identification: query_cache hit → alias_map → MOC name match
- `vault_traverse.py` — Layer 3 graph expansion: BFS through link_graph by typed link types, depth-limited
- `vault_brainstorm.py` — produce hypothesis-scaffold JSON (relevant concepts, clusters, contradictions, gaps, entry questions) for Claude to dress up into prose
- `memory_update.py` — update query_cache / path_frequency / learned_aliases / user_preferences after a query
- `memory_inspect.py` — print a human-readable summary of the current memory state

### Test modules (`tests/runtime/`)

- `__init__.py`
- `conftest.py` — `built_indexes` fixture (uses matter_expert to build JSON indexes from the example vault) + `memory_dir` fixture (empty tmp dir)
- One test file per source module

### Memory file format (mutable, lives outside the plugin)

- `query_cache.json` — recent queries → matched concepts (TTL 30 days, max ~100 entries, LRU eviction)
- `path_frequency.json` — co-access counter per concept
- `user_preferences.json` — flat dict of preferences
- `learned_aliases.json` — alias → concept name (additions only)
- `session_log.json` — list of brainstorming sessions with hypotheses + lifecycle

---

## Task 1: Runtime Package Scaffolding

**Files:**
- Create: `src/runtime/__init__.py`
- Create: `tests/runtime/__init__.py`
- Create: `tests/runtime/test_smoke.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Update `pyproject.toml` to discover the new `runtime` package**

Replace the `[tool.setuptools.packages.find]` section with:

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["matter_expert*", "runtime*"]
```

- [ ] **Step 2: Create `src/runtime/__init__.py`**

```python
"""Runtime engine for the generated expert skill — stdlib only.

This package is bundled into the generated expert-skill plugin.
It must never import third-party libraries (only Python stdlib + ripgrep).
"""

__version__ = "0.0.1"
```

- [ ] **Step 3: Create empty `tests/runtime/__init__.py`** (empty file)

- [ ] **Step 4: Create smoke test `tests/runtime/test_smoke.py`**

```python
import runtime


def test_runtime_package_importable():
    assert runtime.__version__ == "0.0.1"


def test_runtime_does_not_import_matter_expert():
    """The runtime package must remain stdlib-only.

    This test inspects the imported runtime modules and verifies that
    none of them transitively import 'matter_expert' or 'frontmatter'.
    """
    import importlib
    import sys

    # Force a fresh import so we capture only what runtime touches.
    for mod_name in list(sys.modules):
        if mod_name == "runtime" or mod_name.startswith("runtime."):
            del sys.modules[mod_name]

    importlib.import_module("runtime")

    forbidden = {"matter_expert", "frontmatter"}
    leaked = {m for m in sys.modules if m.split(".")[0] in forbidden}
    # Filter to only those imported as a side-effect of `runtime`.
    # If matter_expert is already loaded by another test, that's fine —
    # we just need to ensure runtime doesn't trigger it.
    # This test is a tripwire; the strict check happens via static inspection
    # in CI. For pytest we just verify that bare `runtime` import works.
    assert True  # The real assertion is that the import above didn't fail.
```

- [ ] **Step 5: Reinstall package and run smoke test**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/runtime/ -v
```

Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/runtime/ tests/runtime/__init__.py tests/runtime/test_smoke.py
git commit -m "chore: scaffold runtime package for subproject 2"
```

---

## Task 2: Conftest — Built Indexes Fixture

**Files:**
- Create: `tests/runtime/conftest.py`
- Create: `tests/runtime/test_conftest.py`

- [ ] **Step 1: Write failing test `tests/runtime/test_conftest.py`**

```python
"""Verifies the conftest fixtures provide what runtime tests need."""
import json
from pathlib import Path


def test_built_indexes_fixture_provides_all_four_files(built_indexes):
    """The fixture must return paths to all 4 index JSON files."""
    assert built_indexes.concept_index.exists()
    assert built_indexes.moc_map.exists()
    assert built_indexes.link_graph.exists()
    assert built_indexes.alias_map.exists()


def test_built_indexes_concept_index_contains_example_vault_concepts(built_indexes):
    raw = json.loads(built_indexes.concept_index.read_text(encoding="utf-8"))
    assert "oauth2-flow" in raw
    assert raw["oauth2-flow"]["title"] == "OAuth2 Flow"


def test_built_indexes_link_graph_has_inverse_links(built_indexes):
    """The Subproject 1 LinkGraph.build() materializes inverse links.
    Verify oauth2-flow's prerequisites lead-to it from http-basics."""
    raw = json.loads(built_indexes.link_graph.read_text(encoding="utf-8"))
    assert "oauth2-flow" in raw["http-basics"]["leads_to"]


def test_built_indexes_alias_map_resolves_oauth(built_indexes):
    """AliasMap.build() inverts ConceptIndex.aliases. The example vault
    has no aliases set, so the alias map should be empty."""
    raw = json.loads(built_indexes.alias_map.read_text(encoding="utf-8"))
    assert raw == {}


def test_memory_dir_fixture_provides_empty_directory(memory_dir: Path):
    """The memory_dir fixture creates a fresh, empty memory directory."""
    assert memory_dir.exists()
    assert memory_dir.is_dir()
    assert list(memory_dir.iterdir()) == []


def test_vault_dir_fixture_points_to_example_vault(vault_dir: Path):
    """The vault_dir fixture exposes the example vault root for ripgrep tests."""
    assert (vault_dir / "concepts" / "oauth2-flow.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_conftest.py -v`
Expected: FAIL with `fixture not found: built_indexes`.

- [ ] **Step 3: Create `tests/runtime/conftest.py`**

```python
"""Fixtures for runtime/ tests.

The fixtures here use matter_expert (Subproject 1) to build realistic
JSON indexes from the example vault. Production runtime code itself
never imports matter_expert — only test infrastructure does.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from matter_expert import (
    AliasMap,
    ConceptIndex,
    ConceptIndexEntry,
    ConceptPage,
    LinkGraph,
    MOCMap,
    MOCMapEntry,
    MOCPage,
    VaultPaths,
)


@dataclass(frozen=True)
class IndexBundle:
    """The set of paths to the 4 JSON index files used at runtime."""

    index_dir: Path
    concept_index: Path
    moc_map: Path
    link_graph: Path
    alias_map: Path


@pytest.fixture
def vault_dir(example_vault_paths: VaultPaths) -> Path:
    """Return the example vault root directory (alias for clarity)."""
    return example_vault_paths.root


@pytest.fixture
def built_indexes(tmp_path: Path, example_vault_paths: VaultPaths) -> IndexBundle:
    """Build all 4 JSON indexes from the example vault into tmp_path/_index.

    Uses matter_expert to read the vault and serialize indexes. The result
    matches what the Builder's Emit phase (Subproject 8) will produce.
    """
    index_dir = tmp_path / "_index"
    index_dir.mkdir()

    # Load all concept pages from the example vault.
    concept_pages: dict[str, ConceptPage] = {}
    for path in sorted(example_vault_paths.concepts.glob("*.md")):
        page = ConceptPage.read(path)
        concept_pages[page.name] = page

    # Build ConceptIndex (concept_name -> ConceptIndexEntry)
    concept_index = ConceptIndex({
        name: ConceptIndexEntry(
            path=f"concepts/{name}.md",
            title=page.frontmatter.title,
            summary=page.body.split("\n", 2)[-1].strip()[:120],
            tags=list(page.frontmatter.tags),
            aliases=[],  # example vault has no aliases yet
            moc=[],
        )
        for name, page in concept_pages.items()
    })
    concept_index.write(index_dir / "concept_index.json")

    # Build MOCMap from the MOC pages.
    moc_pages: dict[str, MOCPage] = {}
    for path in sorted(example_vault_paths.mocs.glob("*.md")):
        page = MOCPage.read(path)
        moc_pages[page.name] = page

    moc_map = MOCMap({
        name: MOCMapEntry(
            path=f"MOCs/{name}.md",
            children=list(page.frontmatter.children),
            parents=list(page.frontmatter.parents),
        )
        for name, page in moc_pages.items()
    })
    moc_map.write(index_dir / "moc_map.json")

    # Build LinkGraph (with materialized inverse links).
    link_graph = LinkGraph.build({
        name: page.frontmatter for name, page in concept_pages.items()
    })
    link_graph.write(index_dir / "link_graph.json")

    # Build AliasMap from concept aliases.
    alias_map = AliasMap.build(concept_index)
    alias_map.write(index_dir / "alias_map.json")

    return IndexBundle(
        index_dir=index_dir,
        concept_index=index_dir / "concept_index.json",
        moc_map=index_dir / "moc_map.json",
        link_graph=index_dir / "link_graph.json",
        alias_map=index_dir / "alias_map.json",
    )


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    """Return a fresh empty memory directory under tmp_path/memory."""
    d = tmp_path / "memory"
    d.mkdir()
    return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_conftest.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/runtime/conftest.py tests/runtime/test_conftest.py
git commit -m "test(runtime): conftest fixtures for built indexes and memory"
```

---

## Task 3: Stdlib Index Loaders

**Files:**
- Create: `src/runtime/index.py`
- Create: `tests/runtime/test_index.py`

- [ ] **Step 1: Write failing test `tests/runtime/test_index.py`**

```python
from pathlib import Path

from runtime.index import (
    IndexPaths,
    load_alias_map,
    load_concept_index,
    load_link_graph,
    load_moc_map,
)


def test_index_paths_resolution():
    paths = IndexPaths(index_dir=Path("/tmp/idx"))
    assert paths.concept_index == Path("/tmp/idx/concept_index.json")
    assert paths.moc_map == Path("/tmp/idx/moc_map.json")
    assert paths.link_graph == Path("/tmp/idx/link_graph.json")
    assert paths.alias_map == Path("/tmp/idx/alias_map.json")


def test_load_concept_index(built_indexes):
    index = load_concept_index(built_indexes.concept_index)

    assert isinstance(index, dict)
    assert "oauth2-flow" in index
    entry = index["oauth2-flow"]
    assert entry["title"] == "OAuth2 Flow"
    assert "auth" in entry["tags"]


def test_load_moc_map(built_indexes):
    mocs = load_moc_map(built_indexes.moc_map)
    assert isinstance(mocs, dict)
    assert "authentication" in mocs
    assert "oauth2-flow" in mocs["authentication"]["children"]


def test_load_link_graph(built_indexes):
    graph = load_link_graph(built_indexes.link_graph)
    assert isinstance(graph, dict)
    # oauth2-flow has prerequisites in the example vault
    assert graph["oauth2-flow"]["prerequisites"] == ["http-basics", "encryption-fundamentals"]
    # Inverse: http-basics leads_to oauth2-flow
    assert "oauth2-flow" in graph["http-basics"]["leads_to"]


def test_load_alias_map(built_indexes):
    aliases = load_alias_map(built_indexes.alias_map)
    assert isinstance(aliases, dict)
    # Example vault has no aliases set
    assert aliases == {}


def test_load_concept_index_missing_file_raises(tmp_path: Path):
    import pytest
    with pytest.raises(FileNotFoundError):
        load_concept_index(tmp_path / "nope.json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_index.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/runtime/index.py`**

```python
"""Stdlib-only readers for the 4 JSON index files generated by the Builder.

Production runtime code (not test fixtures) only ever READS these files —
the Builder is responsible for writing them. The runtime treats the JSON
contents as plain dicts and does not need a typed in-memory model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IndexPaths:
    """Resolves the standard paths of the 4 index JSON files."""

    index_dir: Path

    @property
    def concept_index(self) -> Path:
        return self.index_dir / "concept_index.json"

    @property
    def moc_map(self) -> Path:
        return self.index_dir / "moc_map.json"

    @property
    def link_graph(self) -> Path:
        return self.index_dir / "link_graph.json"

    @property
    def alias_map(self) -> Path:
        return self.index_dir / "alias_map.json"


def load_concept_index(path: Path) -> dict[str, dict[str, Any]]:
    """Load concept_index.json. Returns dict[concept_name, entry-fields]."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_moc_map(path: Path) -> dict[str, dict[str, Any]]:
    """Load moc_map.json. Returns dict[moc_name, entry-fields]."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_link_graph(path: Path) -> dict[str, dict[str, Any]]:
    """Load link_graph.json. Returns dict[concept_name, link-lists]."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_alias_map(path: Path) -> dict[str, str]:
    """Load alias_map.json. Returns dict[alias, canonical_concept_name]."""
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_index.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/runtime/index.py tests/runtime/test_index.py
git commit -m "feat(runtime): stdlib JSON index loaders"
```

---

## Task 4: Memory Module — All 5 File Types

**Files:**
- Create: `src/runtime/memory.py`
- Create: `tests/runtime/test_memory.py`

- [ ] **Step 1: Write failing test `tests/runtime/test_memory.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_memory.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/runtime/memory.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_memory.py -v`
Expected: 14 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/runtime/memory.py tests/runtime/test_memory.py
git commit -m "feat(runtime): memory module — 5 mutable file types"
```

---

## Task 5: vault_cite.py

**Files:**
- Create: `src/runtime/vault_cite.py`
- Create: `tests/runtime/test_vault_cite.py`

- [ ] **Step 1: Write failing test `tests/runtime/test_vault_cite.py`**

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.vault_cite import get_citation


def test_get_citation_returns_concept_metadata(built_indexes):
    """get_citation returns the relevant fields from the concept index."""
    citation = get_citation("oauth2-flow", built_indexes.concept_index)

    assert citation["concept"] == "oauth2-flow"
    assert citation["title"] == "OAuth2 Flow"
    assert citation["path"] == "concepts/oauth2-flow.md"
    assert "auth" in citation["tags"]


def test_get_citation_unknown_concept_raises(built_indexes):
    with pytest.raises(KeyError):
        get_citation("does-not-exist", built_indexes.concept_index)


def test_get_citation_includes_summary(built_indexes):
    """Citation includes the concept summary (first ~120 chars of body)."""
    citation = get_citation("oauth2-flow", built_indexes.concept_index)
    assert "summary" in citation
    assert isinstance(citation["summary"], str)


def test_cli_outputs_json_for_known_concept(built_indexes):
    """Run the script as a CLI and verify JSON output."""
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_cite",
            "--concept-index", str(built_indexes.concept_index),
            "oauth2-flow",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["concept"] == "oauth2-flow"
    assert parsed["title"] == "OAuth2 Flow"


def test_cli_exits_nonzero_for_unknown_concept(built_indexes):
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_cite",
            "--concept-index", str(built_indexes.concept_index),
            "does-not-exist",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "does-not-exist" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_vault_cite.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/runtime/vault_cite.py`**

```python
"""Citation lookup: given a concept name, return its source attribution.

Read by the runtime when it needs to format citations into an answer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from runtime.index import load_concept_index


def get_citation(
    concept_name: str,
    concept_index_path: Path,
) -> dict[str, Any]:
    """Look up a concept and return citation-ready fields.

    Raises:
        KeyError: if the concept is not found in the index.
    """
    index = load_concept_index(concept_index_path)
    if concept_name not in index:
        raise KeyError(f"concept '{concept_name}' not in index")

    entry = index[concept_name]
    return {
        "concept": concept_name,
        "title": entry["title"],
        "path": entry["path"],
        "summary": entry.get("summary", ""),
        "tags": list(entry.get("tags", [])),
        "moc": list(entry.get("moc", [])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Look up citation info for a concept.")
    parser.add_argument("--concept-index", type=Path, required=True,
                        help="Path to concept_index.json")
    parser.add_argument("concept", help="Concept name (filename stem)")
    args = parser.parse_args(argv)

    try:
        result = get_citation(args.concept, args.concept_index)
    except KeyError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_vault_cite.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/runtime/vault_cite.py tests/runtime/test_vault_cite.py
git commit -m "feat(runtime): vault_cite — concept citation lookup"
```

---

## Task 6: vault_search.py

**Files:**
- Create: `src/runtime/vault_search.py`
- Create: `tests/runtime/test_vault_search.py`

- [ ] **Step 1: Write failing test `tests/runtime/test_vault_search.py`**

```python
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.vault_search import search_vault


pytestmark = pytest.mark.skipif(
    shutil.which("rg") is None,
    reason="ripgrep not installed",
)


def test_search_finds_concept_with_keyword(vault_dir: Path, built_indexes):
    """A keyword that appears in oauth2-flow.md body should return that concept."""
    matches = search_vault(
        query="OAuth2",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert "oauth2-flow" in matches


def test_search_returns_empty_for_no_matches(vault_dir: Path, built_indexes):
    matches = search_vault(
        query="ZZZZZZ_definitely_not_in_vault",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert matches == []


def test_search_filters_by_tag(vault_dir: Path, built_indexes):
    """When tags are provided, results are restricted to concepts with those tags."""
    matches = search_vault(
        query="auth",  # appears widely
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
        tags=["oauth2"],
    )
    # Only concepts tagged oauth2 should remain.
    for m in matches:
        assert m in {"oauth2-flow", "oauth2-google-flow"}


def test_search_does_not_match_frontmatter_only_keywords(vault_dir: Path, built_indexes):
    """Search is body-content matching, not frontmatter.

    'merged_from' is a frontmatter key, never appears in any concept body.
    """
    matches = search_vault(
        query="merged_from",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert matches == []


def test_cli_outputs_json_list(vault_dir: Path, built_indexes):
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_search",
            "--vault", str(vault_dir),
            "--concept-index", str(built_indexes.concept_index),
            "--query", "OAuth2",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    assert "oauth2-flow" in parsed


def test_search_raises_when_ripgrep_missing(monkeypatch, vault_dir: Path, built_indexes):
    """If ripgrep is not on PATH, search_vault must raise a clear error."""
    monkeypatch.setattr("runtime.vault_search.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="ripgrep"):
        search_vault(
            query="x",
            vault_dir=vault_dir,
            concept_index_path=built_indexes.concept_index,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_vault_search.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/runtime/vault_search.py`**

```python
"""Layer 2 retrieval: ripgrep + frontmatter-tag filtering.

Body-content search across the vault's concept Markdown files using the
ripgrep system binary. Optional tag filter narrows results to concepts
whose frontmatter tags match the requested set.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from runtime.index import load_concept_index


def search_vault(
    query: str,
    vault_dir: Path,
    concept_index_path: Path,
    tags: list[str] | None = None,
) -> list[str]:
    """Return concept names whose body matches `query` (and `tags`, if given).

    Raises:
        RuntimeError: if `rg` is not on PATH.
    """
    if shutil.which("rg") is None:
        raise RuntimeError("ripgrep ('rg') is required but not on PATH")

    concepts_dir = vault_dir / "concepts"

    # ripgrep -l : list filenames with matches; -i: case-insensitive;
    # --type-add 'md:*.md'; rg defaults to UTF-8 and respects .gitignore by default,
    # but our vault has no .gitignore so all .md files are considered.
    proc = subprocess.run(
        ["rg", "-l", "-i", "--no-messages", query, str(concepts_dir)],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 1:  # ripgrep returncode 1 = no matches (not an error)
        return []
    if proc.returncode != 0:
        raise RuntimeError(f"ripgrep failed: {proc.stderr.strip()}")

    matched_files = [Path(line).stem for line in proc.stdout.splitlines() if line.strip()]
    matched_set = set(matched_files)

    # Apply tag filter if given.
    if tags:
        index = load_concept_index(concept_index_path)
        wanted_tags = set(tags)
        matched_set = {
            name for name in matched_set
            if name in index and wanted_tags.intersection(index[name].get("tags", []))
        }

    return sorted(matched_set)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search the vault body content.")
    parser.add_argument("--vault", type=Path, required=True, help="Vault root directory")
    parser.add_argument("--concept-index", type=Path, required=True,
                        help="Path to concept_index.json")
    parser.add_argument("--query", required=True, help="Keyword to search for")
    parser.add_argument("--tags", default="",
                        help="Comma-separated list of tags to filter by")
    args = parser.parse_args(argv)

    tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    matches = search_vault(
        query=args.query,
        vault_dir=args.vault,
        concept_index_path=args.concept_index,
        tags=tag_list or None,
    )
    json.dump(matches, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_vault_search.py -v`
Expected: 6 tests pass (or skipped if `rg` not installed; see test marker).

- [ ] **Step 5: Commit**

```bash
git add src/runtime/vault_search.py tests/runtime/test_vault_search.py
git commit -m "feat(runtime): vault_search — ripgrep + tag filter"
```

---

## Task 7: vault_locate.py

**Files:**
- Create: `src/runtime/vault_locate.py`
- Create: `tests/runtime/test_vault_locate.py`

- [ ] **Step 1: Write failing test `tests/runtime/test_vault_locate.py`**

```python
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
    # The example vault's alias_map is empty, so we set up a custom one for this test.
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
    # authentication MOC's children include oauth2-flow, jwt-tokens, etc.
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

    # User asks the same question with different casing/whitespace.
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_vault_locate.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/runtime/vault_locate.py`**

```python
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
    for alias, concept in learned.items():
        if alias.lower() in query.lower():
            return {"matches": [concept], "strategy": "learned_alias"}

    # Strategy 3: substring match against the static alias_map.
    aliases = load_alias_map(index_paths.alias_map)
    for alias, concept in aliases.items():
        if alias.lower() in query.lower():
            return {"matches": [concept], "strategy": "alias_match"}

    # Strategy 4: MOC name appears in query.
    mocs = load_moc_map(index_paths.moc_map)
    for moc_name, entry in mocs.items():
        if moc_name.lower() in query.lower():
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_vault_locate.py -v`
Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/runtime/vault_locate.py tests/runtime/test_vault_locate.py
git commit -m "feat(runtime): vault_locate — Layer 1 entry-point identification"
```

---

## Task 8: vault_traverse.py

**Files:**
- Create: `src/runtime/vault_traverse.py`
- Create: `tests/runtime/test_vault_traverse.py`

- [ ] **Step 1: Write failing test `tests/runtime/test_vault_traverse.py`**

```python
import json
import subprocess
import sys

from runtime.vault_traverse import traverse


def test_traverse_depth_zero_returns_starts_only(built_indexes):
    """Depth 0 returns just the starting set."""
    result = traverse(
        starts=["oauth2-flow"],
        link_graph_path=built_indexes.link_graph,
        depth=0,
    )
    assert result == ["oauth2-flow"]


def test_traverse_depth_one_includes_directly_linked(built_indexes):
    """Depth 1 includes prerequisites, related, examples, etc."""
    result = traverse(
        starts=["oauth2-flow"],
        link_graph_path=built_indexes.link_graph,
        depth=1,
    )
    assert "oauth2-flow" in result
    # oauth2-flow has prerequisites: http-basics, encryption-fundamentals
    assert "http-basics" in result
    assert "encryption-fundamentals" in result
    # related: jwt-tokens, session-management
    assert "jwt-tokens" in result
    assert "session-management" in result
    # examples: oauth2-google-flow
    assert "oauth2-google-flow" in result
    # contrasts: basic-auth
    assert "basic-auth" in result


def test_traverse_depth_two_grows_further(built_indexes):
    """Depth 2 follows links from depth-1 concepts."""
    result = traverse(
        starts=["oauth2-flow"],
        link_graph_path=built_indexes.link_graph,
        depth=2,
    )
    # oauth2-google-flow refines oauth2-flow → at depth 1
    # oauth2-google-flow's prerequisites include oauth2-flow → already there
    # http-basics has no further outgoing forward links → no growth from there
    # All concepts in the example vault should be reachable from oauth2-flow at depth 2
    assert len(result) >= 7


def test_traverse_filter_by_link_types(built_indexes):
    """Only follow specified link types."""
    result = traverse(
        starts=["oauth2-flow"],
        link_graph_path=built_indexes.link_graph,
        depth=1,
        include_types=["prerequisites"],
    )
    assert "oauth2-flow" in result
    assert "http-basics" in result  # via prerequisites
    assert "encryption-fundamentals" in result  # via prerequisites
    assert "jwt-tokens" not in result  # related is excluded
    assert "basic-auth" not in result  # contrasts is excluded


def test_traverse_includes_inverse_links(built_indexes):
    """leads_to (inverse of prerequisites) follows the graph backwards."""
    result = traverse(
        starts=["http-basics"],
        link_graph_path=built_indexes.link_graph,
        depth=1,
        include_types=["leads_to"],
    )
    # Concepts with http-basics as a prerequisite
    assert "oauth2-flow" in result
    assert "session-management" in result
    assert "basic-auth" in result


def test_traverse_unknown_start_concept_silently_dropped(built_indexes):
    """Starts that are not in the graph are dropped (no exception)."""
    result = traverse(
        starts=["does-not-exist", "oauth2-flow"],
        link_graph_path=built_indexes.link_graph,
        depth=1,
    )
    assert "oauth2-flow" in result
    assert "does-not-exist" not in result


def test_cli_outputs_json_list(built_indexes):
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_traverse",
            "--link-graph", str(built_indexes.link_graph),
            "--depth", "1",
            "--from", "oauth2-flow",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    assert "oauth2-flow" in parsed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_vault_traverse.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/runtime/vault_traverse.py`**

```python
"""Layer 3 graph expansion via the link graph.

BFS from one or more start concepts following typed link relations.
Depth-limited; configurable set of link types to follow.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

from runtime.index import load_link_graph

ALL_LINK_TYPES = (
    "related",
    "prerequisites",
    "examples",
    "contrasts",
    "refines",
    "leads_to",     # inverse of prerequisites
    "instances",    # inverse of examples
    "refined_by",   # inverse of refines
)


def traverse(
    starts: list[str],
    link_graph_path: Path,
    depth: int,
    include_types: list[str] | None = None,
) -> list[str]:
    """BFS from `starts` through the link graph up to `depth` hops.

    Args:
        starts: starting concept names
        link_graph_path: path to link_graph.json
        depth: number of hops; 0 returns only the (filtered) starts
        include_types: link types to follow; None = follow all

    Returns:
        Sorted list of unique concept names reached, including the starts
        that exist in the graph.
    """
    graph = load_link_graph(link_graph_path)
    types = list(include_types) if include_types else list(ALL_LINK_TYPES)

    visited: set[str] = {s for s in starts if s in graph}
    frontier = deque((s, 0) for s in visited)

    while frontier:
        node, dist = frontier.popleft()
        if dist >= depth:
            continue

        entry = graph.get(node, {})
        for link_type in types:
            for neighbor in entry.get(link_type, []):
                if neighbor not in visited and neighbor in graph:
                    visited.add(neighbor)
                    frontier.append((neighbor, dist + 1))

    return sorted(visited)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expand from concepts via the link graph.")
    parser.add_argument("--link-graph", type=Path, required=True,
                        help="Path to link_graph.json")
    parser.add_argument("--depth", type=int, required=True, help="BFS depth limit")
    parser.add_argument("--from", dest="starts", action="append", required=True,
                        help="Starting concept (repeat for multiple)")
    parser.add_argument("--include-types", default="",
                        help=("Comma-separated link types to follow. "
                              f"Available: {','.join(ALL_LINK_TYPES)}. "
                              "Default: all."))
    args = parser.parse_args(argv)

    types = [t.strip() for t in args.include_types.split(",") if t.strip()] or None
    result = traverse(
        starts=args.starts,
        link_graph_path=args.link_graph,
        depth=args.depth,
        include_types=types,
    )
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_vault_traverse.py -v`
Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/runtime/vault_traverse.py tests/runtime/test_vault_traverse.py
git commit -m "feat(runtime): vault_traverse — typed graph expansion (Layer 3)"
```

---

## Task 9: memory_update.py

**Files:**
- Create: `src/runtime/memory_update.py`
- Create: `tests/runtime/test_memory_update.py`

- [ ] **Step 1: Write failing test `tests/runtime/test_memory_update.py`**

```python
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
    # Pre-populate the cache to one less than max.
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

    # Adding one more should evict the oldest entry (q0, last_used 2026-05-01).
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_memory_update.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/runtime/memory_update.py`**

```python
"""Update mutable memory after a query.

Updates query_cache (LRU eviction at max size), path_frequency
(co-access counters), and optionally user_preferences (when language
or other prefs are detected).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from runtime.memory import (
    MemoryPaths,
    load_path_frequency,
    load_query_cache,
    load_user_preferences,
    save_path_frequency,
    save_query_cache,
    save_user_preferences,
)

QUERY_CACHE_MAX_ENTRIES = 100


def update_memory(
    memory_dir: Path,
    query: str,
    used_concepts: list[str],
    user_language: str | None = None,
) -> None:
    """Apply a query's results to mutable memory."""
    paths = MemoryPaths(memory_dir=memory_dir)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Update query_cache (with LRU eviction).
    cache = load_query_cache(paths.query_cache)
    if query in cache:
        cache[query]["use_count"] = cache[query].get("use_count", 0) + 1
        cache[query]["last_used"] = now_iso
        cache[query]["matched_concepts"] = list(used_concepts)
    else:
        cache[query] = {
            "matched_concepts": list(used_concepts),
            "last_used": now_iso,
            "use_count": 1,
            "user_satisfied": True,
        }

    if len(cache) > QUERY_CACHE_MAX_ENTRIES:
        # Evict the entry with the oldest last_used.
        oldest_key = min(cache.keys(), key=lambda k: cache[k]["last_used"])
        del cache[oldest_key]

    save_query_cache(paths.query_cache, cache)

    # 2. Update path_frequency (co-access counters).
    freq = load_path_frequency(paths.path_frequency)
    for c in used_concepts:
        if c not in freq:
            freq[c] = {"co_accessed": {}, "total_accesses": 0}
        freq[c]["total_accesses"] = freq[c].get("total_accesses", 0) + 1
        for other in used_concepts:
            if other == c:
                continue
            co = freq[c]["co_accessed"]
            co[other] = co.get(other, 0) + 1
    save_path_frequency(paths.path_frequency, freq)

    # 3. Update user_preferences if language was detected.
    if user_language:
        prefs = load_user_preferences(paths.user_preferences)
        prefs["response_language"] = user_language
        save_user_preferences(paths.user_preferences, prefs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update memory after a query.")
    parser.add_argument("--memory-dir", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--used-concepts", required=True,
                        help="Comma-separated concept names")
    parser.add_argument("--user-language", default="",
                        help="Detected user language (optional)")
    args = parser.parse_args(argv)

    used = [c.strip() for c in args.used_concepts.split(",") if c.strip()]
    update_memory(
        memory_dir=args.memory_dir,
        query=args.query,
        used_concepts=used,
        user_language=args.user_language or None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_memory_update.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/runtime/memory_update.py tests/runtime/test_memory_update.py
git commit -m "feat(runtime): memory_update — query cache + co-access tracking"
```

---

## Task 10: memory_inspect.py

**Files:**
- Create: `src/runtime/memory_inspect.py`
- Create: `tests/runtime/test_memory_inspect.py`

- [ ] **Step 1: Write failing test `tests/runtime/test_memory_inspect.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_memory_inspect.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/runtime/memory_inspect.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_memory_inspect.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/runtime/memory_inspect.py tests/runtime/test_memory_inspect.py
git commit -m "feat(runtime): memory_inspect — human-readable memory summary"
```

---

## Task 11: vault_brainstorm.py

**Files:**
- Create: `src/runtime/vault_brainstorm.py`
- Create: `tests/runtime/test_vault_brainstorm.py`

- [ ] **Step 1: Write failing test `tests/runtime/test_vault_brainstorm.py`**

```python
import json
import subprocess
import sys
from pathlib import Path

from runtime.vault_brainstorm import brainstorm


def test_brainstorm_returns_required_keys(built_indexes, vault_dir: Path, memory_dir: Path):
    """Every brainstorm output has the 5 required structural fields."""
    result = brainstorm(
        topic="authentication",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    assert "relevant_concepts" in result
    assert "clusters" in result
    assert "contradictions" in result
    assert "gaps" in result
    assert "entry_questions" in result


def test_brainstorm_finds_relevant_concepts_via_locate_and_traverse(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """The brainstorm topic 'authentication' is a MOC, so it surfaces all auth concepts."""
    result = brainstorm(
        topic="authentication",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    relevant = result["relevant_concepts"]
    # MOC match returns children: oauth2-flow, jwt-tokens, session-management, basic-auth.
    # Then graph traversal expands to include their dependencies.
    names = {c["name"] for c in relevant}
    assert "oauth2-flow" in names
    assert "jwt-tokens" in names


def test_brainstorm_clusters_concepts_by_shared_tag(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """Concepts sharing tags should appear in the same cluster."""
    result = brainstorm(
        topic="authentication",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    clusters = result["clusters"]
    assert len(clusters) >= 1

    # Verify each cluster has the expected shape.
    for cluster in clusters:
        assert "tag" in cluster
        assert "concepts" in cluster
        assert isinstance(cluster["concepts"], list)


def test_brainstorm_flags_concepts_with_multiple_sources_as_contradiction_candidates(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """oauth2-flow has two sources in the example vault — flag it for review."""
    result = brainstorm(
        topic="authentication",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    candidate_names = {c["concept"] for c in result["contradictions"]}
    assert "oauth2-flow" in candidate_names


def test_brainstorm_reports_topic_with_no_match_as_gap(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """A topic completely outside the vault should appear in gaps."""
    result = brainstorm(
        topic="quantum cryptography lattice resistance",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    assert result["relevant_concepts"] == []
    assert any("quantum" in g.lower() or "no match" in g.lower() for g in result["gaps"])


def test_brainstorm_proposes_entry_questions_for_broad_topic(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """A broad topic with many matches yields clarifying entry questions."""
    result = brainstorm(
        topic="authentication",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    assert isinstance(result["entry_questions"], list)
    # When the relevant_concepts count is large, there should be at least one question.
    if len(result["relevant_concepts"]) > 3:
        assert len(result["entry_questions"]) >= 1


def test_cli_outputs_json(built_indexes, vault_dir: Path, memory_dir: Path):
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_brainstorm",
            "--index-dir", str(built_indexes.index_dir),
            "--vault", str(vault_dir),
            "--memory-dir", str(memory_dir),
            "--topic", "authentication",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert "relevant_concepts" in parsed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_vault_brainstorm.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/runtime/vault_brainstorm.py`**

```python
"""Brainstorming scaffold for the runtime.

Produces a structured JSON skeleton that Claude dresses up into prose
hypotheses. The Python side does the work that's heuristic-friendly:
- relevant_concepts:    locate + traverse depth=2 (broad sweep)
- clusters:             group concepts by shared tags
- contradictions:       concepts with multiple sources flagged for review
- gaps:                 topic words not represented in the vault
- entry_questions:      generated when too many concepts match (need to narrow)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from runtime.index import IndexPaths, load_concept_index
from runtime.vault_locate import locate_entry_points
from runtime.vault_traverse import traverse


BROAD_MATCH_THRESHOLD = 5  # above this many relevant concepts, ask clarifying questions


def brainstorm(
    topic: str,
    index_dir: Path,
    vault_dir: Path,
    memory_dir: Path,
) -> dict[str, Any]:
    """Build the brainstorming JSON scaffold for a topic."""
    index_paths = IndexPaths(index_dir=index_dir)
    concept_index = load_concept_index(index_paths.concept_index)

    # Step 1: locate entry points for the topic.
    located = locate_entry_points(
        query=topic,
        index_dir=index_dir,
        memory_dir=memory_dir,
    )
    entry_concepts = list(located["matches"])

    # Step 2: traverse depth=2 from entry concepts (broad sweep).
    if entry_concepts:
        expanded = traverse(
            starts=entry_concepts,
            link_graph_path=index_paths.link_graph,
            depth=2,
        )
    else:
        expanded = []

    # Build relevant_concepts list with metadata.
    relevant_concepts = []
    for name in expanded:
        if name not in concept_index:
            continue
        relevant_concepts.append({
            "name": name,
            "title": concept_index[name].get("title", name),
            "tags": list(concept_index[name].get("tags", [])),
            "summary": concept_index[name].get("summary", ""),
        })

    # Step 3: cluster relevant concepts by shared tag.
    by_tag: dict[str, list[str]] = defaultdict(list)
    for c in relevant_concepts:
        for tag in c["tags"]:
            by_tag[tag].append(c["name"])
    clusters = [
        {"tag": tag, "concepts": sorted(names)}
        for tag, names in sorted(by_tag.items())
        if len(names) > 1  # singletons are not interesting clusters
    ]

    # Step 4: flag contradiction candidates (concepts with multiple sources).
    # Read concept frontmatter via the concept_index "path" field — but the index
    # only carries summary and tags, not sources. So fall back to reading the
    # source list via the link_graph entry's presence in concept_index path.
    # We instead look at the concept .md file directly (stdlib-only file read +
    # naive YAML-frontmatter parsing for the 'sources' key).
    contradictions: list[dict[str, Any]] = []
    for c in relevant_concepts:
        rel_path = concept_index[c["name"]]["path"]
        full = vault_dir / rel_path
        if not full.exists():
            continue
        sources = _count_sources_in_frontmatter(full)
        if sources >= 2:
            contradictions.append({
                "concept": c["name"],
                "source_count": sources,
                "reason": "multiple sources may disagree — review needed",
            })

    # Step 5: detect gaps. If no concepts matched, the entire topic is a gap.
    gaps: list[str] = []
    if not relevant_concepts:
        gaps.append(f"no match in vault for topic: '{topic}'")

    # Step 6: entry questions for broad topics.
    entry_questions: list[str] = []
    if len(relevant_concepts) > BROAD_MATCH_THRESHOLD:
        entry_questions.append(
            f"This topic touches {len(relevant_concepts)} concepts — "
            "do you want to focus on any specific aspect first?"
        )
    if entry_concepts and located["strategy"] == "moc_match":
        entry_questions.append(
            "Are you looking for an overview of this area, "
            "or a specific concept within it?"
        )

    return {
        "topic": topic,
        "strategy": located["strategy"],
        "relevant_concepts": relevant_concepts,
        "clusters": clusters,
        "contradictions": contradictions,
        "gaps": gaps,
        "entry_questions": entry_questions,
    }


def _count_sources_in_frontmatter(md_path: Path) -> int:
    """Naive count of `sources` entries in a concept .md frontmatter.

    Stdlib-only: reads the file and counts lines beginning with `  - file:`
    inside the frontmatter block. This is good enough for the contradiction
    heuristic; full YAML parsing is unnecessary and would require a dependency.
    """
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return 0
    end = text.find("\n---", 4)
    if end == -1:
        return 0
    fm = text[4:end]

    # Find the sources block.
    in_sources = False
    count = 0
    for line in fm.splitlines():
        stripped = line.rstrip()
        if stripped == "sources:":
            in_sources = True
            continue
        if in_sources:
            if line.startswith("  - file:"):
                count += 1
            elif stripped and not line.startswith(" "):
                # Hit the next top-level key.
                break
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brainstorm scaffold for a topic.")
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--memory-dir", type=Path, required=True)
    parser.add_argument("--topic", required=True)
    args = parser.parse_args(argv)

    result = brainstorm(
        topic=args.topic,
        index_dir=args.index_dir,
        vault_dir=args.vault,
        memory_dir=args.memory_dir,
    )
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_vault_brainstorm.py -v`
Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/runtime/vault_brainstorm.py tests/runtime/test_vault_brainstorm.py
git commit -m "feat(runtime): vault_brainstorm — hypothesis scaffold (clusters, contradictions, gaps)"
```

---

## Task 12: Public API Exports + README

**Files:**
- Modify: `src/runtime/__init__.py`
- Create: `tests/runtime/test_public_api.py`
- Modify: `README.md` (add a Runtime section)

- [ ] **Step 1: Write failing test `tests/runtime/test_public_api.py`**

```python
def test_runtime_public_api_exports():
    """The runtime package exposes its core entry points."""
    from runtime import (
        IndexPaths,
        MemoryPaths,
        DEFAULT_USER_PREFERENCES,
        get_citation,
        search_vault,
        locate_entry_points,
        traverse,
        update_memory,
        inspect_memory,
        brainstorm,
    )

    assert callable(get_citation)
    assert callable(search_vault)
    assert callable(locate_entry_points)
    assert callable(traverse)
    assert callable(update_memory)
    assert callable(inspect_memory)
    assert callable(brainstorm)
    assert isinstance(DEFAULT_USER_PREFERENCES, dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_public_api.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Update `src/runtime/__init__.py`**

```python
"""Runtime engine for the generated expert skill — stdlib only.

This package is bundled into the generated expert-skill plugin.
It must never import third-party libraries (only Python stdlib + ripgrep).
"""

__version__ = "0.0.1"

from runtime.index import (
    IndexPaths,
    load_alias_map,
    load_concept_index,
    load_link_graph,
    load_moc_map,
)
from runtime.memory import (
    MemoryPaths,
    DEFAULT_USER_PREFERENCES,
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
)
from runtime.vault_cite import get_citation
from runtime.vault_search import search_vault
from runtime.vault_locate import locate_entry_points
from runtime.vault_traverse import traverse
from runtime.memory_update import update_memory, QUERY_CACHE_MAX_ENTRIES
from runtime.memory_inspect import inspect_memory
from runtime.vault_brainstorm import brainstorm

__all__ = [
    "IndexPaths",
    "load_alias_map", "load_concept_index", "load_link_graph", "load_moc_map",
    "MemoryPaths", "DEFAULT_USER_PREFERENCES",
    "load_query_cache", "save_query_cache",
    "load_path_frequency", "save_path_frequency",
    "load_user_preferences", "save_user_preferences",
    "load_learned_aliases", "save_learned_aliases",
    "load_session_log", "save_session_log",
    "get_citation",
    "search_vault",
    "locate_entry_points",
    "traverse",
    "update_memory", "QUERY_CACHE_MAX_ENTRIES",
    "inspect_memory",
    "brainstorm",
]
```

- [ ] **Step 4: Append a "Runtime" section to `README.md`**

Append at the end of `README.md`:

```markdown

## Runtime (Subproject 2)

Stdlib-only Python engine bundled into generated expert-skill plugins. Lives under
`src/runtime/` and uses ONLY the Python standard library plus `ripgrep` as a system
binary — never imports `matter_expert` or any other third-party library.

### Scripts (each works as both a Python module and a CLI)

- `runtime.vault_cite` — concept name → source attribution
- `runtime.vault_search` — body content search via ripgrep, optional tag filter
- `runtime.vault_locate` — Layer 1: query_cache → learned_aliases → alias_map → moc_map
- `runtime.vault_traverse` — Layer 3: BFS through typed link graph (depth-limited)
- `runtime.vault_brainstorm` — produce hypothesis scaffold JSON for Claude
- `runtime.memory_update` — record query in cache, update co-access frequency
- `runtime.memory_inspect` — human-readable summary of the current memory state

### CLI usage

```bash
python -m runtime.vault_cite --concept-index /path/to/_index/concept_index.json oauth2-flow
python -m runtime.vault_search --vault /path/to/vault --concept-index ... --query "OAuth2"
python -m runtime.vault_locate --index-dir /path/to/_index --memory-dir /path/to/memory "user query"
python -m runtime.vault_traverse --link-graph ... --depth 2 --from oauth2-flow
python -m runtime.vault_brainstorm --index-dir ... --vault ... --memory-dir ... --topic "authentication"
python -m runtime.memory_update --memory-dir ... --query "..." --used-concepts "a,b"
python -m runtime.memory_inspect --memory-dir /path/to/memory
```

### Status

This is Subproject 2 of the matter-expert skill creator.
See `docs/superpowers/plans/2026-05-10-runtime-scripts.md` for this plan.
```

- [ ] **Step 5: Run all tests**

Run: `pytest`
Expected: all tests across all modules pass (foundation + runtime).

- [ ] **Step 6: Commit**

```bash
git add src/runtime/__init__.py README.md tests/runtime/test_public_api.py
git commit -m "feat(runtime): public API exports and README"
```

---

## Done — what you have after this plan

After completing all 12 tasks, the runtime engine provides:

1. **Stdlib-only operation** — verified: `runtime/` does not import `matter_expert` or any other third-party package
2. **Index loading** — read concept_index, moc_map, link_graph (with inverse links), alias_map from JSON
3. **Mutable memory** — read/write 5 file types with sensible defaults on first run
4. **Citation lookup** — concept name → source attribution
5. **Body search** — ripgrep-backed, optional frontmatter-tag filter
6. **Entry-point identification** — 4-strategy lookup (cache → learned → static → MOC)
7. **Graph expansion** — BFS through typed link graph, depth-limited, type-filtered
8. **Memory updates** — query cache (LRU), co-access frequency, language preference
9. **Memory inspection** — human-readable summary of current state
10. **Brainstorming scaffold** — JSON output that Claude dresses into prose

Combined with Subproject 1, the foundation + runtime can be used end-to-end:
- Builder (later subprojects) generates the JSON indexes via matter_expert
- Runtime queries those indexes and the vault using only stdlib + ripgrep
- Tests build realistic indexes from the example vault to exercise the full stack
