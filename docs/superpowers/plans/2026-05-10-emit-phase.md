# Emit Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Build the Emit phase — generates the final installable expert-skill plugin from the finished vault (indexes, SKILL.md, bundled runtime scripts, initial memory, plugin metadata, README).

**Architecture:** Inside `src/builder/emit/`. Mostly file-generation — minimal LLM use (only for SKILL.md trigger description). Reads vault from `vault_dir`, generates indexes via matter_expert's existing builders, copies the runtime package, writes initial mutable memory files. Result is a self-contained plugin directory ready to install.

**Tech Stack:** Python 3.11+ stdlib + matter_expert + builder. One optional LLM call for SKILL.md description generation.

---

## File Structure

```
src/builder/emit/
├── __init__.py
├── plugin_metadata.py    # PluginMetadata dataclass + plugin.json writer
├── index_builder.py      # Build the 4 _index/*.json files from vault
├── runtime_bundler.py    # Copy src/runtime/ → <plugin>/skills/<name>/scripts/
├── memory_initializer.py # Write initial mutable memory dir
├── skill_md.py           # SKILL.md generator (trigger description via LLM)
├── readme.py             # README.md generator
├── prompts.py            # Prompt for SKILL.md trigger description
└── orchestrator.py       # EmitOrchestrator — produces the final plugin

tests/builder/emit/
├── __init__.py
├── conftest.py           # CannedAgent + populated vault from QA conftest
└── test_*.py
```

---

## Task 1: PluginMetadata + plugin.json Writer

**Files:**
- Create: `src/builder/emit/__init__.py` (empty)
- Create: `src/builder/emit/plugin_metadata.py`
- Create: `tests/builder/emit/__init__.py` (empty)
- Create: `tests/builder/emit/test_plugin_metadata.py`

- [ ] **Step 1: Write failing test `tests/builder/emit/test_plugin_metadata.py`**

```python
import json
from pathlib import Path

from builder.emit.plugin_metadata import PluginMetadata, write_plugin_json


def test_plugin_metadata_construction():
    meta = PluginMetadata(
        name="oauth-expert",
        version="0.1.0",
        description="OAuth and JWT knowledge.",
        author="builder",
    )
    assert meta.name == "oauth-expert"


def test_write_plugin_json_creates_file(tmp_path: Path):
    meta = PluginMetadata(
        name="x", version="0.1.0",
        description="d", author="a",
    )
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    write_plugin_json(meta, plugin_root)

    plugin_json = plugin_root / ".claude-plugin" / "plugin.json"
    assert plugin_json.exists()
    data = json.loads(plugin_json.read_text(encoding="utf-8"))
    assert data["name"] == "x"
    assert data["version"] == "0.1.0"


def test_write_plugin_json_includes_skill_entry(tmp_path: Path):
    meta = PluginMetadata(name="x", version="0.1.0", description="d", author="a")
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    write_plugin_json(meta, plugin_root)
    data = json.loads(
        (plugin_root / ".claude-plugin" / "plugin.json").read_text()
    )
    # Must declare the bundled skill so Claude Code can auto-discover it.
    assert "skills" in data or data["name"]  # at minimum, name present
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/emit/plugin_metadata.py`**

```python
"""Plugin metadata + plugin.json writer."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PluginMetadata:
    name: str
    version: str
    description: str
    author: str
    homepage: str | None = None
    license: str = "Apache-2.0"


def write_plugin_json(meta: PluginMetadata, plugin_root: Path) -> Path:
    """Write `<plugin_root>/.claude-plugin/plugin.json` and return its path."""
    plugin_dir = plugin_root / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    path = plugin_dir / "plugin.json"
    data: dict = {
        "name": meta.name,
        "version": meta.version,
        "description": meta.description,
        "author": meta.author,
        "license": meta.license,
    }
    if meta.homepage:
        data["homepage"] = meta.homepage
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
git add src/builder/emit/ tests/builder/emit/
git commit -m "feat(builder/emit): PluginMetadata + plugin.json writer"
```

---

## Task 2: Index Builder

**Files:**
- Create: `src/builder/emit/index_builder.py`
- Create: `tests/builder/emit/test_index_builder.py`

Builds the 4 `_index/*.json` files from the vault by reading concept pages and using matter_expert builders.

