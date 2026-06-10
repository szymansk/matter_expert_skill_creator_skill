# Design: BM25F Retrieval for Layer-2 Vault Search

**Date:** 2026-06-09
**Status:** Approved (ready for implementation planning)

## Problem

The Layer-2 vault search (`runtime/vault_search.py`) currently shells out to
`rg -l` (or a pure-Python substring scan when ripgrep is absent) and returns an
**unranked, alphabetically-sorted** set of concept names that contain the query
substring. There is no relevance ranking, no sensible multi-term handling, and
no way to return only the most relevant hits. On larger vaults this surfaces
noise and forces Claude to read pages in arbitrary order.

## Goal

Replace the unranked substring search with **ranked BM25F retrieval**: relevance
ranking, multi-term query support, and Top-N results. Priority is **query-time
performance and precision**.

## Decisions (locked during brainstorming)

1. **Full switch** to ranked BM25 retrieval (ranking + multi-term + Top-N), not
   an add-on to the existing substring behavior.
2. **Precomputed index**: BM25 statistics are built at emit/build time and
   written to `_index/`. Recomputed only when vault content changes (rare,
   explicit). Query time is a pure lookup + scoring.
3. **ripgrep is not required.** It is dropped from the query path entirely; query
   time is pure Python — fast, deterministic, zero runtime dependency. (ripgrep
   was deemed unimportant by the user; the cleanest solution was chosen.)
4. **Indexed fields:** body **+ title + aliases + tags**, each with its own
   field boost (maximum precision, uses existing vault structure).
5. **Scoring model:** true **BM25F** (per-field length normalization + boosts
   merged into one BM25 score). Textbook standard; complexity lives in the
   offline builder.

## Architecture

A single shared pure-Python core used identically by build and query, so
tokenization can never drift between the two.

| Component | File | Role |
|---|---|---|
| BM25F core | `runtime/bm25.py` *(new)* | Tokenizer, index build, BM25F scoring. Imported by both build and query. |
| Index artifact | `_index/bm25_index.json` *(new)* | Vocabulary/postings, per-field doc lengths, avg field lengths, doc count, IDF data. JSON, consistent with the other 4 index files. |
| Emit integration | `builder/emit/index_builder.py` | Writes `bm25_index.json` in addition to the existing 4 indexes. Already loads bodies/titles/tags and builds the AliasMap. |
| Rebuild script | `runtime/bm25_build.py` *(new)* | Standalone CLI to (re)build `bm25_index.json` from a vault — the "added concepts, recompute" case. Bundled into produced skills via `runtime/`. |
| Query | `runtime/vault_search.py` *(rewritten)* | Loads `bm25_index.json`, scores, applies tag filter, returns ranked Top-N. |

`runtime_bundler.py` copies the whole `runtime/` tree into produced skills, so
`bm25.py` and `bm25_build.py` ship automatically with no bundler change required
(verify in tests).

### Why a shared core

The build must tokenize exactly as the query does. Both `index_builder.py`
(builder side) and `vault_search.py` (runtime side) import the tokenizer and
index format from `runtime/bm25.py`. The bundled `lib/` exposes `runtime/` and
`builder/` as sibling top-level packages, so `from runtime.bm25 import ...`
resolves from the builder context too (as the test pythonpath already provides).

## Scoring (BM25F)

One IDF per term; a pseudo term-frequency is the field-weighted sum across fields,
each field length-normalized independently:

```
tf'(t,d) = Σ_f  boost_f · occ(t,f,d) / (1 − b_f + b_f · len_f(d) / avglen_f)
score(q,d) = Σ_{t∈q}  IDF(t) · tf'(t,d) / (k1 + tf'(t,d))
IDF(t) = ln(1 + (N − n_t + 0.5) / (n_t + 0.5))
```

Multi-term queries are implicitly OR with relevance weighting: documents matching
more (and rarer) query terms rank higher.

### Defaults (centralized in one config block in `bm25.py`, tunable)

- Field boosts: **title 3.0 · aliases 2.5 · tags 2.0 · body 1.0**
- `k1 = 1.2`
- Per-field `b`: `b_body = 0.75`; shorter fields (title/aliases/tags) use a
  smaller `b` (e.g. 0.5) since length normalization matters less for short fields.

### Tokenization

- Unicode-aware lowercasing.
- Split on non-alphanumeric boundaries; digits are kept.
- **No stemming** (deterministic, language-neutral; pipeline content is English).
- **No explicit stopword list** — BM25 IDF already down-weights frequent terms.
  The tokenizer is a single function, easy to extend later (YAGNI for now).

### Field sourcing notes

- **body**: frontmatter-stripped Markdown body (reuse existing strip logic).
- **title**: `ConceptPage.frontmatter.title`.
- **tags**: `ConceptPage.frontmatter.tags`.
- **aliases**: from the AliasMap built during emit. Note the current pipeline
  sets `concept_index` aliases to `[]`, so the alias field may be empty in
  practice; the alias field then simply contributes nothing — no special-casing
  needed.

## Index artifact (`_index/bm25_index.json`)

Compact JSON holding everything needed for query-time scoring with no rescan:

- document count `N`
- per-field average lengths `avglen_f`
- per concept: per-field lengths `len_f(d)`
- postings: term → list of `(concept, per-field occurrence counts)` (or an
  equivalent compact encoding)
- enough to compute `IDF(t)` at load (document frequency `n_t` per term)

Exact serialization shape is an implementation detail; it must round-trip through
the vendored pure-Python `json` and stay deterministic across builds (stable
ordering).

## Query interface & backward compatibility

`vault_search.py` keeps `--vault --concept-index --query --tags`. New:

- `--top-n` (default **10**): ranked hits, best first.
- `--scores`: emit `[{"name": …, "score": …}]` instead of a bare name list.
  Default output stays a **plain ranked name list**, so existing SKILL.md
  invocations and callers keep working.
- `--index`: path to `bm25_index.json` (default: alongside `--concept-index`).

The **tag filter is applied after ranking** (restrict ranked results to concepts
carrying at least one requested tag — same semantics as today, but order is now
by relevance). The emitted SKILL.md Layer-2 snippet gains `--top-n 10`.

`search_vault()` keeps its callable signature but its return semantics change
from "sorted set of names" to "relevance-ranked list of names".

## Staleness / error handling

- Index **missing** → build it once automatically (never break); note on stderr.
- Index **stale** (vault mtime newer than index) → use it, warn on stderr to run
  `bm25_build.py`.
- Index **corrupt** → clear error message.
- Empty vault / no term matches → `[]`.

## Testing (TDD)

New tests:
- tokenizer behavior (case, punctuation, digits)
- BM25F ranking order on a small fixture
- **title hit ranks above a body-only hit** (field boost works)
- multi-term weighting (more/rarer terms rank higher)
- tag filter still restricts results
- Top-N truncation
- index build produces expected `bm25_index.json` shape
- stale / missing index handling (auto-build, warning)
- `--scores` output shape

Update existing tests:
- `tests/runtime/test_vault_search.py` (set semantics → ranking semantics)
- `tests/builder/emit/test_skill_md.py` (`--top-n` in emitted snippet)
- `tests/builder/emit/test_runtime_bundler.py` (ships `bm25.py` + `bm25_build.py`)
- `tests/runtime/test_public_api.py` (if it asserts search behavior/exports)

## Out of scope (YAGNI)

- Query-time ripgrep prefiltering.
- Stemming / lemmatization / stopword lists.
- Phrase/proximity queries, fuzzy matching.
- Incremental index updates (full rebuild is fine; recompute is rare).
