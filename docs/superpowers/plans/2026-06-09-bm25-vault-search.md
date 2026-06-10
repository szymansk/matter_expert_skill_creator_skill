# BM25F Vault Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unranked substring Layer-2 vault search with ranked BM25F retrieval backed by a precomputed `_index/bm25_index.json`.

**Architecture:** A single pure-Python core (`runtime/bm25.py`) provides tokenization, index building, and BM25F scoring, used identically by the offline builder and the query-time runtime. The Emit phase writes `bm25_index.json` alongside the existing 4 indexes; a standalone `runtime/bm25_build.py` rebuilds it when vault content changes. `runtime/vault_search.py` becomes a pure-Python lookup that loads the index, scores, applies the tag filter, and returns ranked Top-N. ripgrep is removed from the query path.

**Tech Stack:** Python 3 stdlib only (json, math, re). pytest. The runtime package must never import third-party libraries.

**Key paths:**
- Lib root (where `runtime/`, `builder/`, `matter_expert/` live): `docs-to-skill/skills/docs-to-skill/scripts/lib/`
- Tests root: `tests/` (pytest `pythonpath` already includes the lib root, so `from runtime.bm25 import ...` resolves).

**Field config (defined once in `runtime/bm25.py`):**
- `FIELDS = ("title", "aliases", "tags", "body")`
- `FIELD_BOOSTS = {"title": 3.0, "aliases": 2.5, "tags": 2.0, "body": 1.0}`
- `FIELD_B = {"title": 0.5, "aliases": 0.5, "tags": 0.5, "body": 0.75}`
- `K1 = 1.2`

**Index JSON shape (`_index/bm25_index.json`):**
```json
{
  "N": 7,
  "fields": ["title", "aliases", "tags", "body"],
  "avg_field_len": {"title": 2.1, "aliases": 0.0, "tags": 2.4, "body": 130.5},
  "doc_field_len": {"oauth2-flow": {"title": 2, "aliases": 0, "tags": 3, "body": 128}},
  "postings": {"oauth2": {"oauth2-flow": {"title": 1, "tags": 1, "body": 4}}}
}
```
(`df` per term is derived at query time as `len(postings[term])` — not stored, to stay DRY.)

---

### Task 1: BM25F tokenizer

**Files:**
- Create: `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py`
- Test: `tests/runtime/test_bm25.py`

- [ ] **Step 1: Write the failing test**

Create `tests/runtime/test_bm25.py`:

```python
from runtime.bm25 import tokenize


def test_tokenize_lowercases_and_splits_on_nonalnum():
    assert tokenize("OAuth2 Flow, refresh-token!") == ["oauth2", "flow", "refresh", "token"]


def test_tokenize_keeps_digits_drops_underscore_and_punctuation():
    assert tokenize("merged_from: v2.0 (RFC-6749)") == ["merged", "from", "v2", "0", "rfc", "6749"]


def test_tokenize_empty_string_returns_empty_list():
    assert tokenize("") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_bm25.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'runtime.bm25'`

- [ ] **Step 3: Write minimal implementation**

Create `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py`:

```python
"""Pure-Python BM25F core: tokenizer, index builder, and scorer.

Shared by the Builder's Emit phase (which writes ``_index/bm25_index.json``)
and the runtime query path (``runtime/vault_search.py``). Stdlib only — this
module is bundled into produced skills and must never import third-party code.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

# --- Field-weighting configuration (single source of truth) --------------
FIELDS: tuple[str, ...] = ("title", "aliases", "tags", "body")
FIELD_BOOSTS: dict[str, float] = {"title": 3.0, "aliases": 2.5, "tags": 2.0, "body": 1.0}
FIELD_B: dict[str, float] = {"title": 0.5, "aliases": 0.5, "tags": 0.5, "body": 0.75}
K1: float = 1.2

# Word characters except underscore: keeps letters and digits, splits the rest.
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lowercase and split text into alphanumeric tokens (digits kept)."""
    return _TOKEN_RE.findall(text.lower())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_bm25.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py tests/runtime/test_bm25.py
git commit -m "feat(bm25): add BM25F tokenizer"
```

---

### Task 2: Frontmatter stripping helper (moved into bm25 core)

**Files:**
- Modify: `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py`
- Test: `tests/runtime/test_bm25.py`

Rationale: `assemble_docs` (Task 4) needs to strip frontmatter; keeping it in `bm25.py` avoids a circular import with `vault_search.py`. `vault_search.py` will re-export it in Task 8 for backward compatibility.

- [ ] **Step 1: Write the failing test**

Append to `tests/runtime/test_bm25.py`:

```python
from runtime.bm25 import strip_frontmatter


def test_strip_frontmatter_removes_block_and_leading_newline():
    text = "---\ntitle: Test\ntags: [a]\n---\nBody starts here\n"
    body = strip_frontmatter(text)
    assert not body.startswith("\n")
    assert body.startswith("Body starts here")


def test_strip_frontmatter_without_frontmatter_is_unchanged():
    assert strip_frontmatter("Just body.") == "Just body."


def test_strip_frontmatter_malformed_returns_whole_text():
    text = "---\ntitle: unclosed frontmatter\n"
    assert strip_frontmatter(text) == text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_bm25.py -k strip_frontmatter -v`
Expected: FAIL with `ImportError: cannot import name 'strip_frontmatter'`

- [ ] **Step 3: Write minimal implementation**

Add to `runtime/bm25.py` (after `tokenize`):