- [ ] **Step 1: Write failing test**

```python
import json
from datetime import date
from pathlib import Path

from builder.emit.index_builder import build_indexes
from matter_expert import ConceptFrontmatter, ConceptPage, Source, VaultPaths


def _seed(paths: VaultPaths, name: str, title: str, tags=None,
          aliases=None, related=None, prereq=None):
    fm = ConceptFrontmatter(
        title=title,
        sources=[Source(file=f"{name}-source.md", sections=[])],
        tags=list(tags or []),
        created=date(2026, 5, 10),
        related=list(related or []),
        prerequisites=list(prereq or []),
    )
    paths.concepts.mkdir(parents=True, exist_ok=True)
    ConceptPage(
        frontmatter=fm,
        body=f"# {title}\n\nSummary of {title}.\n",
        path=paths.concept_for(name),
    ).write()


def test_build_indexes_writes_all_four_files(tmp_path: Path):
    paths = VaultPaths(root=tmp_path / "vault")
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()

    _seed(paths, "oauth2-flow", "OAuth2 Flow", tags=["auth"], related=["jwt-tokens"])
    _seed(paths, "jwt-tokens", "JWT", tags=["auth"], prereq=["oauth2-flow"])

    index_dir = tmp_path / "vault" / "_index"
    build_indexes(vault=paths, index_dir=index_dir)

    assert (index_dir / "concept_index.json").exists()
    assert (index_dir / "moc_map.json").exists()
    assert (index_dir / "link_graph.json").exists()
    assert (index_dir / "alias_map.json").exists()


def test_build_indexes_concept_index_contains_seeded_concepts(tmp_path: Path):
    paths = VaultPaths(root=tmp_path / "vault")
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()
    _seed(paths, "x", "Concept X", tags=["t"])

    index_dir = tmp_path / "vault" / "_index"
    build_indexes(vault=paths, index_dir=index_dir)

    data = json.loads((index_dir / "concept_index.json").read_text())
    assert "x" in data
    assert data["x"]["title"] == "Concept X"


def test_build_indexes_link_graph_materializes_inverse(tmp_path: Path):
    paths = VaultPaths(root=tmp_path / "vault")
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()
    _seed(paths, "a", "A")
    _seed(paths, "b", "B", prereq=["a"])

    index_dir = tmp_path / "vault" / "_index"
    build_indexes(vault=paths, index_dir=index_dir)

    graph = json.loads((index_dir / "link_graph.json").read_text())
    # b depends on a → a "leads_to" b
    assert "b" in graph["a"]["leads_to"]
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/emit/index_builder.py`**

```python
"""Build the 4 JSON index files from the vault using matter_expert builders."""
from __future__ import annotations

from pathlib import Path

from matter_expert import (
    AliasMap, ConceptIndex, ConceptIndexEntry, ConceptPage,
    LinkGraph, MOCMap, MOCMapEntry, MOCPage, VaultPaths,
)


def build_indexes(vault: VaultPaths, index_dir: Path) -> None:
    """Generate concept_index, moc_map, link_graph, alias_map as JSON files."""
    index_dir.mkdir(parents=True, exist_ok=True)

    # Load concept pages.
    concept_pages: dict[str, ConceptPage] = {}
    if vault.concepts.exists():
        for path in sorted(vault.concepts.glob("*.md")):
            page = ConceptPage.read(path)
            concept_pages[page.name] = page

    # ConceptIndex: concept_name → ConceptIndexEntry
    def _summary(body: str) -> str:
        # First non-heading line, truncated to 120 chars.
        lines = body.splitlines()
        while lines and (not lines[0].strip()
                          or lines[0].lstrip().startswith("#")):
            lines.pop(0)
        return " ".join(lines).strip()[:120]

    concept_index = ConceptIndex({
        name: ConceptIndexEntry(
            path=f"concepts/{name}.md",
            title=page.frontmatter.title,
            summary=_summary(page.body),
            tags=list(page.frontmatter.tags),
            aliases=[],
            moc=[],
        )
        for name, page in concept_pages.items()
    })
    concept_index.write(index_dir / "concept_index.json")

    # MOCMap from vault/MOCs/.
    moc_pages: dict[str, MOCPage] = {}
    if vault.mocs.exists():
        for path in sorted(vault.mocs.glob("*.md")):
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

    # LinkGraph with inverse links materialized.
    link_graph = LinkGraph.build({
        name: page.frontmatter for name, page in concept_pages.items()
    })
    link_graph.write(index_dir / "link_graph.json")

    # AliasMap inverted from concept_index aliases.
    alias_map = AliasMap.build(concept_index)
    alias_map.write(index_dir / "alias_map.json")
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/emit/index_builder.py tests/builder/emit/test_index_builder.py
git commit -m "feat(builder/emit): index_builder generates 4 JSON indexes from vault"
```

