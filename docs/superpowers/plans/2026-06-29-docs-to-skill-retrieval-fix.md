# docs-to-skill Retrieval Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `docs-to-skill`-generated skills retrieve relevant concepts for natural-language questions by making Layer 2 a tokenized, IDF-ranked search engine, reviving Layer 1 with high-precision deterministic aliases that never suppress Layer 2, and healing the already-built `adscaile-expert`.

**Architecture:** Layer 2 (`vault_search`) becomes the primary engine: tokenize → light-stem → synonym-expand → per-token substring match over `title + aliases + tags` (strong) and `summary + body` (weak), ranked by IDF × field weight with an exact-phrase boost. Layer 1 (`vault_locate`) stays a thin accelerator but ranks alias hits instead of first-hit-wins. Aliases are produced deterministically at emit time (high-precision phrases only). All runtime code stays stdlib-only.

**Tech Stack:** Python 3.10+ (`X | None`, `list[str]` syntax), pytest, stdlib only for `scripts/lib/runtime/*` and the new `runtime/text.py`. Build-time `matter_expert` code may use the vendored `yaml` but adds no third-party deps.

## Global Constraints

- Runtime modules under `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/` (incl. the new `text.py`) MUST import only the Python standard library — produced skills run with zero pip installs. No `requests`, no third-party NLP libs.
- No new third-party dependencies anywhere (build-time included).
- Keep existing module-docstring style and `from __future__ import annotations`.
- Tests run from repo root via `pytest`; `pyproject.toml` sets `pythonpath` and `tests/conftest.py` puts `scripts/lib` on `PYTHONPATH` for subprocess tests. Do not change those.
- All work on a feature branch (NOT `main`). Commit after every task.
- Generator source of truth: `docs-to-skill/skills/docs-to-skill/scripts/...`. The heal (Task 8) edits the *external* built skill at `/Users/marc.szymanski/Projects/adSCAILE_expert/adscaile-expert/skills/adscaile-expert/` — that is a different repo; do not git-commit there.

**Path shorthand used below:**
- `LIB = docs-to-skill/skills/docs-to-skill/scripts/lib`
- `BUILT = /Users/marc.szymanski/Projects/adSCAILE_expert/adscaile-expert/skills/adscaile-expert`

---

## Setup (before Task 1)

- [ ] **Create the feature branch**

```bash
cd /Users/marc.szymanski/Projects/matter_expert_skill_creator_skill
git checkout -b fix/retrieval-tokenize-rank
git add docs/superpowers/specs/2026-06-29-docs-to-skill-retrieval-fix-design.md \
        docs/superpowers/plans/2026-06-29-docs-to-skill-retrieval-fix.md
git commit -m "docs: spec + plan for docs-to-skill retrieval fix"
```

---

### Task 1: `runtime/text.py` — tokenize, stem, synonym expansion

**Files:**
- Create: `LIB/runtime/text.py`
- Test: `tests/runtime/test_text.py`

**Interfaces:**
- Produces:
  - `tokenize(text: str) -> list[str]` — lowercased, de-duped, stopwords + <2-char dropped, split on non-alphanumeric.
  - `stem(token: str) -> str` — light EN+DE suffix folding; never returns <3 chars.
  - `load_synonym_groups(path: Path | None) -> list[list[str]]` — reads `{"groups": [[...], ...]}`; missing/malformed ⇒ `[]`.
  - `build_synonym_index(groups: list[list[str]]) -> dict[str, set[str]]` — term → union of its groups.
  - `expand_token(token: str, syn_index: dict[str, set[str]]) -> set[str]` — `{token, stem(token)}` ∪ synonyms ∪ their stems.

- [ ] **Step 1: Write the failing test**

```python
# tests/runtime/test_text.py
from pathlib import Path

from runtime.text import (
    tokenize, stem, load_synonym_groups, build_synonym_index, expand_token,
)


def test_tokenize_splits_drops_stopwords_and_short_tokens():
    toks = tokenize("Sind kleine Bugfixes erlaubt, ohne einen Rerun?")
    assert "bugfixes" in toks and "rerun" in toks and "kleine" in toks
    assert "sind" not in toks and "ohne" not in toks and "einen" not in toks


def test_tokenize_splits_on_hyphen_and_dedupes():
    assert tokenize("Rerun-Strategie rerun") == ["rerun", "strategie"]


def test_stem_folds_english_plurals_and_suffixes():
    assert stem("bugfixes") == "bugfix"
    assert stem("tokens") == "token"
    assert stem("resumable").startswith("resum")


def test_stem_never_shorter_than_three():
    assert len(stem(" run")) >= 3
    assert stem("rerun") == "rerun"  # trimmed DE suffix list leaves it intact


def test_load_synonym_groups_missing_file_is_empty(tmp_path: Path):
    assert load_synonym_groups(tmp_path / "nope.json") == []
    assert load_synonym_groups(None) == []


def test_load_synonym_groups_reads_groups(tmp_path: Path):
    p = tmp_path / "synonyms.json"
    p.write_text('{"groups": [["rerun", "resume", "Idempotenz"]]}', encoding="utf-8")
    assert load_synonym_groups(p) == [["rerun", "resume", "idempotenz"]]


def test_expand_token_includes_synonyms_and_stems():
    syn = build_synonym_index([["rerun", "resume", "idempotenz"]])
    variants = expand_token("rerun", syn)
    assert {"rerun", "resume", "idempotenz"} <= variants
    # plain token with no group still yields itself + stem
    assert "bugfix" in expand_token("bugfixes", build_synonym_index([]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_text.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'runtime.text'`