```python
def strip_frontmatter(text: str) -> str:
    """Return only the Markdown body (content after a leading ``---`` block).

    If the file does not start with ``---`` or the block is unterminated, the
    text is returned unchanged.
    """
    if not text.startswith("---"):
        return text
    rest = text[3:]  # skip opening "---"
    close = rest.find("\n---")
    if close == -1:
        return text  # malformed — treat whole file as body
    return rest[close + 4:].lstrip("\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_bm25.py -k strip_frontmatter -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py tests/runtime/test_bm25.py
git commit -m "feat(bm25): add frontmatter-stripping helper"
```

---

### Task 3: Index builder (`build_bm25_index`)

**Files:**
- Modify: `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py`
- Test: `tests/runtime/test_bm25.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/runtime/test_bm25.py`:

```python
from runtime.bm25 import build_bm25_index


def _sample_docs():
    return [
        {"name": "oauth2-flow", "title": "OAuth2 Flow", "aliases": [],
         "tags": ["auth", "oauth2"], "body": "OAuth2 is an authorization framework."},
        {"name": "jwt-tokens", "title": "JWT Tokens", "aliases": ["json web token"],
         "tags": ["auth", "token"], "body": "A JWT is a signed token used for auth."},
    ]


def test_build_index_has_expected_top_level_shape():
    idx = build_bm25_index(_sample_docs())
    assert idx["N"] == 2
    assert idx["fields"] == ["title", "aliases", "tags", "body"]
    assert set(idx["avg_field_len"]) == {"title", "aliases", "tags", "body"}
    assert set(idx["doc_field_len"]) == {"oauth2-flow", "jwt-tokens"}


def test_build_index_postings_count_per_field():
    idx = build_bm25_index(_sample_docs())
    # "oauth2" appears in oauth2-flow's title (1), tags (1), body (1).
    assert idx["postings"]["oauth2"]["oauth2-flow"] == {"title": 1, "tags": 1, "body": 1}
    # "auth" appears in both docs' tags, and in jwt-tokens' body once.
    assert idx["postings"]["auth"]["jwt-tokens"]["tags"] == 1
    assert idx["postings"]["auth"]["jwt-tokens"]["body"] == 1


def test_build_index_doc_field_len_counts_tokens():
    idx = build_bm25_index(_sample_docs())
    assert idx["doc_field_len"]["oauth2-flow"]["title"] == 2  # "oauth2", "flow"
    assert idx["doc_field_len"]["jwt-tokens"]["aliases"] == 3  # "json", "web", "token"


def test_build_index_empty_docs():
    idx = build_bm25_index([])
    assert idx["N"] == 0
    assert idx["postings"] == {}
    assert idx["avg_field_len"] == {"title": 0.0, "aliases": 0.0, "tags": 0.0, "body": 0.0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_bm25.py -k build_index -v`
Expected: FAIL with `ImportError: cannot import name 'build_bm25_index'`

- [ ] **Step 3: Write minimal implementation**

Add to `runtime/bm25.py`:

```python
def build_bm25_index(docs: list[dict]) -> dict:
    """Build a serializable BM25F index from per-concept field documents.

    ``docs`` is a list of dicts with keys ``name``, ``title``, ``aliases``
    (list[str]), ``tags`` (list[str]), and ``body`` (str). Returns a JSON-
    serializable index dict (see module docstring / plan for the shape).
    """
    postings: dict[str, dict[str, dict[str, int]]] = {}
    doc_field_len: dict[str, dict[str, int]] = {}
    field_total: dict[str, int] = {f: 0 for f in FIELDS}

    for doc in docs:
        name = doc["name"]
        field_tokens = {
            "title": tokenize(doc.get("title", "") or ""),
            "aliases": tokenize(" ".join(doc.get("aliases") or [])),
            "tags": tokenize(" ".join(doc.get("tags") or [])),
            "body": tokenize(doc.get("body", "") or ""),
        }
        doc_field_len[name] = {f: len(field_tokens[f]) for f in FIELDS}
        for f in FIELDS:
            field_total[f] += len(field_tokens[f])
            counts: dict[str, int] = {}
            for tok in field_tokens[f]:
                counts[tok] = counts.get(tok, 0) + 1
            for tok, cnt in counts.items():
                postings.setdefault(tok, {}).setdefault(name, {})[f] = cnt

    n = len(docs)
    avg_field_len = {f: (field_total[f] / n if n else 0.0) for f in FIELDS}
    return {
        "N": n,
        "fields": list(FIELDS),
        "avg_field_len": avg_field_len,
        "doc_field_len": doc_field_len,
        "postings": postings,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_bm25.py -k build_index -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py tests/runtime/test_bm25.py
git commit -m "feat(bm25): add field-weighted index builder"
```

---

### Task 4: `assemble_docs` — gather field documents from a vault

**Files:**
- Modify: `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py`
- Test: `tests/runtime/test_bm25.py`

Reads the concept Markdown bodies from `<vault>/concepts/*.md` and pulls
title/tags/aliases from `concept_index.json`. Used by both the runtime auto-build
path and the standalone rebuild script.

- [ ] **Step 1: Write the failing test**

Append to `tests/runtime/test_bm25.py`:

