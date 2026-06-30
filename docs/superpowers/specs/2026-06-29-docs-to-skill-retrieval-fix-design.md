# Design: docs-to-skill Retrieval Fix

**Date:** 2026-06-29
**Status:** Approved (pending spec review)
**Source brief:** `/Users/marc.szymanski/Projects/adSCAILE_expert/docs-to-skill-retrieval-fix-brief.md`

## Problem

Skills produced by the `docs-to-skill` generator fail to retrieve relevant
concepts for natural-language questions. The reported symptom:

> Query *"sind kleine Bugfixes erlaubt, ohne einen kompletten Rerun?"* returns
> nothing from all three retrieval layers, even though matching concepts exist
> (`c192-resumable-tasks`, `c192-session-resume`, `c196-task-graph-lifecycle`,
> `c126-change-impact-lookup`, `c163-gate-idempotenz`).

### Verified root causes (all reproduced against source + the built skill)

- **Layer 2 has no tokenization.** `runtime/vault_search.py:110` matches the
  *whole query* as one case-insensitive substring against bodies. The ripgrep
  path passes the query as a single pattern, and `rg` is not on PATH for the
  Python interpreter (`shutil.which("rg") → None`), so the substring fallback
  always runs. A whole natural-language question never occurs verbatim in a body.
- **Aliases are never produced.** `emit/index_builder.py:38` hardcodes
  `aliases=[]`; `ConceptFrontmatter` (concept.py) has no `aliases` field at all;
  `AliasMap.build` iterates empty `entry.aliases`. Result: `alias_map.json == {}`
  in every built skill (verified: 0/514 entries carry aliases). Layer 1's
  alias strategies are therefore dead.
- **`vault_locate.py` is "first hit wins."** Strategies 2 & 3 return on the
  first alias substring match — a short generic alias would collapse a query
  onto a random concept.
- **Vocabulary gap.** The corpus uses *Rerun / resumable / Idempotenz*, not
  *Bugfix*. No morphological or synonym bridging exists.
- **SKILL.md gives no guidance.** The generated Layer-2 instruction says
  `--query "<keyword>"` with no hint that a natural question must be decomposed.

This repo is the **upstream source** of the installed plugin (same GitHub
remote as `~/.claude/plugins/marketplaces/matter-expert-skill-creator`). Runtime
scripts are bundled into each produced skill via `copytree` from
`scripts/lib/runtime/`. Fixing here fixes future builds; the already-built
`adscaile-expert` skill must be healed separately.

## Architecture decision

Layer 2 (keyword search) is the **primary retrieval engine**. Layer 1 (locate)
is a **non-short-circuiting accelerator**, not a co-equal path. This avoids the
shadowing failure mode: a populated-but-mediocre Layer 1 that short-circuits
before the better Layer 2 runs would be *worse* than today's dead Layer 1
(which at least falls through to Layer 2).

Concretely:
- Invest in Layer 2: tokenize → light-stem → synonym-expand → **IDF-weighted**
  ranking over `title + summary + tags + aliases + body`.
- Keep deterministic aliases (A1) but **high-precision only** (phrases), and
  change the SKILL.md orchestration so Layer 1 results *boost* but never
  *suppress* Layer 2.
- Generic morphological bridging via **light stemming** (always on, every
  generated skill) — a more honest answer to the vocabulary gap than an empty
  synonym map. Curated **synonyms** are an editable extra layered on top.

All runtime code stays **stdlib-only / zero-dependency / offline**, preserving
the plugin's "works immediately after marketplace add, no pip" guarantee.

## Components

### New unit: `runtime/text.py` (runtime, stdlib-only, auto-bundled)

Pure helpers shared by the runtime search path. Auto-copied into produced
skills by the existing `bundle_runtime` `copytree`.

- `tokenize(text: str) -> list[str]` — lowercase; split on non-alphanumeric
  (so `Rerun-Strategie` → `["rerun", "strategie"]`); drop a small built-in
  EN+DE stopword set; drop tokens shorter than 2 chars.
- `stem(token: str) -> str` — light suffix folding. EN: strip common suffixes
  (`-s`, `-es`, `-ing`, `-able`, `-ed`) with minimal length guards; DE: a few
  safe suffix rules (`-en`, `-ung`, `-e`). Goal: fold `bugfixes→bugfix`,
  `resumable/resuming→resum`. Conservative — never produce <3-char stems.
- `expand(tokens, synonym_groups) -> list[str]` — given equivalence groups,
  expand each token to its whole group (stemmed). No file I/O here; caller
  loads the groups.

### Edit: `runtime/vault_search.py` (Finding B — the core fix)

New ranking engine, replacing whole-query substring:

1. Load `concept_index` (title, summary, tags, aliases) and read each concept
   body (frontmatter-stripped, as today).
2. For each concept build **stemmed token sets** per field group:
   `strong` = title + aliases + tags; `weak` = summary + body.
3. Compute corpus **document frequency** per stemmed token (how many concepts
   contain it), → `idf(t) = log(1 + N / (1 + df(t)))` — smoothed so IDF is strictly positive even for a token matching most/all concepts (the bare `log(N/(1+df))` would go zero/negative and could drop common-only matches below the score>0 cutoff).
4. Tokenize + stem the query; synonym-expand (groups loaded from
   `--synonyms`, optional; absent/empty ⇒ no expansion).
5. **Score** each concept: for every distinct query token matched, add
   `idf(token) * field_weight` where `field_weight(strong) > field_weight(weak)`.
   A synonym-derived hit counts toward its source token (once). Add an
   **exact full-query phrase** boost when the normalized query is a substring
   of title/body.