- [ ] **Step 3: Write minimal implementation**

```python
# LIB/runtime/text.py
"""Stdlib-only text helpers for the Layer-2 search engine.

Tokenization, light stemming, and synonym expansion. No file I/O beyond
reading the optional synonyms JSON. Bundled into every produced skill via the
runtime copytree, so this module must remain standard-library only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_STOPWORDS = {
    # English
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "is", "it", "of", "on", "or", "the", "to", "was", "what", "when",
    "which", "who", "why", "with", "do", "does", "can", "could", "should",
    "would", "i", "you", "we", "they", "this", "that", "these", "those",
    # German
    "der", "die", "das", "und", "oder", "ein", "eine", "einen", "einem",
    "einer", "ist", "sind", "war", "waren", "wie", "wer", "wo", "im",
    "mit", "ohne", "für", "auf", "an", "zu", "den", "dem", "des",
    "nicht", "auch", "noch", "schon", "man", "es", "sich",
}

_TOKEN_RE = re.compile(r"[a-z0-9äöüß]+")

# Longest-first so the most specific suffix is stripped.
_EN_SUFFIXES = ("ization", "isation", "ableness", "ingly", "able", "ible",
                "ment", "ness", "ing", "ies", "ied", "ions", "ion", "ers",
                "er", "ed", "es", "s")
# Trimmed DE list — bare "e"/"n" removed (too aggressive); substring matching
# bridges the rest.
_DE_SUFFIXES = ("ungen", "ung", "lich", "isch", "keit", "heit", "en", "er",
                "es", "em")


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, drop stopwords and <2-char tokens.

    Returns tokens in first-seen order, de-duplicated.
    """
    seen: list[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        if len(raw) < 2 or raw in _STOPWORDS:
            continue
        if raw not in seen:
            seen.append(raw)
    return seen


def stem(token: str) -> str:
    """Strip at most one EN/DE suffix, keeping the stem at >=3 chars."""
    for suffix in (*_EN_SUFFIXES, *_DE_SUFFIXES):
        if len(token) - len(suffix) >= 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def load_synonym_groups(path: Path | None) -> list[list[str]]:
    """Load equivalence groups from ``{"groups": [[...], ...]}``.

    Missing, unreadable, or malformed files yield no groups so search still
    works (just without synonym expansion).
    """
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    raw_groups = data.get("groups", []) if isinstance(data, dict) else []
    return [
        [str(term).lower() for term in group]
        for group in raw_groups
        if isinstance(group, list)
    ]


def build_synonym_index(groups: list[list[str]]) -> dict[str, set[str]]:
    """Map each term to the union of every group it appears in."""
    index: dict[str, set[str]] = {}
    for group in groups:
        members = set(group)
        for term in group:
            index.setdefault(term, set()).update(members)
    return index


def expand_token(token: str, syn_index: dict[str, set[str]]) -> set[str]:
    """Return match variants: the token, its stem, synonyms, and their stems."""
    variants = {token, stem(token)}
    for synonym in syn_index.get(token, ()):
        variants.add(synonym)
        variants.add(stem(synonym))
    return variants
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_text.py -v`
Expected: PASS (all 7)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/text.py tests/runtime/test_text.py
git commit -m "feat(runtime): add stdlib text helpers (tokenize, stem, synonym expansion)"
```

---

### Task 2: `matter_expert/aliases.py` — deterministic high-precision aliases

**Files:**
- Create: `LIB/matter_expert/aliases.py`
- Test: `tests/test_aliases.py`

**Interfaces:**
- Produces: `derive_aliases(name: str, title: str, tags: list[str]) -> list[str]` — high-precision phrase aliases (full title, slug phrase, multi-word tags, distinctive ≥6-char title words). Lowercased, de-duped, no <4-char entries.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_aliases.py
from matter_expert.aliases import derive_aliases


def test_derives_title_slug_and_distinctive_words():
    aliases = derive_aliases(
        "c192-session-resume", "Session Resume", ["task", "resilience"]
    )
    assert "session resume" in aliases   # full title phrase
    assert "session" in aliases          # distinctive >=6-char word
    assert "resume" in aliases


def test_strips_cNNN_double_dash_prefix_for_slug_phrase():
    aliases = derive_aliases("c196--task-graph-lifecycle", "Task Graph Lifecycle", [])
    assert "task graph lifecycle" in aliases


def test_multi_word_tags_become_phrases():
    aliases = derive_aliases("c001-x", "X", ["change-impact", "single"])
    assert "change impact" in aliases
    assert "single" not in aliases       # single-word tag is not an alias


def test_drops_short_and_dedupes():
    aliases = derive_aliases("c002-ab", "Ab", ["xy"])  # all too short
    assert aliases == []
    assert len(set(aliases)) == len(aliases)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_aliases.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'matter_expert.aliases'`

