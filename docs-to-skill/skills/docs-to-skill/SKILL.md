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

## Runtime location (read this first)

This plugin ships its own Python code, so it works immediately after install
with **no `pip install` step**. The code lives next to this file at
`scripts/lib/` and is reached through `${CLAUDE_SKILL_DIR}`, the absolute path of
this skill's directory that Claude Code sets when the skill activates.

Because each command block below runs in a fresh shell, **every** Python command
is prefixed with the bundled library on `PYTHONPATH`:

```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.helpers_cli <subcommand>
```

Run the commands exactly as written — keep the `PYTHONPATH=...` prefix and use
`python3`. The only things not bundled are a few system binaries used during
Ingest (pandoc, poppler); Step 0 checks for them.

## Ask the user first

1. **Input directory** — path to the source documents
2. **URL list** (optional) — any web pages to include
3. **Plugin name** (kebab-case) and short description
4. **Output directory** — where to write the produced plugin (default: `~/expert-skills/<name>`)
5. **Mode** — subscription (default) or `--api-direct` if they prefer

## Subscription-native flow

Follow these steps in order. Each LLM-driven step uses one of the bundled
subagents (in `docs-to-skill/agents/`); each deterministic step uses
`python -m builder.integration.helpers_cli <subcommand>` with the PYTHONPATH
prefix described above.

### 0. Preflight: check system tools

Run the environment check and read its output:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.helpers_cli doctor
```
If a binary is reported MISSING, tell the user the install command `doctor`
prints. `.md`/`.txt` inputs need nothing; PDFs need poppler (`pdftotext`,
`pdftoppm`); Office/HTML inputs need `pandoc`. Missing tools only skip the
affected files — the rest of the build proceeds — so it is fine to continue if
the user's inputs don't need the missing tool.

### 1. Deterministic Ingest

Run:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.helpers_cli ingest-deterministic \
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
   PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.helpers_cli write-concept \
     --vault <work-dir>/vault --name <name> --title <title> \
     --source-file <doc>.md --source-sections "<sections>" \
     --body-file <tempfile>
   ```
c. Run `write-source` once per source document to preserve the original:
   ```bash
   PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.helpers_cli write-source \
     --vault <work-dir>/vault --name <name> --original-file <doc> \
     --page-count <n> --body-file <tempfile>
   ```
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
     PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.helpers_cli apply-merge \
       --vault <work-dir>/vault --members "a,b,c" --merged-body-file <tmp>
     ```
d. Rebuild the inventory (after merges).
e. For each remaining concept, dispatch the `linker-agent` with the
   target and the full inventory. It returns typed-link JSON. Run:
   ```bash
   PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.helpers_cli apply-links \
     --vault <work-dir>/vault --concept <name> --links-json <tmp>
   ```
f. Group concepts by shared tags (≥ 2 concepts per tag). Run `write-moc`
   for each group:
   ```bash
   PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.helpers_cli write-moc \
     --vault <work-dir>/vault --name <name> --title <title> --children "a,b,c"
   ```

### 4. QA (sampled)

a. Translation QA: sample 5% of concepts (min 10, max 50). For each,
   dispatch the `translation-qa-agent` with the concept body and a
   source excerpt. Collect verdicts.
b. Citation QA: sample 10%. Dispatch the `citation-qa-agent`.
c. Coherence QA: sample 15%. Dispatch the `coherence-qa-agent`.
d. Coverage QA: for each source document, dispatch the `coverage-qa-agent`
   with the source outline + extracted titles.
e. Link Resolution + Vault Integrity: pure-Python validators:
   ```bash
   PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.qa.link_resolution --vault <work-dir>/vault
   PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.qa.integrity --vault <work-dir>/vault
   ```
f. Aggregate verdicts. If FAIL on any validator, report to the user and
   ask whether to fix manually or replay the relevant phase.

### 5. Emit

a. Run:
   ```bash
   PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.helpers_cli build-indexes \
     --vault <work-dir>/vault --index-dir <work-dir>/_index
   ```
b. Dispatch the `trigger-desc-agent` with the dominant vault topics
   (top 10 tags). It returns the pushy trigger description.
c. Run:
   ```bash
   PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.helpers_cli emit-finalize \
     --plugin-root <plugin-out> --plugin-name <name> --version 0.1.0 \
     --description "<short desc>" --author "<user>" \
     --vault <work-dir>/vault --index-dir <work-dir>/_index \
     --skill-description "<from trigger-desc-agent>"
   ```

### 6. Install and verify

The produced plugin is self-contained (stdlib-only runtime, no system binaries
required). Tell the user:
```
cp -r <plugin-out> ~/.claude/plugins/<name>/
# Restart Claude Code; the skill auto-loads.
```

## API-direct flow

For users without Claude Code, or for CI use. Single command:

```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/scripts/lib" python3 -m builder.integration.cli build \
  --input <dir> \
  --run-dir <state-dir> \
  --plugin-root <output> \
  --name <name> \
  --description "<short description>" \
  --yes
```

This uses the existing `AnthropicAgent` (requires `ANTHROPIC_API_KEY` and the
`anthropic` SDK, the one optional dependency — `pip install anthropic`). All 5
phases run inside Python; subagents are NOT used.

## Resume / Replay (API-direct only)

The subscription-native flow re-runs from scratch each time (no
checkpoint file). The API-direct flow supports resume + replay; see the
`build` subcommand's `--replay-from` flag.
