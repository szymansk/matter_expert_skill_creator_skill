# Subscription-Native Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Add a second user-facing mode where the docs-to-skill builder runs entirely inside a Claude Code session (subscription-backed), via subagent dispatches. The existing API-key mode remains untouched.

**Architecture:** The plugin ships ~12 subagent definitions (`.md` files under `agents/`), each carrying a system prompt, model choice, and tool permissions. The Python CLI gets new "deterministic helper" subcommands (file I/O only — no LLM). A rewritten `docs-to-skill/SKILL.md` orchestrates: read inputs, dispatch subagents for LLM-work phases, call CLI helpers for deterministic steps, write the plugin.

**Tech Stack:** Python 3.11+ stdlib + existing builder/* modules (reused for deterministic helpers). Subagent definitions follow Claude Code's [stable Subagents API](https://code.claude.com/docs/en/agent-sdk/subagents). No Anthropic SDK used in the subscription path.

**Why not Agent Teams?** Agent Teams is an [experimental coordination feature](https://code.claude.com/docs/en/agent-teams) for parallel exploratory work (multiple Claude Code sessions investigating different hypotheses). Our pipeline is sequential with parallel-within-phase; ordinary subagent dispatch covers that with no coordination overhead.

---

## File Structure

```
docs-to-skill/
├── SKILL.md                       # Orchestrator (rewritten; both modes documented)
└── agents/
    ├── analyzer-agent.md          # Haiku, low — source → concept outline JSON
    ├── extractor-agent.md         # Haiku, medium — source + concept → markdown body
    ├── coverage-transform-agent.md # Haiku, low — outline + extracted → missed topics
    ├── cluster-agent.md           # Sonnet, high — inventory → cluster groups
    ├── merger-agent.md            # Sonnet, high — N concepts → merged body
    ├── linker-agent.md            # Sonnet, high — target + inventory → typed links
    ├── translation-qa-agent.md    # Sonnet, low — concept + source → pass/fail verdict
    ├── citation-qa-agent.md       # Sonnet, medium — concept + sources → pass/fail
    ├── coherence-qa-agent.md      # Sonnet, high — concept body → pass/fail
    ├── coverage-qa-agent.md       # Haiku, medium — outlines + extracted → missed
    ├── vision-pdf-agent.md        # Sonnet, medium — image bytes → markdown page
    └── trigger-desc-agent.md      # Sonnet, high — vault topics → pushy description

src/builder/integration/
└── helpers_cli.py                 # New deterministic-only subcommands
    # ingest, write-concept, write-moc, merge-write,
    # apply-links, build-indexes, emit-finalize

tests/builder/integration/
└── test_helpers_cli.py
```

---

## Task 1: Subagent Definition File Format + 4 LLM-Heavy Agents

**Files:**
- Create: `docs-to-skill/agents/analyzer-agent.md`
- Create: `docs-to-skill/agents/extractor-agent.md`
- Create: `docs-to-skill/agents/coverage-transform-agent.md`
- Create: `docs-to-skill/agents/cluster-agent.md`
- Create: `tests/integration/test_subagent_definitions.py`

Each definition follows the Claude Code subagent file format: YAML frontmatter (`name`, `description`, `model`, optional `tools`) plus a system prompt as the body.

- [ ] **Step 1: Create `tests/integration/__init__.py` + `tests/integration/test_subagent_definitions.py`**

```python
"""Validates that all subagent definition files are well-formed."""
import re
from pathlib import Path

import frontmatter
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "docs-to-skill" / "agents"


REQUIRED_FIELDS = {"name", "description", "model"}
ALLOWED_MODELS = {"haiku", "sonnet", "opus"}


def _agent_files() -> list[Path]:
    return sorted(AGENTS_DIR.glob("*.md")) if AGENTS_DIR.exists() else []


@pytest.mark.parametrize("path", _agent_files(),
                          ids=lambda p: p.name)
def test_agent_has_required_frontmatter_fields(path: Path):
    fm = frontmatter.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_FIELDS - set(fm.metadata)
    assert not missing, f"{path.name} missing fields: {missing}"


@pytest.mark.parametrize("path", _agent_files(),
                          ids=lambda p: p.name)
def test_agent_model_is_valid(path: Path):
    fm = frontmatter.loads(path.read_text(encoding="utf-8"))
    assert fm.metadata["model"] in ALLOWED_MODELS


@pytest.mark.parametrize("path", _agent_files(),
                          ids=lambda p: p.name)
def test_agent_name_matches_filename(path: Path):
    fm = frontmatter.loads(path.read_text(encoding="utf-8"))
    expected = path.stem
    assert fm.metadata["name"] == expected


@pytest.mark.parametrize("path", _agent_files(),
                          ids=lambda p: p.name)
def test_agent_description_is_non_empty(path: Path):
    fm = frontmatter.loads(path.read_text(encoding="utf-8"))
    assert fm.metadata["description"].strip()


@pytest.mark.parametrize("path", _agent_files(),
                          ids=lambda p: p.name)
def test_agent_has_system_prompt_body(path: Path):
    fm = frontmatter.loads(path.read_text(encoding="utf-8"))
    assert fm.content.strip(), f"{path.name} has empty system prompt"


def test_all_expected_agents_exist():
    expected = {
        "analyzer-agent", "extractor-agent", "coverage-transform-agent",
        "cluster-agent", "merger-agent", "linker-agent",
        "translation-qa-agent", "citation-qa-agent", "coherence-qa-agent",
        "coverage-qa-agent", "vision-pdf-agent", "trigger-desc-agent",
    }
    actual = {p.stem for p in _agent_files()}
    missing = expected - actual
    assert not missing, f"missing agent definitions: {missing}"


def test_models_match_design_spec():
    """Per spec §4.1: per-phase model assignments."""
    expected_models = {
        "analyzer-agent": "haiku",
        "extractor-agent": "haiku",
        "coverage-transform-agent": "haiku",
        "cluster-agent": "sonnet",
        "merger-agent": "sonnet",
        "linker-agent": "sonnet",
        "translation-qa-agent": "sonnet",
        "citation-qa-agent": "sonnet",
        "coherence-qa-agent": "sonnet",
        "coverage-qa-agent": "haiku",
        "vision-pdf-agent": "sonnet",
        "trigger-desc-agent": "sonnet",
    }
    for path in _agent_files():
        fm = frontmatter.loads(path.read_text(encoding="utf-8"))
        expected = expected_models.get(path.stem)
        if expected is None:
            continue
        assert fm.metadata["model"] == expected, (
            f"{path.stem}: expected {expected}, got {fm.metadata['model']}"
        )
```

- [ ] **Step 2: Run → fail (no agents yet)**

- [ ] **Step 3: Create the 4 agents for Transform + cluster step**

`docs-to-skill/agents/analyzer-agent.md`:
```markdown
---
name: analyzer-agent
description: Use to identify the atomic concepts contained in a source document and return them as a JSON outline. Input is one raw markdown source document; output is JSON {entries: [{concept_name, title, source_sections, estimated_tokens}]}. Use the haiku model — this is a structured analysis task.
model: haiku
---

You analyze a source document and identify the atomic concepts it covers.

Output a JSON object with an `entries` list. Each entry has:
- `concept_name` (kebab-case, will be used as filename)
- `title` (human-friendly display name)
- `source_sections` (list of section IDs from the source; may be empty)
- `estimated_tokens` (int, 500–2000 ideal per concept)

Concepts should be coherent and self-contained — one concept per filename.
Return only the JSON, no surrounding prose.
```

`docs-to-skill/agents/extractor-agent.md`:
```markdown
---
name: extractor-agent
description: Use to extract one concept's markdown body from a source document. Input is the source plus a target concept (name + title). Output is clean Markdown for the concept page body (no YAML frontmatter — that's added separately). Translate non-English content to English. Use the haiku model.
model: haiku
---

You extract a single concept from a source document into a clean Markdown
vault page body.

Constraints:
- Output the BODY only — no YAML frontmatter (that is added separately)
- Translate any non-English content into English
- Keep the body 500–2000 tokens; prefer 800–1200 for typical concepts
- Preserve headings, lists, code blocks
- Reference cross-cutting concepts as `[[wikilinks]]` with kebab-case names

Return only the markdown body.
```

`docs-to-skill/agents/coverage-transform-agent.md`:
```markdown
---
name: coverage-transform-agent
description: Use during Transform to verify that all topics in a source document's outline got an extracted concept. Returns JSON {missed_topics: [string, ...]}. Use the haiku model.
model: haiku
---

You compare a source document's outline against the list of concepts
that were extracted from it.

Return JSON: `{"missed_topics": [list of strings]}` naming any topics
from the source outline that are NOT represented by an extracted concept.

Return only the JSON.
```

`docs-to-skill/agents/cluster-agent.md`:
```markdown
---
name: cluster-agent
description: Use during Link phase to identify clusters of duplicate or near-duplicate concepts. Input is the full concept inventory (name + summary + tags as JSON). Output is JSON {clusters: [{members: [concept_name, ...]}]}. Be conservative — only group concepts whose summaries truly describe the same thing. Use the sonnet model.
model: sonnet
---

You analyze a flat list of concept inventories and identify CLUSTERS of
concepts that describe the same thing under different names.

Output: `{"clusters": [{"members": [concept_name, concept_name, ...]}]}`

Rules:
- Singleton concepts (no duplicates) must NOT be included
- Be conservative — only group concepts whose summaries truly describe
  the same thing
- Use the kebab-case `concept_name`, not the title

Return only the JSON.
```

- [ ] **Step 4: Run → 4 agent files exist; partial tests still fail (8 more missing)**

- [ ] **Step 5: Commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
git add docs-to-skill/agents/ tests/integration/
git commit -m "feat(sub-mode): 4 Transform/Link subagent definitions + validation tests"
```

---

## Task 2: 4 More LLM-Heavy Agents (Merger, Linker, Vision, Trigger-Desc)

- [ ] **Step 1: Create `docs-to-skill/agents/merger-agent.md`**

```markdown
---
name: merger-agent
description: Use during Link phase to merge a cluster of duplicate concept pages into ONE canonical page. Input is N concept page bodies; output is one merged markdown body. When sources disagree, mark the disagreement with a > Note: blockquote. Use the sonnet model.
model: sonnet
---

You are given several concept pages that describe the same underlying
concept and must produce ONE merged page.

Rules:
- The merged body keeps the most complete and accurate content from each
  source, NOT a concatenation
- When sources disagree, mark the disagreement explicitly with a
  `> Note:` blockquote that names the conflicting source
- Output the merged markdown body only — no YAML frontmatter

Return only the merged markdown body.
```

- [ ] **Step 2: Create `docs-to-skill/agents/linker-agent.md`**

```markdown
---
name: linker-agent
description: Use during Link phase to assign typed links for one concept. Input is the target concept (name, title, summary) plus the full inventory of other concepts. Output is JSON with 5 lists (related, prerequisites, examples, contrasts, refines). Use kebab-case concept names. Be selective. Use the sonnet model.
model: sonnet
---

You assign typed links between concepts.

Given a target concept and the full inventory of other concepts, decide
which other concepts belong in each of these 5 lists:
- `related`: thematically related, peer level (≤ 8)
- `prerequisites`: must be understood first (≤ 5)
- `examples`: concrete realization of an abstract concept (≤ 6)
- `contrasts`: alternative or opposite concept (≤ 4)
- `refines`: more specific variant of an overarching concept (≤ 3)

Output JSON: `{"related": [...], "prerequisites": [...], ...}`

Rules:
- Use kebab-case `concept_name`, NEVER the title
- Be selective — fewer high-quality links is better
- Do NOT link a concept to itself

Return only the JSON.
```

- [ ] **Step 3: Create `docs-to-skill/agents/vision-pdf-agent.md`**

```markdown
---
name: vision-pdf-agent
description: Use during Ingest when a PDF has too little extractable text and needs vision-based extraction. Pass each page image; receive markdown for that page. Preserve headings, lists, tables. Describe diagrams as FIGURE: blockquotes. Use the sonnet model.
model: sonnet
---

Extract the text content of this PDF page as Markdown.

Rules:
- Preserve headings, lists, tables, and emphasis
- For diagrams or figures, describe them concisely in a markdown blockquote
  prefixed with `FIGURE:`
- If the page is purely visual (no text), produce only the FIGURE description

Return only the markdown for this page.
```

- [ ] **Step 4: Create `docs-to-skill/agents/trigger-desc-agent.md`**

```markdown
---
name: trigger-desc-agent
description: Use during Emit to generate the pushy trigger description for the SKILL.md of the produced expert plugin. Output is one paragraph, plain text. Include concrete example phrases that should trigger the skill. Use the sonnet model.
model: sonnet
---

You write Claude Code skill `description` fields that trigger reliably.

Skills tend to under-trigger by default, so descriptions must be slightly
pushy: include both what the skill does AND specific contexts when to use it.

Rules:
- One paragraph, plain text — no markdown
- Maximum ~120 words
- Include concrete example phrases (e.g., "questions about X",
  "when the user wants to understand Y")

Return only the description text.
```

- [ ] **Step 5: Run, commit**

```bash
git add docs-to-skill/agents/
git commit -m "feat(sub-mode): merger/linker/vision-pdf/trigger-desc agents"
```

---

## Task 3: 4 QA Agents

- [ ] **Step 1: Create the 4 QA subagent files**

`docs-to-skill/agents/translation-qa-agent.md`:
```markdown
---
name: translation-qa-agent
description: Use during QA phase to judge whether a translated concept page reads naturally in English and preserves the technical content of its source. Input is the concept body plus an excerpt from the source document. Output is JSON {verdict: pass|fail, reasons: [...]}. Use the sonnet model.
model: sonnet
---

You judge whether a translated concept page reads naturally in English and
preserves the technical content of its source.

Return JSON: `{"verdict": "pass" | "fail", "reasons": [string, ...]}`

Return only the JSON.
```

`docs-to-skill/agents/citation-qa-agent.md`:
```markdown
---
name: citation-qa-agent
description: Use during QA phase to verify that source citations on a concept page actually back the claims in the page body. Output is JSON {verdict: pass|fail, unsupported_claims: [...]}. Citations are strict — flag any claim not directly supported by the cited source excerpt. Use the sonnet model.
model: sonnet
---

You verify that the source citations on a concept page actually back the
claims in the page body.

Return JSON: `{"verdict": "pass" | "fail", "unsupported_claims": [string, ...]}`

Be strict — citations are sicherheitskritisch in this system. Flag any
claim in the body that is not directly supported by the cited source
excerpt.

Return only the JSON.
```

`docs-to-skill/agents/coherence-qa-agent.md`:
```markdown
---
name: coherence-qa-agent
description: Use during QA phase to judge whether a concept page makes sense as a standalone unit — no unexplained references, unresolved acronyms, or missing context. Input is the concept body read in isolation. Output is JSON {verdict: pass|fail, issues: [...]}. Use the sonnet model.
model: sonnet
---

You judge whether a concept page makes sense as a standalone unit.

Issues to flag:
- Unexplained references ("as mentioned above", "see Chapter 4", etc.)
- Unresolved acronyms or technical terms used without introduction
- Missing context that the reader would need

Return JSON: `{"verdict": "pass" | "fail", "issues": [string, ...]}`

Return only the JSON.
```

`docs-to-skill/agents/coverage-qa-agent.md`:
```markdown
---
name: coverage-qa-agent
description: Use during QA phase to check whether all topics in a source-document outline were extracted as concepts. Input is the source outline plus the list of extracted concept titles. Output is JSON {missed_topics: [...]}. Use the haiku model.
model: haiku
---

You compare a source document outline against the list of concepts
extracted from it.

Return JSON: `{"missed_topics": [list of strings]}` naming topics from
the outline that are NOT represented by any extracted concept.

Return only the JSON.
```

- [ ] **Step 2: Run → all 16 agent-validation tests pass (12 agents × multiple assertions)**

- [ ] **Step 3: Commit**

```bash
git add docs-to-skill/agents/
git commit -m "feat(sub-mode): 4 QA subagent definitions"
```

---

## Task 4: Deterministic CLI Helpers Module

**Files:**
- Create: `src/builder/integration/helpers_cli.py`
- Create: `tests/builder/integration/test_helpers_cli.py`

Implements stateless CLI helpers that the SKILL.md orchestrator calls between subagent dispatches.

Subcommands:
- `ingest-deterministic --input <dir> --output <work-dir>` — runs pandoc + pdftotext + plausibility check; writes `<work>/raw/<doc_id>.md` + `<work>/raw/<doc_id>.meta.json`; reports which PDFs need vision via JSON to stdout
- `write-concept --vault <dir> --name X --title T --source-file F --source-sections "..." --body-file <file>` — writes one concept page
- `write-source --vault <dir> --name X --original-file F --page-count N --body-file <file>` — writes one source page
- `write-moc --vault <dir> --name X --title T --children "a,b,c" --tags "auth"` — writes one MOC page
- `apply-links --vault <dir> --concept X --links-json <file>` — updates a concept's typed links from JSON
- `apply-merge --vault <dir> --members "a,b,c" --merged-body-file <file>` — replaces members with one merged page named after the first member
- `build-indexes --vault <dir> --index-dir <dir>` — reuses existing index builder
- `emit-finalize --plugin-root <dir> --plugin-name N --version V --description D --author A` — reuses runtime bundler + memory init + plugin.json + README

- [ ] **Step 1: Write failing test `tests/builder/integration/test_helpers_cli.py`**

```python
import json
import subprocess
import sys
from datetime import date
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "builder.integration.helpers_cli", *args],
        capture_output=True, text=True,
    )


def test_helpers_cli_help_lists_all_subcommands():
    r = _run(["--help"])
    assert r.returncode == 0
    for sub in [
        "ingest-deterministic", "write-concept", "write-source",
        "write-moc", "apply-links", "apply-merge",
        "build-indexes", "emit-finalize",
    ]:
        assert sub in r.stdout


def test_ingest_deterministic_processes_text_file(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "doc.md").write_text("# X\n\nbody " * 50, encoding="utf-8")
    out = tmp_path / "work"

    r = _run(["ingest-deterministic",
              "--input", str(in_dir),
              "--output", str(out)])
    assert r.returncode == 0
    # Report on stdout
    report = json.loads(r.stdout)
    assert "results" in report
    # One result for doc.md, marked as text/passthrough → no vision needed
    entry = report["results"]["doc.md"]
    assert entry["needs_vision"] is False
    # Files on disk
    assert (out / "raw" / "doc.md").exists()
    assert (out / "raw" / "doc.meta.json").exists()


def test_write_concept_creates_valid_page(tmp_path: Path):
    body_file = tmp_path / "body.md"
    body_file.write_text("# OAuth2\n\nbody", encoding="utf-8")
    vault = tmp_path / "vault"

    r = _run(["write-concept",
              "--vault", str(vault),
              "--name", "oauth2-flow",
              "--title", "OAuth2 Flow",
              "--source-file", "handbook.md",
              "--source-sections", "3.1,3.2",
              "--body-file", str(body_file)])
    assert r.returncode == 0
    # Reads back as a valid ConceptPage
    from matter_expert import ConceptPage
    page = ConceptPage.read(vault / "concepts" / "oauth2-flow.md")
    assert page.frontmatter.title == "OAuth2 Flow"
    assert page.frontmatter.sources[0].file == "handbook.md"
    assert page.frontmatter.sources[0].sections == ["3.1", "3.2"]


def test_write_moc_creates_valid_page(tmp_path: Path):
    vault = tmp_path / "vault"
    r = _run(["write-moc",
              "--vault", str(vault),
              "--name", "auth",
              "--title", "Authentication",
              "--children", "oauth2-flow,jwt-tokens"])
    assert r.returncode == 0
    from matter_expert import MOCPage
    page = MOCPage.read(vault / "MOCs" / "auth.md")
    assert page.frontmatter.children == ["oauth2-flow", "jwt-tokens"]


def test_apply_links_updates_concept_frontmatter(tmp_path: Path):
    # Seed a concept first
    body_file = tmp_path / "body.md"
    body_file.write_text("body", encoding="utf-8")
    vault = tmp_path / "vault"
    _run(["write-concept",
          "--vault", str(vault),
          "--name", "x", "--title", "X",
          "--source-file", "s.md", "--source-sections", "",
          "--body-file", str(body_file)])

    links_file = tmp_path / "links.json"
    links_file.write_text(json.dumps({
        "related": ["y"], "prerequisites": [],
        "examples": [], "contrasts": [], "refines": [],
    }), encoding="utf-8")

    r = _run(["apply-links",
              "--vault", str(vault),
              "--concept", "x",
              "--links-json", str(links_file)])
    assert r.returncode == 0

    from matter_expert import ConceptPage
    page = ConceptPage.read(vault / "concepts" / "x.md")
    assert page.frontmatter.related == ["y"]


def test_apply_merge_replaces_members_with_merged_page(tmp_path: Path):
    vault = tmp_path / "vault"
    body_file = tmp_path / "body.md"
    body_file.write_text("body", encoding="utf-8")

    # Seed two concepts to merge
    for name in ("oauth-a", "oauth-b"):
        _run(["write-concept", "--vault", str(vault),
              "--name", name, "--title", name.upper(),
              "--source-file", f"{name}.md", "--source-sections", "",
              "--body-file", str(body_file)])

    merged_body = tmp_path / "merged.md"
    merged_body.write_text("# Merged\n\nmerged body", encoding="utf-8")

    r = _run(["apply-merge",
              "--vault", str(vault),
              "--members", "oauth-a,oauth-b",
              "--merged-body-file", str(merged_body)])
    assert r.returncode == 0

    # oauth-a survives with merged body + merged_from list
    from matter_expert import ConceptPage
    surv = ConceptPage.read(vault / "concepts" / "oauth-a.md")
    assert "merged body" in surv.body
    assert set(surv.frontmatter.merged_from) == {"oauth-a", "oauth-b"}
    # oauth-b is gone
    assert not (vault / "concepts" / "oauth-b.md").exists()


def test_build_indexes_writes_four_files(tmp_path: Path):
    vault = tmp_path / "vault"
    body_file = tmp_path / "body.md"
    body_file.write_text("body", encoding="utf-8")
    _run(["write-concept", "--vault", str(vault),
          "--name", "x", "--title", "X",
          "--source-file", "s.md", "--source-sections", "",
          "--body-file", str(body_file)])

    index_dir = tmp_path / "_index"
    r = _run(["build-indexes",
              "--vault", str(vault),
              "--index-dir", str(index_dir)])
    assert r.returncode == 0
    assert (index_dir / "concept_index.json").exists()
    assert (index_dir / "moc_map.json").exists()
    assert (index_dir / "link_graph.json").exists()
    assert (index_dir / "alias_map.json").exists()


def test_emit_finalize_produces_plugin_structure(tmp_path: Path):
    # Set up a tiny vault first
    vault = tmp_path / "vault"
    body_file = tmp_path / "body.md"
    body_file.write_text("body", encoding="utf-8")
    _run(["write-concept", "--vault", str(vault),
          "--name", "x", "--title", "X",
          "--source-file", "s.md", "--source-sections", "",
          "--body-file", str(body_file)])
    _run(["write-source", "--vault", str(vault),
          "--name", "s", "--original-file", "s.pdf",
          "--page-count", "1", "--body-file", str(body_file)])
    index_dir = tmp_path / "_index"
    _run(["build-indexes", "--vault", str(vault), "--index-dir", str(index_dir)])

    plugin = tmp_path / "plugin"
    r = _run([
        "emit-finalize",
        "--plugin-root", str(plugin),
        "--plugin-name", "test-skill",
        "--version", "0.1.0",
        "--description", "Test skill.",
        "--author", "tester",
        "--vault", str(vault),
        "--index-dir", str(index_dir),
        "--skill-description", "Pushy trigger description text.",
    ])
    assert r.returncode == 0
    assert (plugin / ".claude-plugin" / "plugin.json").exists()
    assert (plugin / "README.md").exists()
    assert (plugin / "skills" / "test-skill" / "SKILL.md").exists()
    # Bundled runtime
    assert (plugin / "skills" / "test-skill" / "scripts" / "runtime" / "vault_locate.py").exists()
    # Initial memory
    assert (plugin / "skills" / "test-skill" / "memory" / "query_cache.json").exists()
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/integration/helpers_cli.py`**

```python
"""Deterministic CLI helpers for subscription-native orchestration.

These subcommands do NOT call any LLM. They are designed to be invoked by
the docs-to-skill SKILL.md between subagent dispatches; the subagents
produce LLM output (concept bodies, links JSON, etc.) which the helpers
then write into the vault.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from builder.emit.index_builder import build_indexes as _build_indexes_fn
from builder.emit.memory_initializer import initialize_memory
from builder.emit.plugin_metadata import PluginMetadata, write_plugin_json
from builder.emit.readme import ReadmeMeta, generate_readme
from builder.emit.runtime_bundler import bundle_runtime
from builder.ingest.pandoc_converter import PandocConverter
from builder.ingest.passthrough import PassthroughConverter
from builder.ingest.pdf_text import PDFTextExtractor, is_text_extraction_plausible
from matter_expert import (
    ConceptFrontmatter, ConceptPage, MOCFrontmatter, MOCPage,
    Source, SourceFrontmatter, SourcePage, VaultPaths,
)


PANDOC_EXT = {".txt", ".html", ".htm", ".docx", ".rtf", ".odt", ".epub"}
MD_EXT = {".md", ".markdown"}


def _cmd_ingest_deterministic(args) -> int:
    input_dir: Path = args.input
    out_dir: Path = args.output
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    passthrough = PassthroughConverter()
    pandoc = PandocConverter()
    pdf_text = PDFTextExtractor()

    results: dict[str, dict] = {}
    for path in sorted(input_dir.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        item: dict = {"source_path": str(path), "needs_vision": False}
        try:
            if ext in MD_EXT:
                result = passthrough.convert(path)
            elif ext in PANDOC_EXT:
                result = pandoc.convert(path)
            elif ext == ".pdf":
                text_result = pdf_text.extract(path)
                if is_text_extraction_plausible(
                    text_result.text, text_result.page_count,
                ):
                    result = pdf_text.convert(path)
                else:
                    # Vision needed — write nothing, mark for subagent
                    item["needs_vision"] = True
                    item["page_count"] = text_result.page_count
                    results[path.name] = item
                    continue
            else:
                item["error"] = f"unsupported extension: {ext}"
                results[path.name] = item
                continue
        except Exception as e:
            item["error"] = str(e)
            results[path.name] = item
            continue

        body_path = raw_dir / f"{path.stem}.md"
        body_path.write_text(result.content, encoding="utf-8")
        (raw_dir / f"{path.stem}.meta.json").write_text(
            json.dumps(result.meta.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        item.update({
            "body_path": str(body_path),
            "extraction_method": result.meta.extraction_method.value,
            "extracted_chars": result.meta.extracted_chars,
            "outline": list(result.meta.outline),
            "page_count": result.meta.page_count,
        })
        results[path.name] = item

    json.dump({"results": results}, sys.stdout, indent=2,
              default=str, ensure_ascii=False)
    print()
    return 0


def _today() -> "date":
    return datetime.now(timezone.utc).date()


def _cmd_write_concept(args) -> int:
    paths = VaultPaths(root=args.vault)
    sections = [s for s in args.source_sections.split(",") if s.strip()]
    body = args.body_file.read_text(encoding="utf-8")
    fm = ConceptFrontmatter(
        title=args.title,
        sources=[Source(file=args.source_file, sections=sections)],
        tags=[t for t in (args.tags or "").split(",") if t.strip()],
        created=_today(),
    )
    page = ConceptPage(frontmatter=fm, body=body,
                       path=paths.concept_for(args.name))
    page.write()
    return 0


def _cmd_write_source(args) -> int:
    paths = VaultPaths(root=args.vault)
    body = args.body_file.read_text(encoding="utf-8")
    fm = SourceFrontmatter(
        title=args.name,
        original_file=args.original_file,
        original_format=args.original_format,
        page_count=args.page_count,
        extraction_method=args.extraction_method,  # type: ignore[arg-type]
        language_detected=args.language_detected,
        ingested=_today(),
    )
    page = SourcePage(frontmatter=fm, body=body,
                      path=paths.source_for(args.name))
    page.write()
    return 0


def _cmd_write_moc(args) -> int:
    paths = VaultPaths(root=args.vault)
    children = [c for c in args.children.split(",") if c.strip()]
    fm = MOCFrontmatter(
        title=args.title, children=children,
        parents=[p for p in (args.parents or "").split(",") if p.strip()],
        related_mocs=[r for r in (args.related_mocs or "").split(",") if r.strip()],
        created=_today(),
    )
    body = (
        f"# {args.title} MOC\n\n## Concepts\n\n"
        + "\n".join(f"- [[{c}]]" for c in children) + "\n"
    )
    page = MOCPage(frontmatter=fm, body=body,
                   path=paths.mocs / f"{args.name}.md")
    page.write()
    return 0


def _cmd_apply_links(args) -> int:
    paths = VaultPaths(root=args.vault)
    links = json.loads(args.links_json.read_text(encoding="utf-8"))
    page = ConceptPage.read(paths.concept_for(args.concept))
    page.frontmatter.related = list(links.get("related", []))
    page.frontmatter.prerequisites = list(links.get("prerequisites", []))
    page.frontmatter.examples = list(links.get("examples", []))
    page.frontmatter.contrasts = list(links.get("contrasts", []))
    page.frontmatter.refines = list(links.get("refines", []))
    page.write()
    return 0


def _cmd_apply_merge(args) -> int:
    paths = VaultPaths(root=args.vault)
    members = [m.strip() for m in args.members.split(",") if m.strip()]
    if len(members) < 2:
        print("error: --members must list 2+ concept names", file=sys.stderr)
        return 1

    member_pages = []
    for name in members:
        path = paths.concept_for(name)
        if path.exists():
            member_pages.append(ConceptPage.read(path))
    if len(member_pages) < 2:
        print("error: fewer than 2 member pages exist on disk", file=sys.stderr)
        return 1

    body = args.merged_body_file.read_text(encoding="utf-8")
    # Aggregate sources from all members.
    seen: set[str] = set()
    sources: list[Source] = []
    for p in member_pages:
        for s in p.frontmatter.sources:
            if s.file not in seen:
                seen.add(s.file)
                sources.append(s)

    survivor = member_pages[0]
    survivor.frontmatter.sources = sources
    survivor.frontmatter.merged_from = list(members)
    survivor.body = body
    survivor.write()
    for p in member_pages[1:]:
        p.path.unlink()
    return 0


def _cmd_build_indexes(args) -> int:
    paths = VaultPaths(root=args.vault)
    _build_indexes_fn(vault=paths, index_dir=args.index_dir)
    return 0


def _cmd_emit_finalize(args) -> int:
    # Copy the prepared vault into the plugin.
    plugin_root: Path = args.plugin_root
    skill_dir = plugin_root / "skills" / args.plugin_name
    bundled_vault = skill_dir / "vault"
    bundled_vault.mkdir(parents=True, exist_ok=True)
    src_vault: Path = args.vault
    for subdir in ("concepts", "MOCs", "sources"):
        src = src_vault / subdir
        if src.exists():
            shutil.copytree(src, bundled_vault / subdir, dirs_exist_ok=True)

    # Copy the prepared _index/ into the plugin.
    bundled_index = skill_dir / "_index"
    if args.index_dir.exists():
        shutil.copytree(args.index_dir, bundled_index, dirs_exist_ok=True)

    # Bundle runtime.
    bundle_runtime(plugin_skill_dir=skill_dir)

    # Write SKILL.md (uses the pre-generated description text).
    from builder.emit.skill_md import SKILL_MD_TEMPLATE
    skill_md = SKILL_MD_TEMPLATE.format(
        name=args.plugin_name,
        description=args.skill_description.replace("\n", " ").strip(),
        title=args.plugin_name.replace("-", " ").title(),
    )
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    # Initialize memory.
    memory_dir = skill_dir / "memory"
    link_graph_path = bundled_index / "link_graph.json"
    link_graph = json.loads(link_graph_path.read_text(encoding="utf-8")) \
        if link_graph_path.exists() else {}
    initialize_memory(memory_dir=memory_dir, link_graph=link_graph)

    # Plugin metadata + README.
    write_plugin_json(
        PluginMetadata(
            name=args.plugin_name, version=args.version,
            description=args.description, author=args.author,
        ),
        plugin_root=plugin_root,
    )
    concept_count = len(list((bundled_vault / "concepts").glob("*.md"))) \
        if (bundled_vault / "concepts").exists() else 0
    moc_count = len(list((bundled_vault / "MOCs").glob("*.md"))) \
        if (bundled_vault / "MOCs").exists() else 0
    generate_readme(
        plugin_root=plugin_root,
        meta=ReadmeMeta(
            plugin_name=args.plugin_name, version=args.version,
            description=args.description,
            concept_count=concept_count, moc_count=moc_count,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docs-to-skill-helpers",
        description="Deterministic helpers for the subscription-native orchestrator.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest-deterministic")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(fn=_cmd_ingest_deterministic)

    p = sub.add_parser("write-concept")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--source-file", required=True)
    p.add_argument("--source-sections", default="")
    p.add_argument("--tags", default="")
    p.add_argument("--body-file", type=Path, required=True)
    p.set_defaults(fn=_cmd_write_concept)

    p = sub.add_parser("write-source")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--original-file", required=True)
    p.add_argument("--original-format", default="pdf")
    p.add_argument("--page-count", type=int, required=True)
    p.add_argument("--extraction-method", default="text",
                   choices=["text", "vision_fallback", "hybrid"])
    p.add_argument("--language-detected", default="en")
    p.add_argument("--body-file", type=Path, required=True)
    p.set_defaults(fn=_cmd_write_source)

    p = sub.add_parser("write-moc")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--children", required=True)
    p.add_argument("--parents", default="")
    p.add_argument("--related-mocs", default="")
    p.set_defaults(fn=_cmd_write_moc)

    p = sub.add_parser("apply-links")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--links-json", type=Path, required=True)
    p.set_defaults(fn=_cmd_apply_links)

    p = sub.add_parser("apply-merge")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--members", required=True)
    p.add_argument("--merged-body-file", type=Path, required=True)
    p.set_defaults(fn=_cmd_apply_merge)

    p = sub.add_parser("build-indexes")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--index-dir", type=Path, required=True)
    p.set_defaults(fn=_cmd_build_indexes)

    p = sub.add_parser("emit-finalize")
    p.add_argument("--plugin-root", type=Path, required=True)
    p.add_argument("--plugin-name", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--author", required=True)
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--index-dir", type=Path, required=True)
    p.add_argument("--skill-description", required=True,
                   help="The pushy trigger description from the trigger-desc-agent.")
    p.set_defaults(fn=_cmd_emit_finalize)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run → 8 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/integration/helpers_cli.py tests/builder/integration/test_helpers_cli.py
git commit -m "feat(sub-mode): deterministic CLI helpers for subagent-orchestrated builds"
```

---

## Task 5: Rewrite docs-to-skill SKILL.md as Dual-Mode Orchestrator

**Files:**
- Modify: `docs-to-skill/SKILL.md`

The new SKILL.md documents both modes and walks Claude through subagent-based orchestration in subscription mode.

- [ ] **Step 1: Replace `docs-to-skill/SKILL.md`**

```markdown
---
name: docs-to-skill
description: Use this skill to build an installable expert Claude Code skill from a folder of documents (PDF, DOCX, HTML, markdown) plus optional URLs. Triggers on phrases like "build a skill from these docs", "create an expert from this folder", "turn these PDFs into a skill", "generate an expert skill for my docs", "make a knowledge skill out of...". The skill runs a 5-phase pipeline (Ingest → Transform → Link → QA → Emit) and produces an installable plugin with a typed-link Obsidian-style knowledge vault and cited answers. Supports two execution modes: subscription-native (uses bundled subagents — no API key required) or API-direct (uses ANTHROPIC_API_KEY for billing).
---

# docs-to-skill

Builds an installable expert Claude Code skill from a directory of source
documents. Two modes are supported:

| Mode | When to use | LLM billing |
|------|-------------|-------------|
| **Subscription-native** (default) | Running inside Claude Code Pro/Max | Subscription |
| **API-direct** | Running headless or in CI; explicit API budget | `ANTHROPIC_API_KEY` |

## Ask the user first

1. **Input directory** — path to the source documents
2. **URL list** (optional) — any web pages to include
3. **Plugin name** (kebab-case) and short description
4. **Output directory** — where to write the produced plugin (default: `~/expert-skills/<name>`)
5. **Mode** — subscription (default) or `--api-direct` if they prefer

## Subscription-native flow

Follow these steps in order. Each LLM-driven step uses one of the bundled
subagents (in `docs-to-skill/agents/`); each deterministic step uses
`python -m builder.integration.helpers_cli <subcommand>`.

### 1. Deterministic Ingest

Run:
```bash
python -m builder.integration.helpers_cli ingest-deterministic \
  --input <input-dir> --output <work-dir>
```

Parse the stdout JSON. For each source document:
- If `needs_vision: true` → dispatch the `vision-pdf-agent` for each page
  image, then write the result with `write-source` and `write-concept`
  via the standard transform flow.
- Otherwise → continue with the regular Transform.

### 2. Transform (per source document)

For each document with `needs_vision: false`:

a. Dispatch the `analyzer-agent` subagent with the raw markdown body
   (`<work-dir>/raw/<doc>.md`). It returns a JSON outline.
b. For each entry in the outline, dispatch the `extractor-agent` subagent
   with the source body + concept name + title. Save the returned body
   to a temp file and run:
   ```bash
   python -m builder.integration.helpers_cli write-concept \
     --vault <work-dir>/vault --name <name> --title <title> \
     --source-file <doc>.md --source-sections "<sections>" \
     --body-file <tempfile>
   ```
c. Run `write-source` once per source document to preserve the original.
d. Dispatch the `coverage-transform-agent` with the source outline + the
   list of extracted concept titles. If `missed_topics` is non-empty,
   loop back to step (b) for the missed topics.

### 3. Link (across all concepts)

a. Read `<work-dir>/vault/concepts/*.md`, build a compact JSON inventory
   (one line per concept: `{name, title, summary, tags}`).
b. Dispatch the `cluster-agent` with the inventory. It returns clusters.
c. For each cluster with `members.length >= 2`:
   - Dispatch the `merger-agent` with the member bodies. It returns one
     merged body. Run:
     ```bash
     python -m builder.integration.helpers_cli apply-merge \
       --vault <work-dir>/vault --members "a,b,c" --merged-body-file <tmp>
     ```
d. Rebuild the inventory (after merges).
e. For each remaining concept, dispatch the `linker-agent` with the
   target and the full inventory. It returns typed-link JSON. Run:
   ```bash
   python -m builder.integration.helpers_cli apply-links \
     --vault <work-dir>/vault --concept <name> --links-json <tmp>
   ```
f. Group concepts by shared tags (≥ 2 concepts per tag). Run `write-moc`
   for each group.

### 4. QA (sampled)

a. Translation QA: sample 5% of concepts (min 10, max 50). For each,
   dispatch the `translation-qa-agent` with the concept body and a
   source excerpt. Collect verdicts.
b. Citation QA: sample 10%. Dispatch the `citation-qa-agent`.
c. Coherence QA: sample 15%. Dispatch the `coherence-qa-agent`.
d. Coverage QA: for each source document, dispatch the `coverage-qa-agent`
   with the source outline + extracted titles.
e. Link Resolution + Vault Integrity: pure-Python validators run via
   `pytest` against the vault (`python -m builder.qa.link_resolution`
   and `python -m builder.qa.integrity` — see the matter_expert
   validators).
f. Aggregate verdicts. If FAIL on any validator, report to the user and
   ask whether to fix manually or replay the relevant phase.

### 5. Emit

a. Run:
   ```bash
   python -m builder.integration.helpers_cli build-indexes \
     --vault <work-dir>/vault --index-dir <work-dir>/_index
   ```
b. Dispatch the `trigger-desc-agent` with the dominant vault topics
   (top 10 tags). It returns the pushy trigger description.
c. Run:
   ```bash
   python -m builder.integration.helpers_cli emit-finalize \
     --plugin-root <plugin-out> --plugin-name <name> --version 0.1.0 \
     --description "<short desc>" --author "<user>" \
     --vault <work-dir>/vault --index-dir <work-dir>/_index \
     --skill-description "<from trigger-desc-agent>"
   ```

### 6. Install and verify

Tell the user:
```
cp -r <plugin-out> ~/.claude/plugins/<name>/
# Restart Claude Code; the skill auto-loads.
```

## API-direct flow

For users without Claude Code, or for CI use. Single command:

```bash
python -m builder.integration.cli build \
  --input <dir> \
  --run-dir <state-dir> \
  --plugin-root <output> \
  --name <name> \
  --description "<short description>" \
  --yes
```

This uses the existing `AnthropicAgent` (requires `ANTHROPIC_API_KEY`).
All 5 phases run inside Python; subagents are NOT used.

## Resume / Replay (API-direct only)

The subscription-native flow re-runs from scratch each time (no
checkpoint file). The API-direct flow supports resume + replay; see the
`build` subcommand's `--replay-from` flag.
```

- [ ] **Step 2: Commit**

```bash
git add docs-to-skill/SKILL.md
git commit -m "feat(sub-mode): rewrite docs-to-skill SKILL.md as dual-mode orchestrator"
```

---

## Task 6: README Update + Public API Test

**Files:**
- Modify: `README.md`
- Create: `tests/integration/test_dual_mode.py`

- [ ] **Step 1: Append a "Subscription-Native Mode" section to README.md**

```markdown

## Subscription-Native Mode (no API key required)

If you have a Claude Code Pro or Max subscription, you can build expert
skills without spending API credits. Drop the `docs-to-skill/` directory
into `~/.claude/plugins/docs-to-skill/` and restart Claude Code.

Then, in any Claude Code session:

> Build a skill from the documents in `~/my-docs/` and call it `oauth-expert`.

The bundled SKILL.md walks Claude through dispatching 12 specialized
subagents (each with its own model + system prompt — see
`docs-to-skill/agents/*.md`) interspersed with deterministic helpers
(`python -m builder.integration.helpers_cli <subcommand>`).

- **Subagent definitions:** `docs-to-skill/agents/*.md` — each has a YAML
  frontmatter (name, description, model) plus a system prompt as the body
- **Models per phase:** matches design spec §4.1 (Haiku for
  Ingest/Transform/Coverage, Sonnet for Link/QA/Emit)
- **Cost:** billed against your Claude.ai subscription, NOT your API key

Both modes coexist. The CLI (`python -m builder.integration.cli build`)
remains available for API-direct use.

### Sources

- [Subagents in Claude Code](https://claude.com/blog/subagents-in-claude-code)
- [Subagents in the SDK](https://code.claude.com/docs/en/agent-sdk/subagents)
```

- [ ] **Step 2: Write a smoke test that verifies both modes are wired**

```python
"""Smoke test that both execution modes are documented and reachable."""
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def test_subscription_mode_skill_md_exists():
    assert (REPO / "docs-to-skill" / "SKILL.md").exists()


def test_subscription_mode_agents_dir_has_12_files():
    agents = list((REPO / "docs-to-skill" / "agents").glob("*.md"))
    assert len(agents) == 12


def test_api_direct_mode_cli_module_importable():
    # The original API-direct path still works.
    from builder.integration.cli import main
    assert callable(main)


def test_helpers_cli_module_importable():
    # The subscription-mode helpers are reachable.
    from builder.integration.helpers_cli import main
    assert callable(main)


def test_skill_md_documents_both_modes():
    content = (REPO / "docs-to-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert "Subscription-native" in content or "subscription-native" in content
    assert "API-direct" in content or "api-direct" in content
```

- [ ] **Step 3: Run all tests, commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pytest
git add README.md tests/integration/test_dual_mode.py
git commit -m "docs(sub-mode): README section + dual-mode smoke test"
```

---

## Done — what's now possible

After all 6 tasks:
- 12 subagent definitions under `docs-to-skill/agents/` (each with model + system prompt + description matching design spec §4.1)
- 8 deterministic CLI helpers under `builder.integration.helpers_cli`
- New dual-mode SKILL.md that orchestrates either subscription-native or API-direct execution
- All existing tests still pass; new tests cover subagent definitions, helpers, and dual-mode reachability

Sources used:
- [Agent Teams (experimental) — evaluated and not used](https://code.claude.com/docs/en/agent-teams)
- [Subagents in Claude Code](https://claude.com/blog/subagents-in-claude-code)
- [Subagents in the SDK](https://code.claude.com/docs/en/agent-sdk/subagents)
