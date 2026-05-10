---
name: docs-to-skill
description: Use this skill whenever the user wants to build an expert Claude Code skill from a directory of documents (PDFs, DOCX, HTML, markdown) plus optional URLs. Triggers on phrases like "build a skill from these docs", "create an expert from this folder", "turn these PDFs into a skill", "generate an expert skill for my docs". The skill runs a 5-phase pipeline (Ingest → Transform → Link → QA → Emit) and produces an installable Claude Code plugin with a typed-link Obsidian-style knowledge vault and cited answers.
---

# docs-to-skill

This skill produces an installable expert Claude Code skill from a directory of documents.

## When the user invokes this skill

1. Ask which directory contains the source documents (and any URLs).
2. Ask where to write the generated plugin (default: `~/expert-skills/<name>`).
3. Ask for a plugin name (kebab-case) and short description.
4. Run the CLI to estimate cost first:
   ```
   python -m builder.integration.cli estimate --input <dir>
   ```
5. Show the estimate to the user, ask for confirmation.
6. On confirmation, run the full build:
   ```
   python -m builder.integration.cli build \
     --input <dir> --plugin-root <out> --run-dir <state-dir> \
     --name <name> --description "<desc>"
   ```
7. Surface the final cost and plugin path. Tell the user how to install it
   (drop into `~/.claude/plugins/<name>/` and restart Claude Code).

## When the user wants to resume an aborted build

Use the same `build` command — the framework detects the existing
`<state-dir>/pipeline_state.json` and resumes from the first incomplete phase.

## When the user wants to redo a specific phase

Use the same `build` command with `--replay-from <phase>` (one of ingest,
transform, link, qa, emit). The framework resets the target phase plus all
later phases and re-runs them.