- [ ] **Step 3: Write minimal implementation**

```python
# LIB/matter_expert/aliases.py
"""Deterministic, high-precision alias derivation for concept pages.

Run at index-build time (Emit). Produces only meaning-bearing phrases so that
Layer-1 lookup stays precise — no short generic fragments that would over-match.
"""
from __future__ import annotations

import re

_PREFIX_RE = re.compile(r"^c\d+-{1,2}")  # strip cNNN- / cNNN-- slug prefixes
_MIN_LEN = 4                              # drop anything shorter than this
_MIN_SINGLE_WORD_LEN = 6                  # single words must be distinctive
_GENERIC = {"loop", "task", "node", "step", "item", "data", "code", "page"}


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def derive_aliases(name: str, title: str, tags: list[str]) -> list[str]:
    aliases: list[str] = []

    def add(candidate: str) -> None:
        candidate = _norm(candidate)
        if len(candidate) < _MIN_LEN or candidate in _GENERIC:
            return
        if candidate not in aliases:
            aliases.append(candidate)

    if title:
        add(title)

    slug = _PREFIX_RE.sub("", name)
    slug_words = [w for w in slug.split("-") if w]
    if len(slug_words) >= 2:
        add(" ".join(slug_words))

    for tag in tags:
        if " " in tag or "-" in tag:
            add(tag.replace("-", " "))

    for word in _norm(title).split():
        if len(word) >= _MIN_SINGLE_WORD_LEN and word not in _GENERIC:
            add(word)

    return aliases
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_aliases.py -v`
Expected: PASS (all 4)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/matter_expert/aliases.py tests/test_aliases.py
git commit -m "feat(matter_expert): deterministic high-precision alias derivation"
```

---

### Task 3: Wire aliases into the index builder

**Files:**
- Modify: `LIB/builder/emit/index_builder.py` (the `aliases=[]` at line ~38)
- Test: `tests/builder/emit/test_index_builder.py` (add cases)

**Interfaces:**
- Consumes: `derive_aliases` (Task 2), `AliasMap.build` (existing, unchanged).
- Produces: `concept_index.json` entries with non-empty `aliases`; non-empty `alias_map.json`.

- [ ] **Step 1: Write the failing test** (append to `tests/builder/emit/test_index_builder.py`)

```python
def test_build_indexes_populates_aliases(tmp_path: Path):
    paths = VaultPaths(root=tmp_path / "vault")
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()
    _seed(paths, "c192-session-resume", "Session Resume", tags=["resilience"])

    index_dir = tmp_path / "vault" / "_index"
    build_indexes(vault=paths, index_dir=index_dir)

    concept_index = json.loads((index_dir / "concept_index.json").read_text())
    assert concept_index["c192-session-resume"]["aliases"]  # non-empty
    assert "session resume" in concept_index["c192-session-resume"]["aliases"]

    alias_map = json.loads((index_dir / "alias_map.json").read_text())
    assert alias_map != {}
    assert alias_map.get("session resume") == "c192-session-resume"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/emit/test_index_builder.py::test_build_indexes_populates_aliases -v`
Expected: FAIL — `aliases` is `[]`, assertion on non-empty fails

- [ ] **Step 3: Write minimal implementation**

In `LIB/builder/emit/index_builder.py`, add the import near the top:

```python
from matter_expert.aliases import derive_aliases
```

Replace the hardcoded `aliases=[]` in the `ConceptIndexEntry(...)` construction:

```python
        name: ConceptIndexEntry(
            path=f"concepts/{name}.md",
            title=page.frontmatter.title,
            summary=_summary(page.body),
            tags=list(page.frontmatter.tags),
            aliases=derive_aliases(
                name, page.frontmatter.title, list(page.frontmatter.tags)
            ),
            moc=[],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/emit/test_index_builder.py -v`
Expected: PASS (existing 3 + new 1)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/builder/emit/index_builder.py tests/builder/emit/test_index_builder.py
git commit -m "feat(emit): populate concept aliases at index-build time"
```

---

### Task 4: Ship an empty `synonyms.json` in generated memory

**Files:**
- Modify: `LIB/builder/emit/memory_initializer.py` (`initialize_memory`)
- Test: `tests/builder/emit/test_memory_initializer.py` (add a case)

**Interfaces:**
- Produces: `memory/synonyms.json` = `{"groups": []}` in every generated skill (editable; consumed by `vault_search --synonyms`).

- [ ] **Step 1: Write the failing test** (append to `tests/builder/emit/test_memory_initializer.py`)

```python
def test_initial_synonyms_is_empty_groups(tmp_path: Path):
    memory_dir = tmp_path / "memory"
    initialize_memory(memory_dir=memory_dir)
    data = json.loads((memory_dir / "synonyms.json").read_text())
    assert data == {"groups": []}
```

(If `initialize_memory` / `json` are not already imported at the top of the test file, they are — the file already uses both. Verify the existing imports cover `from builder.emit.memory_initializer import initialize_memory` and `import json`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/emit/test_memory_initializer.py::test_initial_synonyms_is_empty_groups -v`
Expected: FAIL — `synonyms.json` does not exist

- [ ] **Step 3: Write minimal implementation**

In `LIB/builder/emit/memory_initializer.py`, add one line inside `initialize_memory`, after the `session_log.json` write:

```python
    _save_json(memory_dir / "session_log.json", [])
    _save_json(memory_dir / "synonyms.json", {"groups": []})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/emit/test_memory_initializer.py -v`
Expected: PASS (existing + new)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/builder/emit/memory_initializer.py tests/builder/emit/test_memory_initializer.py
git commit -m "feat(emit): ship empty editable memory/synonyms.json"
```

---

### Task 5: Rewrite Layer 2 — tokenized, IDF-ranked `vault_search`

**Files:**
- Modify: `LIB/runtime/vault_search.py` (replace ripgrep/substring engine; keep `_strip_frontmatter`)
- Modify: `tests/runtime/test_vault_search.py` (keep valid tests, replace the two ripgrep-specific ones, add ranking tests)

**Interfaces:**
- Consumes: `runtime.text` (Task 1), `runtime.index.load_concept_index` (existing).
- Produces: `search_vault(query, vault_dir, concept_index_path, tags=None, synonyms_path=None, limit=None) -> list[str]` — ranked best-first. CLI gains `--synonyms` and `--limit` (default 20). `_strip_frontmatter` unchanged and still exported.

- [ ] **Step 1: Replace the two ripgrep-specific tests and add ranking tests**

In `tests/runtime/test_vault_search.py`: delete `test_search_falls_back_when_ripgrep_missing` and `test_ripgrep_and_python_paths_agree` (they assert the removed rg architecture). Keep all other existing tests unchanged. Append:

```python
def test_search_tokenizes_natural_question(vault_dir: Path, built_indexes):
    """A whole natural-language question matches via its content tokens, not as
    one verbatim substring."""
    matches = search_vault(
        query="how does the oauth2 flow actually work?",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert "oauth2-flow" in matches


def test_search_ranks_rarer_token_concept_higher():
    """A concept matching a rare, discriminating token outranks one matching
    only a common token."""
    import json
    from pathlib import Path as _P
    # Build a tiny synthetic vault + index inline.
    import tempfile
    tmp = _P(tempfile.mkdtemp())
    concepts = tmp / "concepts"; concepts.mkdir()
    (concepts / "rare.md").write_text(
        "---\ntitle: Rare\n---\nThe widget uses idempotenz heavily.\n", encoding="utf-8")
    (concepts / "common1.md").write_text(
        "---\ntitle: C1\n---\nThe widget is common.\n", encoding="utf-8")
    (concepts / "common2.md").write_text(
        "---\ntitle: C2\n---\nThe widget is common too.\n", encoding="utf-8")
    index = {
        "rare": {"path": "concepts/rare.md", "title": "Rare", "summary": "",
                 "tags": [], "aliases": [], "moc": []},
        "common1": {"path": "concepts/common1.md", "title": "C1", "summary": "",
                    "tags": [], "aliases": [], "moc": []},
        "common2": {"path": "concepts/common2.md", "title": "C2", "summary": "",
                    "tags": [], "aliases": [], "moc": []},
    }
    cidx = tmp / "concept_index.json"
    cidx.write_text(json.dumps(index), encoding="utf-8")

    ranked = search_vault(query="widget idempotenz", vault_dir=tmp,
                          concept_index_path=cidx)
    assert ranked[0] == "rare"  # matches both tokens incl. the rare one


def test_search_synonym_expansion_bridges_vocabulary(tmp_path: Path):
    import json
    concepts = tmp_path / "concepts"; concepts.mkdir()
    (concepts / "resilience.md").write_text(
        "---\ntitle: Resilience\n---\nTasks support resume after a crash.\n",
        encoding="utf-8")
    index = {"resilience": {"path": "concepts/resilience.md", "title": "Resilience",
                            "summary": "", "tags": [], "aliases": [], "moc": []}}
    cidx = tmp_path / "concept_index.json"
    cidx.write_text(json.dumps(index), encoding="utf-8")
    syn = tmp_path / "synonyms.json"
    syn.write_text('{"groups": [["rerun", "resume"]]}', encoding="utf-8")

    # Query says "rerun"; the body says "resume"; the synonym group bridges them.
    matches = search_vault(query="rerun", vault_dir=tmp_path,
                           concept_index_path=cidx, synonyms_path=syn)
    assert "resilience" in matches
    # Without synonyms there is no match.
    assert search_vault(query="rerun", vault_dir=tmp_path,
                        concept_index_path=cidx) == []


def test_search_limit_caps_results(vault_dir: Path, built_indexes):
    matches = search_vault(query="auth security token http session encryption",
                           vault_dir=vault_dir,
                           concept_index_path=built_indexes.concept_index,
                           limit=2)
    assert len(matches) <= 2


def test_single_keyword_preserves_prior_matches(vault_dir: Path, built_indexes):
    """Regression contract: a single keyword still returns its old body matches
    (now possibly ranked / with extras), never fewer."""
    matches = set(search_vault(query="auth", vault_dir=vault_dir,
                               concept_index_path=built_indexes.concept_index))
    assert {"basic-auth", "oauth2-flow", "oauth2-google-flow"} <= matches
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/runtime/test_vault_search.py -v`
Expected: FAIL — new signature/kwargs (`synonyms_path`, `limit`) and ranking behavior not implemented yet (e.g. `TypeError: search_vault() got an unexpected keyword argument 'synonyms_path'`).

- [ ] **Step 3: Write the implementation** (replace the body of `LIB/runtime/vault_search.py` below the `_strip_frontmatter` function; keep the module docstring updated and keep `_strip_frontmatter` exactly as-is)

```python
"""Layer 2 retrieval: tokenized, IDF-ranked keyword search (stdlib only).

The query is tokenized, light-stemmed, and synonym-expanded; each distinct
query token is substring-matched against a concept's strong fields
(title + aliases + tags) and weak fields (summary + body, frontmatter stripped).
Concepts are ranked by the sum of IDF(token) * field-weight, with a boost when
the whole normalized query appears verbatim. Pure Python — produced skills need
no system binaries.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if _HERE.name == "runtime":
    _scripts = _HERE.parent
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))

from runtime.index import load_concept_index
from runtime.text import (
    build_synonym_index, expand_token, load_synonym_groups, tokenize,
)

_STRONG_WEIGHT = 3.0   # title + aliases + tags
_WEAK_WEIGHT = 1.0     # summary + body
_PHRASE_BOOST = 5.0    # whole normalized query appears verbatim


# _strip_frontmatter stays unchanged (see existing definition).


def _matches_any(text: str, variants: set[str]) -> bool:
    return any(v and v in text for v in variants)


def search_vault(
    query: str,
    vault_dir: Path,
    concept_index_path: Path,
    tags: list[str] | None = None,
    synonyms_path: Path | None = None,
    limit: int | None = None,
) -> list[str]:
    """Return concept names ranked by relevance to `query` (best first).

    `tags`, if given, restricts results to concepts carrying one of those tags.
    `synonyms_path` (optional) enables synonym expansion. `limit` caps results.
    """
    index = load_concept_index(concept_index_path)
    concepts_dir = vault_dir / "concepts"

    bodies: dict[str, str] = {}
    if concepts_dir.exists():
        for md_file in concepts_dir.glob("*.md"):
            bodies[md_file.stem] = _strip_frontmatter(
                md_file.read_text(encoding="utf-8")
            ).lower()

    names = set(bodies) | set(index)
    strong_text: dict[str, str] = {}
    weak_text: dict[str, str] = {}
    combined: dict[str, str] = {}
    for name in names:
        entry = index.get(name, {})
        strong_parts = [entry.get("title", "")]
        strong_parts += list(entry.get("aliases", []))
        strong_parts += list(entry.get("tags", []))
        strong_text[name] = " ".join(strong_parts).lower()
        weak_text[name] = (entry.get("summary", "").lower()
                           + " " + bodies.get(name, ""))
        combined[name] = strong_text[name] + " " + weak_text[name]

    syn_index = build_synonym_index(load_synonym_groups(synonyms_path))
    q_tokens = tokenize(query)
    token_variants = {t: expand_token(t, syn_index) for t in q_tokens}

    n_docs = max(len(names), 1)
    doc_freq: dict[str, int] = {
        t: sum(1 for name in names if _matches_any(combined[name], variants))
        for t, variants in token_variants.items()
    }

    def idf(token: str) -> float:
        return math.log(1 + n_docs / (1 + doc_freq.get(token, 0)))

    norm_query = " ".join(query.lower().split())

    scores: dict[str, float] = {}
    for name in names:
        score = 0.0
        for token, variants in token_variants.items():
            if _matches_any(strong_text[name], variants):
                score += idf(token) * _STRONG_WEIGHT
            elif _matches_any(weak_text[name], variants):
                score += idf(token) * _WEAK_WEIGHT
        if score and norm_query and norm_query in combined[name]:
            score += _PHRASE_BOOST
        if score > 0:
            scores[name] = score

    ranked = sorted(scores, key=lambda name: (-scores[name], name))

    if tags:
        wanted = set(tags)
        ranked = [
            name for name in ranked
            if name in index and wanted.intersection(index[name].get("tags", []))
        ]

    if limit is not None:
        ranked = ranked[:limit]
    return ranked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search the vault body content.")
    parser.add_argument("--vault", type=Path, required=True, help="Vault root directory")
    parser.add_argument("--concept-index", type=Path, required=True,
                        help="Path to concept_index.json")
    parser.add_argument("--query", required=True,
                        help="The user's question or keywords")
    parser.add_argument("--tags", default="",
                        help="Comma-separated list of tags to filter by")
    parser.add_argument("--synonyms", type=Path, default=None,
                        help="Optional path to synonyms.json")
    parser.add_argument("--limit", type=int, default=20,
                        help="Maximum number of ranked results")
    args = parser.parse_args(argv)

    tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    matches = search_vault(
        query=args.query,
        vault_dir=args.vault,
        concept_index_path=args.concept_index,
        tags=tag_list or None,
        synonyms_path=args.synonyms,
        limit=args.limit,
    )
    json.dump(matches, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Important:** preserve the existing `_strip_frontmatter` function verbatim (the tests import it). Place it between the imports and `_matches_any`. Remove the old `import shutil`, `import subprocess`, `import tempfile`, and the `_search_with_ripgrep` / `_search_with_python` / `_filter_by_tags` functions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_vault_search.py -v`
Expected: PASS (kept tests + 5 new). Then run the focused regression: `pytest tests/runtime/ -v`.

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/vault_search.py tests/runtime/test_vault_search.py
git commit -m "feat(runtime): tokenized IDF-ranked Layer-2 search with synonym expansion"
```

---

### Task 6: Rank alias hits in `vault_locate` (no first-hit-wins)

**Files:**
- Modify: `LIB/runtime/vault_locate.py` (strategies 2 & 3)
- Modify: `tests/runtime/test_vault_locate.py` (add ranking cases)

**Interfaces:**
- Produces: `locate_entry_points(...)` unchanged signature; `matches` for `learned_alias`/`alias_match` is now a specificity-ranked list (longest alias first), de-duped.

- [ ] **Step 1: Write the failing tests** (append to `tests/runtime/test_vault_locate.py`)

```python
def test_alias_hits_ranked_by_specificity(built_indexes, memory_dir: Path):
    (built_indexes.index_dir / "alias_map.json").write_text(
        json.dumps({"auth": "basic-auth", "oauth2 flow": "oauth2-flow"}),
        encoding="utf-8",
    )
    result = locate_entry_points(
        query="explain the oauth2 flow auth bits",
        index_dir=built_indexes.index_dir,
        memory_dir=memory_dir,
    )
    assert result["strategy"] == "alias_match"
    # Longer, more specific alias ranks first; both concepts present.
    assert result["matches"][0] == "oauth2-flow"
    assert "basic-auth" in result["matches"]


def test_short_generic_alias_does_not_collapse_query(built_indexes, memory_dir: Path):
    (built_indexes.index_dir / "alias_map.json").write_text(
        json.dumps({"id": "wrong-concept", "session management": "session-mgmt"}),
        encoding="utf-8",
    )
    result = locate_entry_points(
        query="how does session management handle an id",
        index_dir=built_indexes.index_dir,
        memory_dir=memory_dir,
    )
    assert result["matches"][0] == "session-mgmt"  # not the short "id" hit
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/runtime/test_vault_locate.py -v`
Expected: FAIL — current code returns the first hit only (single-element list, wrong order).

- [ ] **Step 3: Write the implementation**

In `LIB/runtime/vault_locate.py`, add a helper above `locate_entry_points`:

```python
def _ranked_alias_hits(alias_to_concept: dict[str, str],
                       normalized_query: str) -> list[str]:
    """All aliases that are substrings of the query, ranked by specificity
    (longer alias = more specific), de-duped by concept (best rank kept)."""
    hits = [
        (len(_normalize(alias)), concept)
        for alias, concept in alias_to_concept.items()
        if _normalize(alias) and _normalize(alias) in normalized_query
    ]
    hits.sort(key=lambda pair: -pair[0])
    ranked: list[str] = []
    for _, concept in hits:
        if concept not in ranked:
            ranked.append(concept)
    return ranked
```

Replace Strategy 2 and Strategy 3 blocks with:

```python
    # Strategy 2: ranked substring matches against learned_aliases.
    learned = load_learned_aliases(memory_paths.learned_aliases)
    ranked = _ranked_alias_hits(learned, normalized)
    if ranked:
        return {"matches": ranked, "strategy": "learned_alias"}

    # Strategy 3: ranked substring matches against the static alias_map.
    aliases = load_alias_map(index_paths.alias_map)
    ranked = _ranked_alias_hits(aliases, normalized)
    if ranked:
        return {"matches": ranked, "strategy": "alias_match"}
```

(Use the existing `normalized = _normalize(query)` variable; the duplicate `normalized_query = _normalize(query)` that the old Strategy 2 created can be removed.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runtime/test_vault_locate.py -v`
Expected: PASS (existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/vault_locate.py tests/runtime/test_vault_locate.py
git commit -m "fix(runtime): rank Layer-1 alias hits by specificity (no first-hit-wins)"
```

---

### Task 7: Update generated SKILL.md guidance + orchestration

**Files:**
- Modify: `LIB/builder/emit/skill_md.py` (`SKILL_MD_TEMPLATE`)
- Modify: `tests/builder/emit/test_skill_md.py` (assert guidance strings present)

**Interfaces:**
- Produces: generated SKILL.md whose Layer-1 step says "always also run Layer 2 unless strategy=query_cache", and whose Layer-2 step passes the full question + `--synonyms` and explains tokenization/ranking.

- [ ] **Step 1: Write the failing test** (append to `tests/builder/emit/test_skill_md.py`; reuse its existing fixtures/agent stub — match the file's current style)

```python
def test_skill_md_documents_tokenized_layer2_and_orchestration(tmp_path, fake_agent):
    from builder.emit.skill_md import SkillMdMeta, generate_skill_md
    path = generate_skill_md(
        skill_dir=tmp_path,
        meta=SkillMdMeta(skill_name="demo-expert", dominant_topics=["a", "b"]),
        agent=fake_agent,
    )
    text = path.read_text(encoding="utf-8")
    assert "always" in text.lower() and "layer 2" in text.lower()
    assert "query_cache" in text
    assert "--synonyms" in text
    assert "tokeniz" in text.lower()  # explains tokenization
```

(If `test_skill_md.py` has no `fake_agent` fixture, define a minimal one in that test mirroring the existing stub used by its other tests — an object with `.call(prompt, model=...)` returning an object with `.text`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/emit/test_skill_md.py -v`
Expected: FAIL — template lacks `--synonyms`, `query_cache`, tokenization wording.

- [ ] **Step 3: Update the template**

In `LIB/builder/emit/skill_md.py`, edit `SKILL_MD_TEMPLATE`. Replace the Layer-1 list item (step 1) and the Layer-2 list item (step 2) with:

```text
1. **Layer 1 — Locate entry points (accelerator).** Run:
   ```bash
   python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/vault_locate.py" \\
     --index-dir "${{CLAUDE_SKILL_DIR}}/_index" \\
     --memory-dir "${{CLAUDE_SKILL_DIR}}/memory" \\
     "<user-query>"
   ```
   Treat its matches as starting points. **Always also run Layer 2** below,
   unless Layer 1 returned `strategy: query_cache` (a confirmed exact prior) —
   Layer 1 boosts but never replaces the keyword search.

2. **Layer 2 — Keyword search (primary).** Pass the full question or the
   meaningful keywords; the search tokenizes, drops stopwords, light-stems,
   expands synonyms, and ranks concepts by how many distinct query terms they
   match (rarer terms weigh more). Run:
   ```bash
   python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/vault_search.py" \\
     --vault "${{CLAUDE_SKILL_DIR}}/vault" \\
     --concept-index "${{CLAUDE_SKILL_DIR}}/_index/concept_index.json" \\
     --synonyms "${{CLAUDE_SKILL_DIR}}/memory/synonyms.json" \\
     --limit 20 \\
     --query "<the user's question or keywords>"
   ```
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/emit/test_skill_md.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/builder/emit/skill_md.py tests/builder/emit/test_skill_md.py
git commit -m "feat(emit): SKILL.md guidance for tokenized search + non-suppressing Layer 1"
```

---

### Task 8: Full suite + heal the built `adscaile-expert`

**Files:**
- Create: `scripts/heal_adscaile.py` (one-off operational script in this repo)
- External (no commit): `BUILT/_index/*.json`, `BUILT/memory/synonyms.json`, `BUILT/scripts/runtime/{vault_search.py,vault_locate.py,text.py}`

**Interfaces:**
- Consumes: every prior task. Produces: a healed external skill that passes the acceptance query.

- [ ] **Step 1: Run the entire test suite (gate before touching the built skill)**

Run: `pytest -q`
Expected: PASS (all green). Fix any regressions before continuing.

- [ ] **Step 2: Write the heal script**

```python
# scripts/heal_adscaile.py
"""One-off: heal the already-built adscaile-expert skill in place.

Rebuilds its _index with the fixed builder (populating aliases), copies the
fixed runtime scripts into its bundled scripts/runtime/, and seeds an editable
synonyms.json. Not part of the plugin; lives in the generator repo only.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "docs-to-skill" / "skills" / "docs-to-skill" / "scripts" / "lib"
sys.path.insert(0, str(LIB))

BUILT = Path(
    "/Users/marc.szymanski/Projects/adSCAILE_expert/adscaile-expert/"
    "skills/adscaile-expert"
)

from builder.emit.index_builder import build_indexes  # noqa: E402
from matter_expert import VaultPaths  # noqa: E402

SYNONYM_GROUPS = {
    "groups": [
        ["rerun", "resume", "wiederaufnahme", "idempotenz", "resumable"],
        ["bugfix", "fix", "patch"],
    ]
}


def main() -> int:
    if not BUILT.exists():
        print(f"built skill not found: {BUILT}")
        return 1

    # 1. Rebuild the index (fills aliases + alias_map).
    build_indexes(vault=VaultPaths(root=BUILT / "vault"),
                  index_dir=BUILT / "_index")

    # 2. Copy the fixed runtime scripts.
    runtime_src = LIB / "runtime"
    runtime_dst = BUILT / "scripts" / "runtime"
    for fname in ("vault_search.py", "vault_locate.py", "text.py"):
        shutil.copy2(runtime_src / fname, runtime_dst / fname)

    # 3. Seed editable synonyms.
    (BUILT / "memory" / "synonyms.json").write_text(
        json.dumps(SYNONYM_GROUPS, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 4. Report.
    cidx = json.loads((BUILT / "_index" / "concept_index.json").read_text())
    amap = json.loads((BUILT / "_index" / "alias_map.json").read_text())
    with_aliases = sum(1 for v in cidx.values() if v.get("aliases"))
    print(f"concepts: {len(cidx)}, with aliases: {with_aliases}, "
          f"alias_map entries: {len(amap)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run the heal script**

Run: `python3 scripts/heal_adscaile.py`
Expected: prints `concepts: 514, with aliases: <>0, alias_map entries: <>0`

- [ ] **Step 4: Verify the acceptance query (the original symptom)**

```bash
SK="/Users/marc.szymanski/Projects/adSCAILE_expert/adscaile-expert/skills/adscaile-expert"
PYTHONPATH="$SK/scripts/lib" python3 "$SK/scripts/runtime/vault_search.py" \
  --vault "$SK/vault" \
  --concept-index "$SK/_index/concept_index.json" \
  --synonyms "$SK/memory/synonyms.json" \
  --query "sind kleine Bugfixes erlaubt, ohne einen kompletten Rerun?"
```

Expected: a **non-empty ranked JSON list** containing at least one of
`c192-resumable-tasks`, `c192-session-resume`, `c196-task-graph-lifecycle`,
`c126-change-impact-lookup`, `c163-gate-idempotenz`.

Also verify Layer 1 now fires and the regression holds:

```bash
PYTHONPATH="$SK/scripts/lib" python3 "$SK/scripts/runtime/vault_locate.py" \
  --index-dir "$SK/_index" --memory-dir "$SK/memory" \
  "wie funktioniert ein Rerun"        # expect strategy != none
PYTHONPATH="$SK/scripts/lib" python3 "$SK/scripts/runtime/vault_search.py" \
  --vault "$SK/vault" --concept-index "$SK/_index/concept_index.json" \
  --query "Rerun"                      # expect the prior 6 still present
```

If the acceptance list is empty, inspect which concepts the discriminating
tokens (`rerun`, `resume`, `idempotenz`) hit and extend `SYNONYM_GROUPS`
accordingly, then re-run Step 3–4. (Do NOT seed corpus terms into the generator
default — only into the built skill's synonyms.json.)

- [ ] **Step 5: Commit the heal script (generator repo only)**

```bash
git add scripts/heal_adscaile.py
git commit -m "chore: one-off heal script for the built adscaile-expert skill"
```

---

## Self-Review

**Spec coverage:**
- Finding B (tokenize + rank) → Task 1 (helpers) + Task 5 (engine). ✓
- Finding A1 (deterministic aliases) → Task 2 + Task 3. ✓
- Finding A (vault_locate ranking) → Task 6. ✓
- Finding C (synonyms, empty by default) → Task 1 (load/expand) + Task 4 (ship empty) + Task 8 (seed for heal). ✓
- Finding D (SKILL.md guidance + non-suppressing Layer 1) → Task 7. ✓
- Heal existing skill → Task 8. ✓
- Light stemming (spec architecture) → Task 1 `stem`, used in Task 5. ✓
- IDF ranking (spec) → Task 5. ✓
- Synonyms in `memory/` not `_index/` (spec) → Task 4 + Task 7 `--synonyms .../memory/synonyms.json`. ✓
- Regression contract (preserved, not identical) → Task 5 `test_single_keyword_preserves_prior_matches`. ✓
- Over-matching guard → Task 6 `test_short_generic_alias_does_not_collapse_query`. ✓
- Acceptance gate → Task 8 Step 4. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; commands have expected output. ✓

**Type consistency:** `derive_aliases(name, title, tags)` identical in Tasks 2/3/8. `search_vault(..., synonyms_path=None, limit=None)` consistent in Tasks 5/8. `tokenize/stem/load_synonym_groups/build_synonym_index/expand_token` names identical across Tasks 1/5. `_ranked_alias_hits`/`_normalize` consistent within Task 6. ✓

**Deliberate test changes (documented):** Task 5 removes `test_search_falls_back_when_ripgrep_missing` and `test_ripgrep_and_python_paths_agree` because the new engine is pure-Python by design (no ripgrep path); their intent — "works with zero system binaries" and "fallback correctness" — is subsumed by the new pure-Python engine and its kept tests.