---

## Task 3: Runtime Bundler

**Files:**
- Create: `src/builder/emit/runtime_bundler.py`
- Create: `tests/builder/emit/test_runtime_bundler.py`

Copies the `src/runtime/` package into the generated plugin's `skills/<name>/scripts/` directory.

- [ ] **Step 1: Write failing test**

```python
from pathlib import Path

from builder.emit.runtime_bundler import bundle_runtime


def test_bundle_runtime_copies_runtime_package(tmp_path: Path):
    plugin_skill_dir = tmp_path / "skills" / "my-skill"
    bundle_runtime(plugin_skill_dir)

    scripts = plugin_skill_dir / "scripts"
    assert scripts.exists()
    # Some key runtime modules
    assert (scripts / "index.py").exists()
    assert (scripts / "memory.py").exists()
    assert (scripts / "vault_locate.py").exists()
    assert (scripts / "vault_search.py").exists()
    assert (scripts / "vault_traverse.py").exists()
    assert (scripts / "vault_brainstorm.py").exists()
    assert (scripts / "vault_cite.py").exists()
    assert (scripts / "memory_update.py").exists()
    assert (scripts / "memory_inspect.py").exists()


def test_bundle_runtime_does_not_copy_pycache(tmp_path: Path):
    plugin_skill_dir = tmp_path / "skills" / "my-skill"
    bundle_runtime(plugin_skill_dir)

    scripts = plugin_skill_dir / "scripts"
    assert not list(scripts.glob("__pycache__"))
    assert not list(scripts.rglob("*.pyc"))
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/emit/runtime_bundler.py`**

```python
"""Copy the runtime package into the generated plugin's scripts/ directory."""
from __future__ import annotations

import shutil
from pathlib import Path


def _find_runtime_source() -> Path:
    """Locate the `src/runtime/` directory of the current matter_expert checkout."""
    # __file__ is .../matter_expert_skill_creator_skill/src/builder/emit/runtime_bundler.py
    # Climb up to src/ then descend into runtime/.
    here = Path(__file__).resolve()
    src_dir = here.parent.parent.parent  # src/
    runtime = src_dir / "runtime"
    if not runtime.is_dir():
        raise RuntimeError(f"runtime source not found at {runtime}")
    return runtime


def bundle_runtime(plugin_skill_dir: Path) -> Path:
    """Copy runtime/*.py into `<plugin_skill_dir>/scripts/`.

    Returns the scripts directory path. Excludes __pycache__ and *.pyc.
    """
    runtime_src = _find_runtime_source()
    scripts = plugin_skill_dir / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)

    def _ignore(_dir: str, names: list[str]) -> list[str]:
        return [n for n in names if n == "__pycache__" or n.endswith(".pyc")]

    for item in runtime_src.iterdir():
        if item.name in {"__pycache__"}:
            continue
        if item.is_dir():
            shutil.copytree(
                item, scripts / item.name,
                dirs_exist_ok=True, ignore=_ignore,
            )
        else:
            shutil.copy2(item, scripts / item.name)
    return scripts
```