```python
import json
from pathlib import Path

from runtime.bm25 import assemble_docs


def test_assemble_docs_merges_body_and_index_metadata(tmp_path: Path):
    vault = tmp_path / "vault"
    concepts = vault / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "oauth2-flow.md").write_text(
        "---\ntitle: OAuth2 Flow\ntags: [auth]\n---\nOAuth2 body text.\n",
        encoding="utf-8",
    )
    index_dir = tmp_path / "_index"
    index_dir.mkdir()
    concept_index = index_dir / "concept_index.json"
    concept_index.write_text(json.dumps({
        "oauth2-flow": {"title": "OAuth2 Flow", "tags": ["auth", "oauth2"], "aliases": ["oauth"]},
    }), encoding="utf-8")

    docs = assemble_docs(vault, concept_index)
    assert len(docs) == 1
    doc = docs[0]
    assert doc["name"] == "oauth2-flow"
    assert doc["title"] == "OAuth2 Flow"
    assert doc["tags"] == ["auth", "oauth2"]
    assert doc["aliases"] == ["oauth"]
    assert doc["body"].startswith("OAuth2 body text")
    assert "title:" not in doc["body"]  # frontmatter stripped


def test_assemble_docs_handles_concept_absent_from_index(tmp_path: Path):
    vault = tmp_path / "vault"
    concepts = vault / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "orphan.md").write_text("---\ntitle: X\n---\nBody.\n", encoding="utf-8")
    index_dir = tmp_path / "_index"
    index_dir.mkdir()
    concept_index = index_dir / "concept_index.json"
    concept_index.write_text("{}", encoding="utf-8")

    docs = assemble_docs(vault, concept_index)
    assert docs[0]["name"] == "orphan"
    assert docs[0]["title"] == ""
    assert docs[0]["tags"] == []
    assert docs[0]["aliases"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_bm25.py -k assemble_docs -v`
Expected: FAIL with `ImportError: cannot import name 'assemble_docs'`

- [ ] **Step 3: Write minimal implementation**

Add to `runtime/bm25.py`:

```python
def assemble_docs(vault_dir: Path, concept_index_path: Path) -> list[dict]:
    """Build BM25 field documents from a vault and its concept index.

    Bodies come from ``<vault_dir>/concepts/*.md`` (frontmatter stripped);
    title/tags/aliases come from ``concept_index.json``.
    """
    vault_dir = Path(vault_dir)
    concept_index_path = Path(concept_index_path)
    index = json.loads(concept_index_path.read_text(encoding="utf-8"))
    concepts_dir = vault_dir / "concepts"
    docs: list[dict] = []
    for md_file in sorted(concepts_dir.glob("*.md")):
        name = md_file.stem
        entry = index.get(name, {})
        docs.append({
            "name": name,
            "title": entry.get("title", ""),
            "aliases": list(entry.get("aliases", [])),
            "tags": list(entry.get("tags", [])),
            "body": strip_frontmatter(md_file.read_text(encoding="utf-8")),
        })
    return docs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_bm25.py -k assemble_docs -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py tests/runtime/test_bm25.py
git commit -m "feat(bm25): assemble field documents from a vault"
```

---

### Task 5: BM25F scorer (`BM25Index`)

**Files:**
- Modify: `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py`
- Test: `tests/runtime/test_bm25.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/runtime/test_bm25.py`:

```python
from runtime.bm25 import BM25Index, build_bm25_index


def _index_from(docs):
    return BM25Index.from_dict(build_bm25_index(docs))


def test_score_ranks_relevant_concept_first():
    docs = [
        {"name": "oauth2-flow", "title": "OAuth2 Flow", "aliases": [],
         "tags": ["oauth2"], "body": "OAuth2 OAuth2 OAuth2 authorization."},
        {"name": "jwt-tokens", "title": "JWT Tokens", "aliases": [],
         "tags": ["token"], "body": "A token mentions oauth2 once in passing."},
    ]
    ranked = _index_from(docs).score("oauth2")
    assert ranked[0][0] == "oauth2-flow"
    assert [n for n, _ in ranked][:2] == ["oauth2-flow", "jwt-tokens"]


def test_title_hit_outranks_body_only_hit():
    docs = [
        {"name": "bernoulli-principle", "title": "Bernoulli Principle", "aliases": [],
         "tags": [], "body": "Pressure and velocity relationship."},
        {"name": "lift-generation", "title": "Lift Generation", "aliases": [],
         "tags": [], "body": "Lift is sometimes explained via bernoulli effects."},
    ]
    ranked = _index_from(docs).score("bernoulli")
    assert ranked[0][0] == "bernoulli-principle"


def test_multi_term_query_prefers_doc_matching_more_terms():
    docs = [
        {"name": "both", "title": "", "aliases": [], "tags": [],
         "body": "alpha beta appear together here."},
        {"name": "one", "title": "", "aliases": [], "tags": [],
         "body": "alpha appears but the other term does not."},
    ]
    ranked = _index_from(docs).score("alpha beta")
    assert ranked[0][0] == "both"


def test_score_no_matching_terms_returns_empty():
    docs = [{"name": "x", "title": "T", "aliases": [], "tags": [], "body": "hello world"}]
    assert _index_from(docs).score("zzzznope") == []


def test_score_top_n_truncates():
    docs = [
        {"name": f"c{i}", "title": "", "aliases": [], "tags": [], "body": "common term"}
        for i in range(5)
    ]
    ranked = _index_from(docs).score("common", top_n=2)
    assert len(ranked) == 2


def test_score_is_deterministic_on_ties():
    docs = [
        {"name": "b-concept", "title": "", "aliases": [], "tags": [], "body": "term"},
        {"name": "a-concept", "title": "", "aliases": [], "tags": [], "body": "term"},
    ]
    ranked = _index_from(docs).score("term")
    # Equal scores → tie-break alphabetically by name.
    assert [n for n, _ in ranked] == ["a-concept", "b-concept"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_bm25.py -k "score or BM25Index" -v`
Expected: FAIL with `ImportError: cannot import name 'BM25Index'`

- [ ] **Step 3: Write minimal implementation**

Add to `runtime/bm25.py`:

