# Design: Layer-1 Cold-Start Retrieval via Title/Alias/Tag BM25

**Date:** 2026-06-10
**Status:** Approved (ready for implementation planning)

## Problem

The produced skill's Layer-1 entry-point locator (`runtime/vault_locate.py`)
resolves a query through four strategies in priority order:

1. `query_cache` — exact normalized match against cached queries
2. `learned_aliases` — alias is a substring of the query
3. `alias_map` — alias is a substring of the query
4. `moc_map` — a MOC name appears verbatim in the query
5. otherwise → `{"matches": [], "strategy": "none"}`

In the BM25 evaluation (`docs-to-skill-eval/`), Layer 1 returned
`"strategy": "none"` for **every** natural-language question. Reasons: the
cache and learned aliases are empty on a fresh skill; `alias_map` is empty
because the build pipeline currently sets concept aliases to `[]`; and MOC names
rarely appear verbatim in a natural query. Layer 1 is therefore dead weight at
cold start — the system relies entirely on Layer 2.

## Goal

Make Layer 1 productive for cold-start natural-language queries by returning
useful **entry-point** concepts, while keeping it **distinct from Layer 2**
(which does broad full-body BM25 recall). Layer 1 should answer "what concept is
this query about?" with high precision. The existing four strategies stay as
higher-priority short-cuts (they are the learning / exact-match path).

## Decisions (locked during brainstorming)

1. **Cold-start hit, not a Layer-1/Layer-2 merge.** Keep the layered model;
   Layer 1 stays a precise entry-point selector.
2. **New fallback ranks Title + Aliases + Tags** (not body) via BM25 — high
   precision, clearly distinct from Layer 2's full-body search.
3. **Top-N = 3** entry points (narrow start; Layer 3 expands via links).

## Architecture

### New strategy 5: `title_search`

`locate_entry_points` keeps strategies 1–4 unchanged. Before returning `"none"`,
it runs a **field-restricted BM25 ranking over Title + Aliases + Tags** and
returns the top-N concepts with score > 0:

```
{"matches": ["concept-a", "concept-b", "concept-c"], "strategy": "title_search"}
```

If the field-restricted score is zero for all concepts (no query token matches
any title/alias/tag), it returns `{"matches": [], "strategy": "none"}` and
Layer 2 takes over — preserving today's behavior for genuinely out-of-title
queries.

### Field-restricted scoring (`BM25Index.score` extension)

Add an optional `fields` parameter to `BM25Index.score`:

```python
def score(self, query: str, top_n: int | None = None,
          fields: tuple[str, ...] = FIELDS) -> list[tuple[str, float]]:
```

The per-field `tf'` accumulation only includes fields in `fields`; a concept
whose only occurrence of a term is in an excluded field contributes 0 for that
term (and is excluded if it matches nothing in the selected fields). **IDF stays
global** (document frequency over all fields) — this is a minimal, deterministic
change that is adequate for ranking; recomputing per-field df is explicitly out
of scope (YAGNI). Layer 2 (`vault_search`) calls `score` with the default
(all fields) and is unchanged. Layer 1 calls
`score(query, top_n=3, fields=("title", "aliases", "tags"))`.

This reuses the existing `bm25_index.json` (postings already carry per-field
counts and `doc_field_len` carries per-field lengths) — no index format change.

### Integration

`vault_locate` loads `index_dir / "bm25_index.json"` (already produced by Emit
and already present in `_index/`). It needs **no vault access** — the index
alone suffices for scoring. The CLI signature
(`--index-dir --memory-dir query`) is unchanged, so the emitted SKILL.md Layer-1
command needs no change.

### Error handling / graceful degradation

- `bm25_index.json` **missing** (e.g. an older skill, or not yet built) → skip
  strategy 5 and return `"none"` (exactly today's behavior). No crash.
- Corrupt `bm25_index.json` → skip strategy 5 (treat as missing); Layer 2 still
  works. Layer 1 must never hard-fail the locate step.
- Empty query / empty index → `"none"`.

## Components touched

| File | Change |
|---|---|
| `runtime/bm25.py` | Add `fields` param to `BM25Index.score` (field-restricted tf′). |
| `runtime/vault_locate.py` | Add strategy 5 `title_search`: load bm25 index, score `fields=("title","aliases","tags")`, return top-3 > 0; graceful skip if index absent/corrupt. |
| tests | Unit tests for field-restricted scoring + the new strategy + graceful degradation; an integration check on the Scholz vault. |

## Testing (TDD)

Unit — `BM25Index.score(fields=…)`:
- a term present only in `body` does NOT contribute when `fields=("title",...)`
- a title hit ranks; a tag-only hit ranks; both excluded-field and selected-field
  behavior verified on a small fixture
- default call (no `fields`) is unchanged (regression)

Unit — `locate_entry_points`:
- strategies 1–4 keep priority: when an alias/MOC/cache hit exists, the result is
  that strategy, NOT `title_search`
- a cold-start query whose tokens match concept titles/tags returns
  `strategy:"title_search"` with the expected concept among the top-3
- a query matching nothing in title/alias/tag returns `strategy:"none"`
- missing `bm25_index.json` → `strategy:"none"`, no exception
- corrupt `bm25_index.json` → `strategy:"none"`, no exception

Integration:
- Build/locate against the Scholz vault: the eval questions that previously gave
  `"none"` (e.g. "Breguet range equation", "landing field length wing loading")
  now return the gold concept (`breguet-range-equation-fuel`,
  `landing-field-length-constraint`) within the top-3 from Layer 1.

## Out of scope (YAGNI)

- Per-field IDF recomputation.
- Changing the bm25 index format.
- Merging Layer 1 and Layer 2.
- Populating concept aliases in the build pipeline (separate concern; aliases
  activate automatically here once present).
- Re-emitting / re-evaluating all existing skills (the eval re-run is a
  verification step, not a deliverable of this change).