- [ ] **Step 4: Run → 2 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/emit/runtime_bundler.py tests/builder/emit/test_runtime_bundler.py
git commit -m "feat(builder/emit): runtime_bundler copies stdlib-only scripts into plugin"
```

---

## Task 4: Memory Initializer

**Files:**
- Create: `src/builder/emit/memory_initializer.py`
- Create: `tests/builder/emit/test_memory_initializer.py`

Writes initial mutable memory files (query_cache, path_frequency seeded from link graph, user_preferences defaults, learned_aliases empty, session_log empty).

- [ ] **Step 1: Write failing test**

```python
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
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/emit/memory_initializer.py`**

```python
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
                freq[name]["co_accessed"][neighbor] = (
                    freq[name]["co_accessed"].get(neighbor, 0) + 1
                )
                # Symmetric seeding so memory_update finds co-accesses immediately.
                freq[neighbor]["co_accessed"][name] = (
                    freq[neighbor]["co_accessed"].get(name, 0) + 1
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
```

- [ ] **Step 4: Run → 5 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/emit/memory_initializer.py tests/builder/emit/test_memory_initializer.py
git commit -m "feat(builder/emit): initialize_memory seeds path_frequency from link graph"
```

---

## Task 5: SKILL.md Generator

**Files:**
- Create: `src/builder/emit/prompts.py`
- Create: `src/builder/emit/skill_md.py`
- Create: `tests/builder/emit/conftest.py`
- Create: `tests/builder/emit/test_skill_md.py`

The trigger description is LLM-generated (Sonnet, high effort) so the description is "pushy" enough to trigger reliably per the skill-creator guidance.

- [ ] **Step 1: Write `src/builder/emit/prompts.py`**

```python
"""Prompts for the Emit phase."""

TRIGGER_DESC_SYSTEM = (
    "You write Claude Code skill 'description' fields that trigger reliably. "
    "Skills tend to under-trigger by default, so descriptions must be slightly "
    "pushy: include both what the skill does AND specific contexts when to use "
    "it. The output is one paragraph, plain text, no markdown. Maximum ~120 words."
)


def trigger_desc_prompt(skill_name: str, dominant_topics: list[str]) -> str:
    topics = ", ".join(dominant_topics) if dominant_topics else "various concepts"
    return (
        f"Generate a triggering description for the skill `{skill_name}`. "
        f"The skill answers questions and supports brainstorming about: {topics}. "
        f"Include concrete example phrases that should trigger the skill (e.g., "
        f"'questions about X', 'when the user wants to understand Y'). "
        f"Return the description as plain text, one paragraph."
    )
```

- [ ] **Step 2: Write `tests/builder/emit/conftest.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from builder.ingest.protocols import AgentResponse


@dataclass
class CannedAgent:
    canned_text: str = "MOCK_TRIGGER_DESCRIPTION"
    canned_input_tokens: int = 100
    canned_output_tokens: int = 50
    calls: list[dict] = field(default_factory=list)

    def call(self, prompt, *, model="haiku", images=None) -> AgentResponse:
        self.calls.append({"prompt": prompt, "model": model})
        return AgentResponse(
            text=self.canned_text,
            input_tokens=self.canned_input_tokens,
            output_tokens=self.canned_output_tokens,
        )


@pytest.fixture
def canned_agent() -> CannedAgent:
    return CannedAgent()
```

- [ ] **Step 3: Write failing test `tests/builder/emit/test_skill_md.py`**

```python
from pathlib import Path

from builder.emit.skill_md import generate_skill_md, SkillMdMeta


def test_generate_skill_md_writes_file(tmp_path: Path, canned_agent):
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)

    meta = SkillMdMeta(
        skill_name="my-skill",
        dominant_topics=["oauth2", "jwt"],
    )
    path = generate_skill_md(skill_dir=skill_dir, meta=meta, agent=canned_agent)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert "name: my-skill" in content
    assert "description:" in content


def test_skill_md_uses_sonnet(tmp_path: Path, canned_agent):
    skill_dir = tmp_path / "skills" / "x"
    skill_dir.mkdir(parents=True)
    generate_skill_md(
        skill_dir=skill_dir,
        meta=SkillMdMeta(skill_name="x", dominant_topics=[]),
        agent=canned_agent,
    )
    assert canned_agent.calls[-1]["model"] == "sonnet"


def test_skill_md_includes_workflow_sections(tmp_path: Path, canned_agent):
    """SKILL.md must document Q&A and brainstorming workflows + citation format."""
    skill_dir = tmp_path / "skills" / "x"
    skill_dir.mkdir(parents=True)
    path = generate_skill_md(
        skill_dir=skill_dir,
        meta=SkillMdMeta(skill_name="x", dominant_topics=["auth"]),
        agent=canned_agent,
    )
    content = path.read_text(encoding="utf-8")
    assert "Q&A" in content or "answer" in content.lower()
    assert "brainstorm" in content.lower()
    assert "citation" in content.lower() or "source" in content.lower()
```

- [ ] **Step 4: Run → fail**

- [ ] **Step 5: Implement `src/builder/emit/skill_md.py`**

```python
"""Generate the SKILL.md for the expert skill plugin."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from builder.emit.prompts import trigger_desc_prompt
from builder.ingest.protocols import AgentCaller


@dataclass(frozen=True)
class SkillMdMeta:
    skill_name: str
    dominant_topics: list[str]


SKILL_MD_TEMPLATE = """\
---
name: {name}
description: {description}
---

# {title}

This skill answers questions and supports brainstorming based on the vault
of curated knowledge bundled in this plugin.

## When the user asks a question (Q&A mode)

1. Run `scripts/vault_locate.py` with the user's query to find entry points.
2. If needed, run `scripts/vault_search.py` for keyword search.
3. Run `scripts/vault_traverse.py` to expand the context via typed links.
4. Read the identified concept pages from `vault/concepts/`.
5. Synthesize the answer with explicit citations using the citation format below.
6. After answering, run `scripts/memory_update.py` to record what was used.

## When the user wants to brainstorm

1. Detect brainstorming intent (hypothetical, "what if", "options for", etc.).
2. Run `scripts/vault_brainstorm.py` for the topic — get a hypothesis scaffold.
3. Present hypotheses with confidence levels, sources, assumptions,
   and falsification criteria.
4. Make vault gaps (🔍) and source contradictions (⚠️) explicit.
5. Mark world-knowledge additions with 💡.
6. End with a forschende Folgefrage.

## Citation format

Cite vault concepts as `[[concept-name]]` and the underlying source as
`Source.pdf §X.Y`. Always show citations alongside the claim they support.
"""


def generate_skill_md(
    skill_dir: Path,
    meta: SkillMdMeta,
    agent: AgentCaller,
) -> Path:
    """Generate the SKILL.md for an expert skill and write it to disk."""
    description = _generate_description(meta, agent)
    content = SKILL_MD_TEMPLATE.format(
        name=meta.skill_name,
        description=description.replace("\n", " ").strip(),
        title=meta.skill_name.replace("-", " ").title(),
    )
    path = skill_dir / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _generate_description(meta: SkillMdMeta, agent: AgentCaller) -> str:
    prompt = trigger_desc_prompt(
        skill_name=meta.skill_name,
        dominant_topics=list(meta.dominant_topics),
    )
    response = agent.call(prompt, model="sonnet")
    return response.text.strip()
```

- [ ] **Step 6: Run → 3 pass**

- [ ] **Step 7: Commit**

```bash
git add src/builder/emit/prompts.py src/builder/emit/skill_md.py \
        tests/builder/emit/conftest.py tests/builder/emit/test_skill_md.py
git commit -m "feat(builder/emit): SKILL.md generator with LLM-written trigger description"
```

---

## Task 6: README Generator

**Files:**
- Create: `src/builder/emit/readme.py`
- Create: `tests/builder/emit/test_readme.py`

- [ ] **Step 1: Write failing test**

```python
from pathlib import Path

from builder.emit.readme import generate_readme, ReadmeMeta


def test_generate_readme_writes_file(tmp_path: Path):
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()

    meta = ReadmeMeta(
        plugin_name="my-skill", version="0.1.0",
        description="Expert on OAuth.",
        concept_count=42, moc_count=5,
    )
    path = generate_readme(plugin_root=plugin_root, meta=meta)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "my-skill" in content
    assert "42" in content
    assert "OAuth" in content
    assert "install" in content.lower()
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/emit/readme.py`**

```python
"""Generate the README.md for the produced expert-skill plugin."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReadmeMeta:
    plugin_name: str
    version: str
    description: str
    concept_count: int
    moc_count: int


README_TEMPLATE = """\
# {plugin_name}

**Version:** {version}

{description}

## What's bundled

- **{concept_count} concepts** in `skills/{plugin_name}/vault/concepts/`
- **{moc_count} Maps of Content** in `skills/{plugin_name}/vault/MOCs/`
- Pre-built JSON indexes in `skills/{plugin_name}/_index/`
- Stdlib-only runtime scripts in `skills/{plugin_name}/scripts/`

## Install

Drop this plugin into your Claude Code plugin directory:

```
~/.claude/plugins/{plugin_name}/
```

Restart Claude Code and the skill auto-loads. Ask any question on the
covered topics and the skill triggers.

## How it works

The skill uses a four-layer retrieval pipeline (locate → search → traverse →
synthesize) backed by the bundled vault. Citations are sourced from the
original documents recorded in each concept's frontmatter.
"""


def generate_readme(plugin_root: Path, meta: ReadmeMeta) -> Path:
    plugin_root.mkdir(parents=True, exist_ok=True)
    path = plugin_root / "README.md"
    path.write_text(
        README_TEMPLATE.format(
            plugin_name=meta.plugin_name,
            version=meta.version,
            description=meta.description,
            concept_count=meta.concept_count,
            moc_count=meta.moc_count,
        ),
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 4: Run → 1 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/emit/readme.py tests/builder/emit/test_readme.py
git commit -m "feat(builder/emit): README generator for produced plugins"
```

---

## Task 7: Emit Orchestrator + Public API

**Files:**
- Create: `src/builder/emit/orchestrator.py`
- Create: `tests/builder/emit/test_orchestrator.py`
- Modify: `src/builder/emit/__init__.py`
- Create: `tests/builder/emit/test_public_api.py`

The orchestrator wires it all together: copies the vault into the plugin's `skills/<name>/vault/`, builds indexes, bundles runtime, writes SKILL.md, initializes memory, writes plugin.json + README.

- [ ] **Step 1: Write failing test `tests/builder/emit/test_orchestrator.py`**

```python
import json
from datetime import date
from pathlib import Path

from builder.emit.orchestrator import EmitOrchestrator, EmitConfig
from builder.phases import Phase
from builder.pipeline import Pipeline
from matter_expert import (
    ConceptFrontmatter, ConceptPage, MOCFrontmatter, MOCPage,
    Source, SourceFrontmatter, SourcePage, VaultPaths,
)


def _build_vault(root: Path) -> VaultPaths:
    paths = VaultPaths(root=root)
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()

    fm = ConceptFrontmatter(
        title="OAuth2",
        sources=[Source(file="handbook.md", sections=["3.1"])],
        tags=["auth"], created=date(2026, 5, 10),
    )
    ConceptPage(frontmatter=fm, body="# OAuth2\n\nbody",
                path=paths.concept_for("oauth2-flow")).write()

    moc = MOCPage(
        frontmatter=MOCFrontmatter(
            title="Auth", children=["oauth2-flow"],
            parents=[], related_mocs=[], created=date(2026, 5, 10),
        ),
        body="# Auth MOC\n", path=paths.mocs / "auth.md",
    )
    moc.write()

    src = SourcePage(
        frontmatter=SourceFrontmatter(
            title="Handbook", original_file="handbook.pdf",
            original_format="pdf", page_count=1,
            extraction_method="text", language_detected="en",
            ingested=date(2026, 5, 10),
        ),
        body="Handbook body", path=paths.source_for("handbook"),
    )
    src.write()
    return paths


def test_orchestrator_produces_full_plugin_structure(
    tmp_path: Path, canned_agent, run_dir,
):
    vault_paths = _build_vault(tmp_path / "vault")
    plugin_root = tmp_path / "out_plugin"

    cfg = EmitConfig(
        plugin_name="oauth-expert",
        plugin_version="0.1.0",
        plugin_description="Expert on OAuth and JWT.",
        author="builder",
    )
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = EmitOrchestrator(agent=canned_agent, config=cfg)

    orch.emit(vault=vault_paths, plugin_root=plugin_root, pipeline=pipeline)

    # Top-level structure.
    assert (plugin_root / ".claude-plugin" / "plugin.json").exists()
    assert (plugin_root / "README.md").exists()
    # Skill directory
    skill = plugin_root / "skills" / "oauth-expert"
    assert (skill / "SKILL.md").exists()
    # Bundled vault
    assert (skill / "vault" / "concepts" / "oauth2-flow.md").exists()
    assert (skill / "vault" / "MOCs" / "auth.md").exists()
    assert (skill / "vault" / "sources" / "handbook.md").exists()
    # Index files
    assert (skill / "_index" / "concept_index.json").exists()
    assert (skill / "_index" / "moc_map.json").exists()
    assert (skill / "_index" / "link_graph.json").exists()
    assert (skill / "_index" / "alias_map.json").exists()
    # Bundled runtime
    assert (skill / "scripts" / "vault_locate.py").exists()
    assert (skill / "scripts" / "vault_brainstorm.py").exists()
    # Initial memory
    assert (skill / "memory" / "query_cache.json").exists()
    assert (skill / "memory" / "user_preferences.json").exists()


def test_orchestrator_marks_phase_complete_in_pipeline(
    tmp_path: Path, canned_agent, run_dir,
):
    vault_paths = _build_vault(tmp_path / "vault")
    plugin_root = tmp_path / "out_plugin"
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = EmitOrchestrator(
        agent=canned_agent,
        config=EmitConfig(plugin_name="x", plugin_version="0.1.0",
                            plugin_description="d", author="a"),
    )
    orch.emit(vault=vault_paths, plugin_root=plugin_root, pipeline=pipeline)
    assert pipeline.is_phase_complete(Phase.EMIT)


def test_orchestrator_records_cost_for_skill_md(
    tmp_path: Path, canned_agent, run_dir,
):
    """SKILL.md trigger description is LLM-generated → cost > 0."""
    vault_paths = _build_vault(tmp_path / "vault")
    plugin_root = tmp_path / "out_plugin"
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = EmitOrchestrator(
        agent=canned_agent,
        config=EmitConfig(plugin_name="x", plugin_version="0.1.0",
                            plugin_description="d", author="a"),
    )
    orch.emit(vault=vault_paths, plugin_root=plugin_root, pipeline=pipeline)
    assert pipeline.state.cost_tracker["per_phase"].get("emit", 0) > 0
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/emit/orchestrator.py`**

```python
"""Emit orchestrator — produces the final installable plugin."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from builder.cost_tracker import TokenUsage, estimate_cost
from builder.emit.index_builder import build_indexes
from builder.emit.memory_initializer import initialize_memory
from builder.emit.plugin_metadata import PluginMetadata, write_plugin_json
from builder.emit.readme import ReadmeMeta, generate_readme
from builder.emit.runtime_bundler import bundle_runtime
from builder.emit.skill_md import SkillMdMeta, generate_skill_md
from builder.ingest.protocols import AgentCaller
from builder.phases import Model, Phase
from builder.pipeline import Pipeline
from matter_expert import VaultPaths


@dataclass(frozen=True)
class EmitConfig:
    plugin_name: str
    plugin_version: str
    plugin_description: str
    author: str


class _CostTrackingAgent:
    def __init__(self, inner: AgentCaller, pipeline: Pipeline) -> None:
        self._inner = inner
        self._pipeline = pipeline

    def call(self, prompt, *, model="haiku", images=None):
        resp = self._inner.call(prompt, model=model, images=images)
        try:
            model_enum = Model(model)
        except ValueError:
            model_enum = Model.SONNET
        usage = TokenUsage(
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cached_input_tokens=getattr(resp, "cached_input_tokens", 0),
        )
        self._pipeline.record_cost(Phase.EMIT,
                                    estimate_cost(model_enum, usage))
        return resp


class EmitOrchestrator:
    def __init__(self, agent: AgentCaller, config: EmitConfig) -> None:
        self._agent = agent
        self._config = config

    def emit(self, vault: VaultPaths, plugin_root: Path,
             pipeline: Pipeline) -> None:
        pipeline.mark_phase_started(Phase.EMIT)
        tracked = _CostTrackingAgent(self._agent, pipeline)

        cfg = self._config
        skill_dir = plugin_root / "skills" / cfg.plugin_name
        bundled_vault = skill_dir / "vault"
        index_dir = skill_dir / "_index"
        memory_dir = skill_dir / "memory"

        # 1. Copy the vault into the plugin.
        self._copy_vault(vault, bundled_vault)

        # 2. Build the 4 indexes from the bundled vault.
        bundled_paths = VaultPaths(root=bundled_vault)
        build_indexes(vault=bundled_paths, index_dir=index_dir)

        # 3. Bundle the runtime scripts.
        bundle_runtime(plugin_skill_dir=skill_dir)

        # 4. Generate SKILL.md (LLM call → cost recorded via tracked agent).
        topics = self._extract_dominant_topics(bundled_paths)
        generate_skill_md(
            skill_dir=skill_dir,
            meta=SkillMdMeta(skill_name=cfg.plugin_name, dominant_topics=topics),
            agent=tracked,
        )

        # 5. Initialize memory.
        link_graph = json.loads(
            (index_dir / "link_graph.json").read_text(encoding="utf-8")
        )
        initialize_memory(memory_dir=memory_dir, link_graph=link_graph)

        # 6. Write plugin.json.
        write_plugin_json(
            PluginMetadata(
                name=cfg.plugin_name, version=cfg.plugin_version,
                description=cfg.plugin_description, author=cfg.author,
            ),
            plugin_root=plugin_root,
        )

        # 7. Write README.
        concept_count = (
            len(list(bundled_paths.concepts.glob("*.md")))
            if bundled_paths.concepts.exists() else 0
        )
        moc_count = (
            len(list(bundled_paths.mocs.glob("*.md")))
            if bundled_paths.mocs.exists() else 0
        )
        generate_readme(
            plugin_root=plugin_root,
            meta=ReadmeMeta(
                plugin_name=cfg.plugin_name, version=cfg.plugin_version,
                description=cfg.plugin_description,
                concept_count=concept_count, moc_count=moc_count,
            ),
        )

        pipeline.mark_phase_completed(Phase.EMIT)

    def _copy_vault(self, vault: VaultPaths, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        for subdir in ("concepts", "MOCs", "sources"):
            src = vault.root / subdir
            if src.exists():
                shutil.copytree(src, dest / subdir, dirs_exist_ok=True)

    def _extract_dominant_topics(self, vault: VaultPaths) -> list[str]:
        """Return the top tags across all concepts (most frequent first)."""
        from collections import Counter
        from matter_expert import ConceptPage
        counts: Counter[str] = Counter()
        if vault.concepts.exists():
            for path in vault.concepts.glob("*.md"):
                page = ConceptPage.read(path)
                counts.update(page.frontmatter.tags)
        return [tag for tag, _ in counts.most_common(10)]
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Update `src/builder/emit/__init__.py`**

```python
"""Emit phase — generates the installable expert-skill plugin."""
from builder.emit.plugin_metadata import PluginMetadata, write_plugin_json
from builder.emit.index_builder import build_indexes
from builder.emit.runtime_bundler import bundle_runtime
from builder.emit.memory_initializer import (
    DEFAULT_USER_PREFERENCES, initialize_memory,
)
from builder.emit.skill_md import SkillMdMeta, generate_skill_md
from builder.emit.readme import ReadmeMeta, generate_readme
from builder.emit.orchestrator import EmitConfig, EmitOrchestrator

__all__ = [
    "PluginMetadata", "write_plugin_json",
    "build_indexes",
    "bundle_runtime",
    "DEFAULT_USER_PREFERENCES", "initialize_memory",
    "SkillMdMeta", "generate_skill_md",
    "ReadmeMeta", "generate_readme",
    "EmitConfig", "EmitOrchestrator",
]
```

- [ ] **Step 6: Write `tests/builder/emit/test_public_api.py`**

```python
def test_emit_public_api():
    from builder.emit import (
        PluginMetadata, write_plugin_json,
        build_indexes,
        bundle_runtime,
        DEFAULT_USER_PREFERENCES, initialize_memory,
        SkillMdMeta, generate_skill_md,
        ReadmeMeta, generate_readme,
        EmitConfig, EmitOrchestrator,
    )
    assert callable(generate_skill_md)
    assert callable(generate_readme)
```

- [ ] **Step 7: Run all tests, commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pytest
git add src/builder/emit/orchestrator.py src/builder/emit/__init__.py \
        tests/builder/emit/test_orchestrator.py tests/builder/emit/test_public_api.py
git commit -m "feat(builder/emit): orchestrator + public API exports"
```