```python
@dataclass
class BM25Index:
    """In-memory BM25F index loaded from ``bm25_index.json``."""

    n: int
    fields: tuple[str, ...]
    avg_field_len: dict[str, float]
    doc_field_len: dict[str, dict[str, int]]
    postings: dict[str, dict[str, dict[str, int]]]

    @classmethod
    def from_dict(cls, data: dict) -> "BM25Index":
        return cls(
            n=data["N"],
            fields=tuple(data["fields"]),
            avg_field_len=data["avg_field_len"],
            doc_field_len=data["doc_field_len"],
            postings=data["postings"],
        )

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def score(self, query: str, top_n: int | None = None) -> list[tuple[str, float]]:
        """Return ``(concept_name, score)`` pairs ranked by BM25F, best first.

        Ties are broken alphabetically by concept name for determinism.
        """
        scores: dict[str, float] = {}
        for term in set(tokenize(query)):
            plist = self.postings.get(term)
            if not plist:
                continue
            df = len(plist)
            idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
            for name, field_counts in plist.items():
                tf_prime = 0.0
                for field, cnt in field_counts.items():
                    avg = self.avg_field_len.get(field) or 1.0
                    length = self.doc_field_len[name].get(field, 0)
                    denom = 1.0 - FIELD_B[field] + FIELD_B[field] * (length / avg)
                    tf_prime += FIELD_BOOSTS[field] * cnt / denom
                scores[name] = scores.get(name, 0.0) + idf * tf_prime / (K1 + tf_prime)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:top_n] if top_n is not None else ranked
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_bm25.py -k "score or BM25Index" -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Run the whole bm25 test file**

Run: `pytest tests/runtime/test_bm25.py -v`
Expected: PASS (all tasks 1–5 tests green)

- [ ] **Step 6: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25.py tests/runtime/test_bm25.py
git commit -m "feat(bm25): add BM25F scorer with field boosts"
```

---

### Task 6: Add `bm25_index` to `IndexPaths`

**Files:**
- Modify: `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/index.py`
- Test: `tests/runtime/test_index.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/runtime/test_index.py`:

```python
def test_index_paths_exposes_bm25_index():
    from pathlib import Path
    from runtime.index import IndexPaths
    paths = IndexPaths(index_dir=Path("/tmp/_index"))
    assert paths.bm25_index == Path("/tmp/_index/bm25_index.json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_index.py::test_index_paths_exposes_bm25_index -v`
Expected: FAIL with `AttributeError: 'IndexPaths' object has no attribute 'bm25_index'`

- [ ] **Step 3: Write minimal implementation**

In `runtime/index.py`, add a property to the `IndexPaths` dataclass (after `alias_map`):

```python
    @property
    def bm25_index(self) -> Path:
        return self.index_dir / "bm25_index.json"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_index.py::test_index_paths_exposes_bm25_index -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/index.py tests/runtime/test_index.py
git commit -m "feat(index): add bm25_index path to IndexPaths"
```

---

### Task 7: Emit phase writes `bm25_index.json`

**Files:**
- Modify: `docs-to-skill/skills/docs-to-skill/scripts/lib/builder/emit/index_builder.py`
- Test: `tests/builder/emit/test_index_builder.py` (create if absent)

> Note: aliases are passed as `[]` here, matching the current pipeline (concept
> frontmatter has no alias field and `concept_index` aliases are empty). The
> runtime rebuild path (`assemble_docs`) already reads aliases from the index,
> so alias indexing activates automatically once aliases are populated upstream.

- [ ] **Step 1: Write the failing test**

Create or append to `tests/builder/emit/test_index_builder.py`:

```python
import json
from pathlib import Path

from matter_expert import VaultPaths
from builder.emit.index_builder import build_indexes


def test_build_indexes_writes_bm25_index(example_vault_paths: VaultPaths, tmp_path: Path):
    index_dir = tmp_path / "_index"
    build_indexes(example_vault_paths, index_dir)

    bm25_path = index_dir / "bm25_index.json"
    assert bm25_path.exists(), "Emit must write bm25_index.json"
    data = json.loads(bm25_path.read_text(encoding="utf-8"))
    assert data["N"] >= 1
    assert data["fields"] == ["title", "aliases", "tags", "body"]
    # A known token from the example vault must be indexed.
    assert "oauth2" in data["postings"]
    assert "oauth2-flow" in data["postings"]["oauth2"]
```

If `tests/builder/emit/` has no `conftest.py` providing `example_vault_paths`,
verify the fixture is available from the root `tests/conftest.py` first:

Run: `grep -rn "def example_vault_paths" tests/`
If it is only defined under `tests/runtime/conftest.py`, add the same fixture to
`tests/conftest.py` (root) so builder tests can use it. The fixture body:

```python
import pytest
from pathlib import Path
from matter_expert import VaultPaths

@pytest.fixture
def example_vault_paths() -> VaultPaths:
    return VaultPaths(root=Path(__file__).parent / "fixtures" / "example_vault")
```