6. Return concept names ranked best-first, capped at `--limit` (default 20).
   `--tags` filter preserved.

**Backward compatibility:** a single keyword still returns its concepts (now
ranked). Regression contract = *preservation, not exact equality*: the old
body matches for a single keyword must remain a subset of the new result set.
A substring fallback is retained for single-token queries so the old 6
`Rerun` matches are not lost to token-boundary effects.

New CLI: `--synonyms PATH` (optional), `--limit N` (default 20). Existing
`--vault`, `--concept-index`, `--query`, `--tags` unchanged.

### Edit: `runtime/vault_locate.py` (Finding A — ranking)

Strategies 2 (`learned_aliases`) and 3 (`alias_map`): collect **all** aliases
whose normalized form is a substring of the normalized query, rank by
specificity (longer/phrase first), return ranked top-N concept names. Strategy
labels unchanged. `query_cache` (exact prior) and `moc_map` unchanged.

The "never suppress Layer 2" behaviour is enforced in SKILL.md orchestration,
not inside this script — `vault_locate` stays a thin lookup.

### New unit: `matter_expert/aliases.py` + edit `emit/index_builder.py` (Finding A1)

`derive_aliases(name: str, title: str, tags: list[str]) -> list[str]` —
high-precision phrases only:
- Title phrase (full title, normalized).
- Slug phrase: strip `cNNN-` / `cNNN--` prefix, split on `-`, join — only if
  it yields ≥ 2 meaningful words.
- Multi-word tags (containing a space/hyphen) as phrases.
- Drop: anything < 4 chars, pure stopwords; single-word aliases only if length
  ≥ 6 and non-stopword. Dedup, lowercase-normalize.

`index_builder.py`: `aliases=[]` → `aliases=derive_aliases(name, title, tags)`.
`AliasMap.build` then fills `alias_map.json` automatically (no change needed
there).

### Edit: `emit/memory_initializer.py` — ship empty `synonyms.json`

Emit `memory/synonyms.json` = `{"groups": []}` (editable; lives in `memory/`,
the mutable runtime dir — not in the "immutable" `_index/`). Generated skills
ship it empty; no corpus assumptions baked in.

### Edit: `emit/skill_md.py` (Finding D — orchestration + guidance)

- **Layer 1 step:** describe it as an accelerator. "Use its matches as starting
  points, but **always also run Layer 2** unless Layer 1 returned
  `strategy=query_cache` (a confirmed exact prior)."
- **Layer 2 step:** "Pass the full question or keywords — the search tokenizes,
  drops stopwords, light-stems, expands synonyms, and ranks by IDF-weighted
  distinct terms matched. Prefer the meaningful nouns/verbs from the question."
  Add `--synonyms "${CLAUDE_SKILL_DIR}/memory/synonyms.json"` and an optional
  `--limit` to the example.

### Heal: `adscaile-expert` (generator fix is not retroactive)

Target: `/Users/marc.szymanski/Projects/adSCAILE_expert/adscaile-expert/skills/adscaile-expert`.

1. Rebuild its `_index` with the fixed builder (fills `aliases` +
   `alias_map.json`) against its existing vault.
2. Copy the fixed `vault_search.py`, `vault_locate.py`, and new `text.py`
   into its `scripts/runtime/`.
3. Seed its `memory/synonyms.json` groups:
   `["rerun","resume","wiederaufnahme","idempotenz","resumable"]` and
   `["bugfix","fix","patch"]` — so the acceptance query robustly reaches the
   resilience/idempotency concepts. Documented as editable.
4. Verify the acceptance query against the healed skill.

## Testing (TDD)

Unit:
- `text.py`: tokenization (punctuation/hyphen split, stopwords, min length),
  stemming (`bugfixes→bugfix`, `resumable→resum`, no <3-char stems), synonym
  group expansion.
- `aliases.py`: prefix stripping, phrase derivation, generic/short filtering,
  dedup.

Component:
- `vault_search`: multi-token recall, IDF ranking order (rare-token concept
  ranks above common-token concept), phrase boost, synonym hit, single-keyword
  backward-compat (old matches ⊆ new), `--tags` filter, `--limit`.
- `vault_locate`: multiple alias hits return ranked list; a short alias does
  not collapse the query; longer/more-specific alias ranks first.
- `index_builder`: `aliases` non-empty; `alias_map.json` non-empty.
- `skill_md`: template contains the new Layer-1/Layer-2 guidance strings.

Acceptance gate (against healed `adscaile-expert`):
- `vault_search.py --query "sind kleine Bugfixes erlaubt, ohne einen kompletten Rerun?"`
  returns a non-empty ranked list including ≥ 1 of
  `c192-resumable-tasks`, `c192-session-resume`, `c196-task-graph-lifecycle`,
  `c126-change-impact-lookup`, `c163-gate-idempotenz`.
- `vault_locate.py` returns `strategy != none` for representative natural
  questions.
- After rebuild: `alias_map.json` non-empty; `concept_index` entries carry
  non-empty `aliases`.
- Regression: existing single-keyword queries still return their prior matches.
- Over-matching: a short generic alias does not collapse a query onto a random
  concept (ranking, not first-hit-wins).

## Out of scope (YAGNI)

- Embedding/vector semantic ranking (breaks zero-dependency/offline guarantee).
- LLM-generated aliases (A2) and an `aliases` frontmatter field.
- Rewriting `vault_traverse` (Layer 3) — unaffected.
