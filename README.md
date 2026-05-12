# matter_expert — Foundation Library

Foundation library for the matter-expert skill creator.

This library defines the data model and I/O for the Obsidian-compatible
knowledge vault that the matter-expert skill creator builds and consumes.

## Install

```bash
pip install -e ".[dev]"
```

## Public API

### Vault structure
- `VaultPaths(root)` — resolve standard paths inside a vault

### Page types
- `ConceptPage`, `ConceptFrontmatter`, `Source` — the core unit of the vault
- `MOCPage`, `MOCFrontmatter` — Map-of-Content pages (hierarchical overviews)
- `SourcePage`, `SourceFrontmatter` — original-document pages under `vault/sources/`

### Index files (under `_index/`)
- `ConceptIndex` — concept name → location & metadata
- `MOCMap` — MOC hierarchy
- `LinkGraph` — typed links + materialized inverse links
- `AliasMap` — user-facing aliases → canonical concept names

### Validators
- `validate_vault(paths)` — full vault integrity check
- `validate_concept_frontmatter(fm, concept_name)` — single-concept structural check

## Usage

```python
from pathlib import Path
from matter_expert import VaultPaths, ConceptPage, validate_vault

paths = VaultPaths(root=Path("./vault"))
issues = validate_vault(paths)
for issue in issues:
    print(f"[{issue.severity.value}] {issue.location}: {issue.message}")

# Read a concept
page = ConceptPage.read(paths.concept_for("oauth2-flow"))
print(page.frontmatter.title)
print(page.frontmatter.related)  # ['jwt-tokens', 'session-management']
```

## Tests

```bash
pytest
```

## Status

This is Subproject 1 of the matter-expert skill creator.
See `docs/superpowers/specs/2026-05-10-docs-to-skill-design.md` for the full design.
See `docs/superpowers/plans/2026-05-10-foundation.md` for the implementation plan.

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

## Builder Pipeline Framework (Subproject 3)

The orchestration shell that subprojects 4–8 plug their phase agents into. Lives
under `src/builder/` and persists run state to `~/.docs-to-skill/<run-id>/pipeline_state.json`.

### Public API

```python
from pathlib import Path
from builder import (
    Pipeline, Phase, Model, Effort,
    DEFAULT_CONFIGS, config_for_phase,
    TokenUsage, estimate_cost, format_cost_breakdown,
    FailureClass, PipelineError, with_retry,
)

# Create a fresh run
pipeline = Pipeline.create(
    run_id="2026-05-10-knowledge-base",
    input_dir=Path("/path/to/inputs"),
    url_list=["https://example.com/spec"],
    run_dir=Path.home() / ".docs-to-skill" / "2026-05-10-knowledge-base",
)
pipeline.set_estimated_total(11.80)

# Phase implementations call:
pipeline.mark_phase_started(Phase.INGEST)
pipeline.record_item(Phase.INGEST, "doc_001.pdf", status="done", method="text")
pipeline.record_cost(Phase.INGEST, 0.42)
pipeline.mark_phase_completed(Phase.INGEST)

# Resume after a crash:
pipeline = Pipeline.resume(Path.home() / ".docs-to-skill" / "2026-05-10-knowledge-base")

# Replay a phase (and discard later phases' work):
pipeline.replay_from(Phase.LINK)
```

### Status

This is Subproject 3 of the matter-expert skill creator.
See `docs/superpowers/plans/2026-05-10-pipeline-framework.md` for this plan.

## End-to-end Builder (Subproject 9)

The user-facing entry point. Wires Ingest → Transform → Link → QA → Emit into
a single command.

### CLI

```bash
# Estimate the cost before running:
python -m builder.integration.cli estimate --input /path/to/docs

# Run the full build (asks for confirmation unless --yes):
python -m builder.integration.cli build \
  --input /path/to/docs \
  --run-dir ~/.docs-to-skill/2026-05-10-oauth-expert \
  --plugin-root ~/expert-skills/oauth-expert \
  --name oauth-expert \
  --description "Expert on OAuth, JWT, and authentication."

# Resume an aborted build (same command — auto-detects existing state):
python -m builder.integration.cli build \
  --input /path/to/docs \
  --run-dir ~/.docs-to-skill/2026-05-10-oauth-expert \
  --plugin-root ~/expert-skills/oauth-expert \
  --name oauth-expert \
  --description "Expert on OAuth, JWT, and authentication."

# Replay a specific phase (e.g., redo Link with a different model config):
python -m builder.integration.cli build \
  ... \
  --replay-from link
```

The CLI requires:
- `ANTHROPIC_API_KEY` in the environment (for the AnthropicAgent)
- `pandoc`, `pdftotext`, `pdftoppm` on PATH (system binaries)

### User-facing skill

For Claude Code users, `docs-to-skill/SKILL.md` provides a conversational
wrapper that invokes the CLI. Drop the `docs-to-skill/` directory into
`~/.claude/plugins/docs-to-skill/` and Claude will use it for any
"build a skill from these documents..." style request.

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