(Only add it if `grep` shows it is not already resolvable from the root conftest.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/emit/test_index_builder.py::test_build_indexes_writes_bm25_index -v`
Expected: FAIL — `bm25_index.json` does not exist.

- [ ] **Step 3: Write minimal implementation**

In `builder/emit/index_builder.py`, add the import at the top:

```python
import json

from runtime.bm25 import build_bm25_index
```

Then at the end of `build_indexes()` (after the alias_map write), add:

```python
    # BM25F index for Layer-2 ranked search.
    bm25_docs = [
        {
            "name": name,
            "title": page.frontmatter.title,
            "aliases": [],
            "tags": list(page.frontmatter.tags),
            "body": page.body,
        }
        for name, page in concept_pages.items()
    ]
    (index_dir / "bm25_index.json").write_text(
        json.dumps(build_bm25_index(bm25_docs), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/builder/emit/test_index_builder.py::test_build_indexes_writes_bm25_index -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/builder/emit/index_builder.py tests/builder/emit/test_index_builder.py tests/conftest.py
git commit -m "feat(emit): write bm25_index.json during index build"
```

---

### Task 8: Rewrite `vault_search.py` to use the BM25 index

**Files:**
- Modify: `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/vault_search.py`
- Test: `tests/runtime/test_vault_search.py` (rewritten in Task 10)

This task rewrites the module; its behavior is verified by the rewritten tests in
Task 10. Implement the module fully here.

- [ ] **Step 1: Replace the file contents**

Overwrite `runtime/vault_search.py` with:

```python
"""Layer 2 retrieval: ranked BM25F search over a precomputed index.

Loads ``_index/bm25_index.json`` (built by the Emit phase or rebuilt with
``runtime/bm25_build.py``) and returns concept names ranked by relevance.
An optional tag filter narrows results to concepts whose frontmatter tags
match. Pure Python — no system binaries required at query time.

If the index is missing it is built once automatically. If the vault has been
modified more recently than the index a staleness warning is printed to stderr.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# When executed directly from a bundled plugin, runtime/ sits inside scripts/.
_HERE = Path(__file__).resolve().parent
if _HERE.name == "runtime":
    _scripts = _HERE.parent
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))

from runtime.bm25 import (
    BM25Index,
    assemble_docs,
    build_bm25_index,
    strip_frontmatter,  # re-exported for backward compatibility
)
from runtime.index import load_concept_index

# Backward-compatible alias: older callers/tests import this private name.
_strip_frontmatter = strip_frontmatter

DEFAULT_TOP_N = 10


def _vault_newer_than(vault_dir: Path, index_path: Path) -> bool:
    """True if any concept file is newer than the index file."""
    idx_mtime = index_path.stat().st_mtime
    for md_file in (vault_dir / "concepts").glob("*.md"):
        if md_file.stat().st_mtime > idx_mtime:
            return True
    return False


def _load_or_build_index(
    index_path: Path, vault_dir: Path, concept_index_path: Path
) -> BM25Index:
    if not index_path.exists():
        print("bm25: index missing — building it now.", file=sys.stderr)
        data = build_bm25_index(assemble_docs(vault_dir, concept_index_path))
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        return BM25Index.from_dict(data)
    if _vault_newer_than(vault_dir, index_path):
        print(
            "bm25: index may be stale; run bm25_build.py to refresh.",
            file=sys.stderr,
        )
    return BM25Index.load(index_path)


def _ranked_with_scores(
    query: str,
    vault_dir: Path,
    concept_index_path: Path,
    tags: list[str] | None,
    top_n: int | None,
    bm25_index_path: Path | None,
) -> list[tuple[str, float]]:
    if bm25_index_path is None:
        bm25_index_path = concept_index_path.parent / "bm25_index.json"
    index = _load_or_build_index(bm25_index_path, vault_dir, concept_index_path)
    ranked = index.score(query)  # full ranking; truncate after tag filter

    if tags:
        concept_index = load_concept_index(concept_index_path)
        wanted = set(tags)
        ranked = [
            (name, score)
            for name, score in ranked
            if name in concept_index
            and wanted.intersection(concept_index[name].get("tags", []))
        ]
    return ranked[:top_n] if top_n is not None else ranked


def search_vault(
    query: str,
    vault_dir: Path,
    concept_index_path: Path,
    tags: list[str] | None = None,
    top_n: int | None = DEFAULT_TOP_N,
    bm25_index_path: Path | None = None,
) -> list[str]:
    """Return concept names ranked by BM25F relevance (best first).

    Results are restricted to concepts carrying at least one of ``tags`` when
    given, and truncated to ``top_n`` (pass ``None`` for all hits).
    """
    ranked = _ranked_with_scores(
        query, vault_dir, concept_index_path, tags, top_n, bm25_index_path
    )
    return [name for name, _score in ranked]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ranked BM25F vault search.")
    parser.add_argument("--vault", type=Path, required=True, help="Vault root directory")
    parser.add_argument("--concept-index", type=Path, required=True,
                        help="Path to concept_index.json")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--tags", default="",
                        help="Comma-separated list of tags to filter by")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                        help="Maximum number of ranked results (0 = all)")
    parser.add_argument("--scores", action="store_true",
                        help="Output [{name, score}] instead of a name list")
    parser.add_argument("--index", type=Path, default=None,
                        help="Path to bm25_index.json (default: beside concept-index)")
    args = parser.parse_args(argv)

    tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    top_n = args.top_n if args.top_n > 0 else None

    ranked = _ranked_with_scores(
        query=args.query,
        vault_dir=args.vault,
        concept_index_path=args.concept_index,
        tags=tag_list or None,
        top_n=top_n,
        bm25_index_path=args.index,
    )

    if args.scores:
        payload = [{"name": name, "score": score} for name, score in ranked]
    else:
        payload = [name for name, _score in ranked]
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Quick import sanity check**

Run: `python3 -c "import sys; sys.path.insert(0,'docs-to-skill/skills/docs-to-skill/scripts/lib'); import runtime.vault_search; print('ok')"`
Expected: prints `ok` (no import errors). Behavioral verification happens in Task 10.

- [ ] **Step 3: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/vault_search.py
git commit -m "feat(search): rank Layer-2 results with BM25F index"
```

---

### Task 9: Standalone rebuild script `bm25_build.py`

**Files:**
- Create: `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25_build.py`
- Test: `tests/runtime/test_bm25_build.py`

- [ ] **Step 1: Write the failing test**

Create `tests/runtime/test_bm25_build.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.bm25_build import main as bm25_build_main


def _make_vault(tmp_path: Path):
    vault = tmp_path / "vault"
    concepts = vault / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "oauth2-flow.md").write_text(
        "---\ntitle: OAuth2 Flow\ntags: [auth]\n---\nOAuth2 authorization body.\n",
        encoding="utf-8",
    )
    index_dir = tmp_path / "_index"
    index_dir.mkdir()
    concept_index = index_dir / "concept_index.json"
    concept_index.write_text(json.dumps({
        "oauth2-flow": {"title": "OAuth2 Flow", "tags": ["auth"], "aliases": []},
    }), encoding="utf-8")
    return vault, concept_index, index_dir


def test_bm25_build_writes_index_beside_concept_index(tmp_path: Path):
    vault, concept_index, index_dir = _make_vault(tmp_path)
    rc = bm25_build_main(["--vault", str(vault), "--concept-index", str(concept_index)])
    assert rc == 0
    out = index_dir / "bm25_index.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "oauth2" in data["postings"]


def test_bm25_build_honors_explicit_out(tmp_path: Path):
    vault, concept_index, _ = _make_vault(tmp_path)
    out = tmp_path / "custom" / "bm25.json"
    rc = bm25_build_main([
        "--vault", str(vault), "--concept-index", str(concept_index), "--out", str(out),
    ])
    assert rc == 0
    assert out.exists()


def test_bm25_build_cli_runs_as_module(tmp_path: Path):
    vault, concept_index, index_dir = _make_vault(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "runtime.bm25_build",
         "--vault", str(vault), "--concept-index", str(concept_index)],
        capture_output=True, text=True, check=True,
    )
    assert (index_dir / "bm25_index.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_bm25_build.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'runtime.bm25_build'`

- [ ] **Step 3: Write minimal implementation**

Create `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25_build.py`:

```python
"""Rebuild ``bm25_index.json`` for a vault.

Run this after adding or editing concept pages so Layer-2 search reflects the
new content. Pure Python — no system binaries required.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# When executed directly from a bundled plugin, runtime/ sits inside scripts/.
_HERE = Path(__file__).resolve().parent
if _HERE.name == "runtime":
    _scripts = _HERE.parent
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))

from runtime.bm25 import assemble_docs, build_bm25_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the BM25 vault index.")
    parser.add_argument("--vault", type=Path, required=True, help="Vault root directory")
    parser.add_argument("--concept-index", type=Path, required=True,
                        help="Path to concept_index.json")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output path (default: bm25_index.json beside concept-index)")
    args = parser.parse_args(argv)

    out = args.out or args.concept_index.parent / "bm25_index.json"
    data = build_bm25_index(assemble_docs(args.vault, args.concept_index))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    print(f"wrote {out} ({data['N']} concepts, {len(data['postings'])} terms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_bm25_build.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/bm25_build.py tests/runtime/test_bm25_build.py
git commit -m "feat(bm25): add standalone bm25_build rebuild script"
```

---

### Task 10: Rewrite `test_vault_search.py` for ranking + update conftest

**Files:**
- Modify: `tests/runtime/conftest.py`
- Modify (overwrite): `tests/runtime/test_vault_search.py`

The `built_indexes` fixture must now also write `bm25_index.json`, since
`search_vault` reads it (it would otherwise auto-build, which also works, but the
fixture should mirror the real Emit output and the `IndexBundle` should expose it).

- [ ] **Step 1: Update the `built_indexes` fixture**

In `tests/runtime/conftest.py`:

(a) Add a field to the `IndexBundle` dataclass:

```python
@dataclass(frozen=True)
class IndexBundle:
    """The set of paths to the JSON index files used at runtime."""

    index_dir: Path
    concept_index: Path
    moc_map: Path
    link_graph: Path
    alias_map: Path
    bm25_index: Path
```

(b) At the top of the file, add the import:

```python
import json
from runtime.bm25 import build_bm25_index
```

(c) In the `built_indexes` fixture, after the `alias_map.write(...)` line and
before the `return IndexBundle(...)`, add:

```python
    # BM25F index — mirrors the Emit phase output.
    bm25_docs = [
        {
            "name": name,
            "title": page.frontmatter.title,
            "aliases": [],
            "tags": list(page.frontmatter.tags),
            "body": page.body,
        }
        for name, page in concept_pages.items()
    ]
    (index_dir / "bm25_index.json").write_text(
        json.dumps(build_bm25_index(bm25_docs), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
```

(d) Update the `return IndexBundle(...)` to include the new path:

```python
    return IndexBundle(
        index_dir=index_dir,
        concept_index=index_dir / "concept_index.json",
        moc_map=index_dir / "moc_map.json",
        link_graph=index_dir / "link_graph.json",
        alias_map=index_dir / "alias_map.json",
        bm25_index=index_dir / "bm25_index.json",
    )
```

- [ ] **Step 2: Overwrite `tests/runtime/test_vault_search.py`**

Replace the entire file with:

```python
import json
import subprocess
import sys
from pathlib import Path

from runtime.vault_search import search_vault


def test_search_finds_concept_with_keyword(vault_dir: Path, built_indexes):
    matches = search_vault(
        query="OAuth2",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert "oauth2-flow" in matches


def test_search_ranks_strong_match_first(vault_dir: Path, built_indexes):
    """'session' hits session-management in title + tags + body, so it ranks #1.

    (Verified empirically against the example vault: 'session' returns only
    session-management.)
    """
    matches = search_vault(
        query="session",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert matches[0] == "session-management"


def test_search_returns_empty_for_no_matches(vault_dir: Path, built_indexes):
    # Single nonsense token — must tokenize to one term that is in no field.
    # (Do NOT use a multi-word phrase: common words like "in"/"not" would match.)
    matches = search_vault(
        query="zzzznonexistentterm",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert matches == []


def test_search_filters_by_tag(vault_dir: Path, built_indexes):
    matches = search_vault(
        query="auth",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
        tags=["oauth2"],
    )
    for m in matches:
        assert m in {"oauth2-flow", "oauth2-google-flow"}


def test_search_excludes_frontmatter_content(vault_dir: Path, built_indexes):
    """Frontmatter is not indexed.

    Every concept's frontmatter has a `created: 2026-..` date, but the token
    "2026" appears in no body/title/tag — so if frontmatter were indexed this
    would match all concepts; it must return [].
    """
    matches = search_vault(
        query="2026",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert matches == []


def test_search_top_n_truncates(vault_dir: Path, built_indexes):
    matches = search_vault(
        query="auth",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
        top_n=2,
    )
    assert len(matches) <= 2


def test_search_auto_builds_index_when_missing(vault_dir: Path, built_indexes):
    """Deleting the index should trigger an automatic rebuild, not a crash."""
    built_indexes.bm25_index.unlink()
    matches = search_vault(
        query="OAuth2",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert "oauth2-flow" in matches
    assert built_indexes.bm25_index.exists()


def test_cli_outputs_ranked_json_list(vault_dir: Path, built_indexes):
    result = subprocess.run(
        [sys.executable, "-m", "runtime.vault_search",
         "--vault", str(vault_dir),
         "--concept-index", str(built_indexes.concept_index),
         "--query", "OAuth2"],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    assert "oauth2-flow" in parsed


def test_cli_scores_flag_outputs_name_score_objects(vault_dir: Path, built_indexes):
    result = subprocess.run(
        [sys.executable, "-m", "runtime.vault_search",
         "--vault", str(vault_dir),
         "--concept-index", str(built_indexes.concept_index),
         "--query", "google", "--scores"],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    assert parsed and set(parsed[0]) == {"name", "score"}
    # 'google' is a unique term: only oauth2-google-flow matches it.
    assert parsed[0]["name"] == "oauth2-google-flow"


def test_search_corrupt_index_raises_clear_error(vault_dir: Path, built_indexes):
    """A corrupt bm25_index.json yields a ValueError naming the file, not a
    bare JSONDecodeError."""
    import pytest
    built_indexes.bm25_index.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt index"):
        search_vault(
            query="oauth2",
            vault_dir=vault_dir,
            concept_index_path=built_indexes.concept_index,
        )


def test_strip_frontmatter_still_importable_from_vault_search():
    """Backward-compatible re-export of the frontmatter helper."""
    from runtime.vault_search import _strip_frontmatter
    text = "---\ntitle: Test\n---\nBody starts here\n"
    assert _strip_frontmatter(text).startswith("Body starts here")
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/runtime/test_vault_search.py -v`
Expected: PASS (all tests green)

- [ ] **Step 4: Commit**

```bash
git add tests/runtime/conftest.py tests/runtime/test_vault_search.py
git commit -m "test(search): cover BM25F ranking, top-n, scores, auto-build"
```

---

### Task 11: Ship `bm25.py` + `bm25_build.py` in produced skills

**Files:**
- Modify: `tests/builder/emit/test_runtime_bundler.py`

The bundler copies the whole `runtime/` tree, so no production change is needed —
this task adds assertions that the new modules ship (and would catch a future
`ignore`-rule regression).

- [ ] **Step 1: Write the failing test**

In `tests/builder/emit/test_runtime_bundler.py`, inside
`test_bundle_runtime_copies_runtime_package`, add after the existing
`assert (runtime / "memory_inspect.py").exists()` line:

```python
    assert (runtime / "bm25.py").exists()
    assert (runtime / "bm25_build.py").exists()
```

- [ ] **Step 2: Run test to verify it passes (modules already exist)**

Run: `pytest tests/builder/emit/test_runtime_bundler.py -v`
Expected: PASS — the files exist (created in Tasks 1 and 9), so the bundler ships them.

> If this fails because the files are absent, Tasks 1/9 were not completed —
> stop and finish them first.

- [ ] **Step 3: Commit**

```bash
git add tests/builder/emit/test_runtime_bundler.py
git commit -m "test(emit): assert bm25 modules are bundled into produced skills"
```

---

### Task 12: Emit `--top-n` in the generated SKILL.md

**Files:**
- Modify: `docs-to-skill/skills/docs-to-skill/scripts/lib/builder/emit/skill_md.py:49-55`
- Test: `tests/builder/emit/test_skill_md.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/builder/emit/test_skill_md.py` (reuse the existing
`canned_agent` fixture and `generate_skill_md` / `SkillMdMeta` imports already
present in that file):

```python
def test_skill_md_layer2_passes_top_n(tmp_path: Path, canned_agent):
    skill_dir = tmp_path / "skills" / "x"
    skill_dir.mkdir(parents=True)
    path = generate_skill_md(
        skill_dir=skill_dir,
        meta=SkillMdMeta(skill_name="x", dominant_topics=["topic"]),
        agent=canned_agent,
    )
    content = path.read_text(encoding="utf-8")
    search_idx = content.index("vault_search.py")
    search_block = content[search_idx:search_idx + 400]
    assert "--top-n" in search_block
```

If `Path`, `generate_skill_md`, `SkillMdMeta`, or `canned_agent` are not already
imported/defined at the top of the test file, mirror the imports used by the
existing tests in the same file.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/emit/test_skill_md.py::test_skill_md_layer2_passes_top_n -v`
Expected: FAIL — `--top-n` is not in the Layer-2 block.

- [ ] **Step 3: Update the template**

In `builder/emit/skill_md.py`, the Layer-2 block currently reads:

```python
   python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/vault_search.py" \\
     --vault "${{CLAUDE_SKILL_DIR}}/vault" \\
     --concept-index "${{CLAUDE_SKILL_DIR}}/_index/concept_index.json" \\
     --query "<keyword>"
```

Change the last line to add `--top-n` and update the surrounding prose to mention
ranking. Replace those lines with:

```python
   python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/vault_search.py" \\
     --vault "${{CLAUDE_SKILL_DIR}}/vault" \\
     --concept-index "${{CLAUDE_SKILL_DIR}}/_index/concept_index.json" \\
     --query "<keyword>" \\
     --top-n 10
```

Also update the Layer-2 heading text from
`**Layer 2 — Keyword search (if Layer 1 yielded nothing useful).** Run:`
to
`**Layer 2 — Ranked BM25 search (if Layer 1 yielded nothing useful).** Returns concepts ranked by relevance, best first. Run:`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/builder/emit/test_skill_md.py -v`
Expected: PASS (new test green, existing skill_md tests still green)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/builder/emit/skill_md.py tests/builder/emit/test_skill_md.py
git commit -m "feat(emit): SKILL.md documents ranked BM25 search with --top-n"
```

---

### Task 13: Update runtime package exports and docstring

**Files:**
- Modify: `docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/__init__.py`
- Test: `tests/runtime/test_public_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/runtime/test_public_api.py`:

```python
def test_runtime_exports_bm25_helpers():
    from runtime import build_bm25_index, BM25Index, tokenize
    assert callable(build_bm25_index)
    assert callable(tokenize)
    assert isinstance(BM25Index, type)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_public_api.py::test_runtime_exports_bm25_helpers -v`
Expected: FAIL with `ImportError: cannot import name 'build_bm25_index' from 'runtime'`

- [ ] **Step 3: Update `runtime/__init__.py`**

(a) Update the module docstring: replace the sentence block that claims ripgrep
is used (the paragraph mentioning `ripgrep` / "falls back to a pure-Python scan")
with:

```python
"""Runtime engine for the generated expert skill — stdlib only.

This package is bundled into the generated expert-skill plugin.
It must never import third-party libraries — Python standard library only.
Layer-2 search ranks results with a precomputed BM25F index
(``_index/bm25_index.json``); no system binaries are required at query time.
"""
```

(b) Add the import (next to the other `from runtime.xxx import` lines):

```python
from runtime.bm25 import build_bm25_index, BM25Index, tokenize
```

(c) Add the names to `__all__`:

```python
    "build_bm25_index", "BM25Index", "tokenize",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_public_api.py -v`
Expected: PASS (existing export test + new bm25 export test green)

- [ ] **Step 5: Commit**

```bash
git add docs-to-skill/skills/docs-to-skill/scripts/lib/runtime/__init__.py tests/runtime/test_public_api.py
git commit -m "feat(runtime): export BM25 helpers; drop ripgrep claim from docstring"
```

---

### Task 14: Full suite + integration sanity

**Files:**
- None (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `pytest`
Expected: all tests pass. If any pre-existing test references the old search
behavior (ripgrep fast/fallback path, alphabetical ordering), fix it to match the
ranked BM25 behavior — the search contract is now "ranked list, best first,
truncated to top-n".

- [ ] **Step 2: End-to-end smoke check on the example vault**

First build all indexes (this exercises the Task 7 emit path and produces
`bm25_index.json`):
```bash
PYTHONPATH=docs-to-skill/skills/docs-to-skill/scripts/lib python3 - <<'PY'
from pathlib import Path
from matter_expert import VaultPaths
from builder.emit.index_builder import build_indexes
out = Path("/tmp/bm25_smoke_index")
build_indexes(VaultPaths(root=Path("tests/fixtures/example_vault")), out)
print("built indexes:", sorted(p.name for p in out.iterdir()))
PY
```
Expected: the printed list includes `bm25_index.json` alongside the other 4.

Next confirm the standalone rebuild script regenerates it (exercises Task 9):
```bash
PYTHONPATH=docs-to-skill/skills/docs-to-skill/scripts/lib \
  python3 -m runtime.bm25_build \
  --vault tests/fixtures/example_vault \
  --concept-index /tmp/bm25_smoke_index/concept_index.json; echo "exit=$?"
```
Expected: prints `wrote .../bm25_index.json (...)` and `exit=0`.

Then query it (exercises Task 8):
```bash
PYTHONPATH=docs-to-skill/skills/docs-to-skill/scripts/lib \
  python3 -m runtime.vault_search \
  --vault tests/fixtures/example_vault \
  --concept-index /tmp/bm25_smoke_index/concept_index.json \
  --query "oauth2" --scores
```
Expected: JSON list of `{name, score}` with `oauth2-flow` ranked at or near the top.

- [ ] **Step 3: Commit (if any fixes were needed in Step 1)**

```bash
git add -A
git commit -m "test: align remaining tests with ranked BM25 search"
```

---

## Notes for the implementer

- **DRY:** `build_bm25_index`, `assemble_docs`, `tokenize`, and `strip_frontmatter`
  live only in `runtime/bm25.py`. Both the Emit phase and the runtime query/rebuild
  paths import from there — never duplicate tokenization.
- **YAGNI (do not add):** query-time ripgrep, stemming, stopword lists, phrase/fuzzy
  queries, incremental index updates.
- **Determinism:** always serialize the index with `json.dumps(..., sort_keys=True)`;
  score ties break alphabetically by concept name.
- **Stdlib only in `runtime/`:** `bm25.py` and `bm25_build.py` must import nothing
  beyond `json`, `math`, `re`, `argparse`, `sys`, `dataclasses`, `pathlib`.
