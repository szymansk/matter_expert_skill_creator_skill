# Transform Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Build the Transform phase of the docs-to-skill builder — converts raw markdown documents (from Ingest) into translated, concept-chunked vault pages with frontmatter.

**Architecture:** Inside `src/builder/transform/`. Three agents per source document (analyzer → extractor → coverage-checker), each using the AgentCaller protocol from SP4. Tests use mocked agents that return canned JSON for analysis and canned markdown for extraction. The orchestrator integrates with the Pipeline framework.

**Tech Stack:** Python 3.11+ stdlib + matter_expert library (for ConceptFrontmatter, Source, ConceptPage).

---

## File Structure

```
src/builder/transform/
├── __init__.py
├── outline.py            # ConceptOutline + OutlineEntry dataclasses
├── analyzer.py           # ConceptAnalyzer — Haiku/low → JSON outline
├── extractor.py          # ConceptExtractor — Haiku/medium → vault page content
├── coverage.py           # CoverageChecker — Haiku/low → finds missed concepts
├── prompts.py            # Prompt templates (analyzer/extractor/coverage)
├── chunk_size.py         # validate_chunk_size helper (500-2000 tokens)
└── orchestrator.py       # TransformOrchestrator — wires everything to Pipeline

tests/builder/transform/
├── __init__.py
├── conftest.py           # MockAnalysisAgent, MockExtractionAgent, etc.
├── test_outline.py
├── test_analyzer.py
├── test_extractor.py
├── test_coverage.py
├── test_chunk_size.py
└── test_orchestrator.py
```

---

## Task 1: Package Scaffolding + ConceptOutline

**Files:**
- Create: `src/builder/transform/__init__.py` (empty)
- Create: `src/builder/transform/outline.py`
- Create: `tests/builder/transform/__init__.py` (empty)
- Create: `tests/builder/transform/test_outline.py`

- [ ] **Step 1: Write failing test `tests/builder/transform/test_outline.py`**

```python
from builder.transform.outline import ConceptOutline, OutlineEntry


def test_outline_entry_construction():
    entry = OutlineEntry(
        concept_name="oauth2-flow",
        title="OAuth2 Flow",
        source_sections=["3.1", "3.2"],
        estimated_tokens=1200,
    )
    assert entry.concept_name == "oauth2-flow"
    assert entry.estimated_tokens == 1200


def test_outline_entry_round_trip():
    entry = OutlineEntry(
        concept_name="x",
        title="X",
        source_sections=["1.1"],
        estimated_tokens=500,
    )
    assert OutlineEntry.from_dict(entry.to_dict()) == entry


def test_concept_outline_round_trip():
    outline = ConceptOutline(entries=[
        OutlineEntry(concept_name="a", title="A",
                     source_sections=[], estimated_tokens=600),
        OutlineEntry(concept_name="b", title="B",
                     source_sections=["2.1"], estimated_tokens=1200),
    ])
    assert ConceptOutline.from_dict(outline.to_dict()) == outline


def test_concept_outline_iteration():
    outline = ConceptOutline(entries=[
        OutlineEntry(concept_name="a", title="A",
                     source_sections=[], estimated_tokens=100),
    ])
    names = [e.concept_name for e in outline]
    assert names == ["a"]
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/transform/outline.py`**

```python
"""Concept outline produced by the analyzer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OutlineEntry:
    """One concept identified during source-document analysis."""
    concept_name: str           # filename-stem form: "oauth2-flow"
    title: str                  # display title: "OAuth2 Flow"
    source_sections: list[str]  # e.g. ["3.1", "3.2"]
    estimated_tokens: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutlineEntry":
        return cls(
            concept_name=data["concept_name"],
            title=data["title"],
            source_sections=list(data.get("source_sections", [])),
            estimated_tokens=int(data["estimated_tokens"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_name": self.concept_name,
            "title": self.title,
            "source_sections": list(self.source_sections),
            "estimated_tokens": self.estimated_tokens,
        }


@dataclass
class ConceptOutline:
    """List of identified concepts for one source document."""
    entries: list[OutlineEntry] = field(default_factory=list)

    def __iter__(self):
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConceptOutline":
        return cls(entries=[
            OutlineEntry.from_dict(e) for e in data.get("entries", [])
        ])

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [e.to_dict() for e in self.entries]}
```

- [ ] **Step 4: Run → 4 pass**

- [ ] **Step 5: Commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
git add src/builder/transform/ tests/builder/transform/
git commit -m "feat(builder/transform): ConceptOutline + OutlineEntry"
```

---

## Task 2: Prompts Module + Chunk Size Validator

**Files:**
- Create: `src/builder/transform/prompts.py`
- Create: `src/builder/transform/chunk_size.py`
- Create: `tests/builder/transform/test_chunk_size.py`

- [ ] **Step 1: Write `src/builder/transform/prompts.py`**

```python
"""Prompt templates for the Transform agents.

These are exported as plain strings (or functions returning strings) so
tests can assert that the right prompt was used and the orchestrator can
inject parameters cleanly.
"""
from __future__ import annotations


ANALYZER_SYSTEM = (
    "You analyze a source document and identify the atomic concepts it "
    "covers. Output a JSON object with an 'entries' list. Each entry has: "
    "concept_name (kebab-case, used as filename), title (human display), "
    "source_sections (list of section IDs from the source, may be empty), "
    "estimated_tokens (int, 500-2000 ideal). Concepts should be coherent "
    "and self-contained — one concept per filename."
)


def analyzer_prompt(source_text: str, source_name: str) -> str:
    return (
        f"Source document: {source_name}\n\n"
        f"---\n{source_text}\n---\n\n"
        f"Identify the atomic concepts and return JSON only."
    )


EXTRACTOR_SYSTEM = (
    "You extract a single concept from a source document into a clean "
    "Markdown vault page. The output is the BODY of the concept page only "
    "(no YAML frontmatter — that is added separately). Translate any non-"
    "English content to English. Keep the body 500-2000 tokens. Preserve "
    "headings, lists, code blocks. Reference cross-cutting concepts as "
    "[[wikilinks]] using kebab-case names."
)


def extractor_prompt(
    source_text: str,
    source_name: str,
    concept_name: str,
    concept_title: str,
) -> str:
    return (
        f"Source: {source_name}\n"
        f"Target concept: {concept_name} ({concept_title})\n\n"
        f"---\n{source_text}\n---\n\n"
        f"Output the concept's markdown body only."
    )


COVERAGE_SYSTEM = (
    "You compare a source document's outline to the list of concepts "
    "extracted from it. Return JSON: {\"missed_topics\": [list of strings]} "
    "naming any topics from the source outline that are NOT represented by "
    "an extracted concept."
)


def coverage_prompt(
    source_outline: list[str],
    extracted_concept_titles: list[str],
) -> str:
    return (
        f"Source outline:\n" + "\n".join(f"- {h}" for h in source_outline)
        + "\n\nExtracted concepts:\n"
        + "\n".join(f"- {t}" for t in extracted_concept_titles)
        + "\n\nReturn JSON only."
    )
```

No new tests for prompts (they're plain strings tested indirectly via agent tests).

- [ ] **Step 2: Write failing test `tests/builder/transform/test_chunk_size.py`**

```python
import pytest

from builder.transform.chunk_size import (
    MAX_CHUNK_TOKENS,
    MIN_CHUNK_TOKENS,
    classify_chunk_size,
    estimate_tokens,
)


def test_estimate_tokens_basic():
    """Rough heuristic: ~4 chars per token."""
    text = "x" * 4000
    assert estimate_tokens(text) == 1000


def test_estimate_tokens_zero():
    assert estimate_tokens("") == 0


def test_chunk_size_constants():
    assert MIN_CHUNK_TOKENS == 500
    assert MAX_CHUNK_TOKENS == 2000


@pytest.mark.parametrize("size,expected", [
    (100, "too_small"),
    (300, "too_small"),
    (499, "too_small"),
    (500, "ok"),
    (1000, "ok"),
    (2000, "ok"),
    (2001, "too_large"),
    (5000, "too_large"),
])
def test_classify_chunk_size(size, expected):
    assert classify_chunk_size(size) == expected
```

- [ ] **Step 3: Run → fail**

- [ ] **Step 4: Implement `src/builder/transform/chunk_size.py`**

```python
"""Heuristics for evaluating concept-page token counts."""
from __future__ import annotations


CHARS_PER_TOKEN = 4  # rough English heuristic; Haiku tokenizer is similar
MIN_CHUNK_TOKENS = 500
MAX_CHUNK_TOKENS = 2000


def estimate_tokens(text: str) -> int:
    """Quick estimate of token count via the 4-chars-per-token heuristic."""
    return len(text) // CHARS_PER_TOKEN


def classify_chunk_size(token_count: int) -> str:
    """Return 'too_small' | 'ok' | 'too_large'."""
    if token_count < MIN_CHUNK_TOKENS:
        return "too_small"
    if token_count > MAX_CHUNK_TOKENS:
        return "too_large"
    return "ok"
```

- [ ] **Step 5: Run → 11 pass**

- [ ] **Step 6: Commit**

```bash
git add src/builder/transform/prompts.py src/builder/transform/chunk_size.py tests/builder/transform/test_chunk_size.py
git commit -m "feat(builder/transform): prompts + chunk size classifier"
```

---

## Task 3: Conftest with Transform Mock Agent

**Files:**
- Create: `tests/builder/transform/conftest.py`

- [ ] **Step 1: Create the conftest**

```python
"""Fixtures for transform tests.

`canned_agent` returns scripted responses based on prompt content,
simulating an LLM that produces consistent JSON outlines and markdown
extractions for our test inputs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from builder.ingest.protocols import AgentResponse


@dataclass
class CannedAgent:
    """An AgentCaller that returns scripted text per prompt-substring match.

    `recipes` maps a substring to a canned text. The first matching recipe
    wins; if nothing matches, returns `default`.
    """
    recipes: dict[str, str] = field(default_factory=dict)
    default: str = "MOCK_DEFAULT_RESPONSE"
    canned_input_tokens: int = 200
    canned_output_tokens: int = 100
    calls: list[dict] = field(default_factory=list)

    def call(
        self,
        prompt: str,
        *,
        model: str = "haiku",
        images: list[bytes] | None = None,
    ) -> AgentResponse:
        self.calls.append({"prompt": prompt, "model": model,
                           "n_images": len(images) if images else 0})
        for needle, text in self.recipes.items():
            if needle in prompt:
                return AgentResponse(
                    text=text,
                    input_tokens=self.canned_input_tokens,
                    output_tokens=self.canned_output_tokens,
                )
        return AgentResponse(
            text=self.default,
            input_tokens=self.canned_input_tokens,
            output_tokens=self.canned_output_tokens,
        )


@pytest.fixture
def canned_agent() -> CannedAgent:
    return CannedAgent()


@pytest.fixture
def outline_json_response() -> str:
    """A canned analyzer JSON response covering two concepts."""
    return json.dumps({
        "entries": [
            {"concept_name": "oauth2-flow", "title": "OAuth2 Flow",
             "source_sections": ["3.1", "3.2"], "estimated_tokens": 1200},
            {"concept_name": "jwt-tokens", "title": "JWT Tokens",
             "source_sections": ["3.3"], "estimated_tokens": 800},
        ]
    })
```

- [ ] **Step 2: Run pytest to confirm nothing breaks**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pytest tests/builder/transform -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/builder/transform/conftest.py
git commit -m "test(builder/transform): conftest with CannedAgent"
```

---

## Task 4: ConceptAnalyzer

**Files:**
- Create: `src/builder/transform/analyzer.py`
- Create: `tests/builder/transform/test_analyzer.py`

- [ ] **Step 1: Write failing test `tests/builder/transform/test_analyzer.py`**

```python
import json

import pytest

from builder.transform.analyzer import AnalyzerError, ConceptAnalyzer
from builder.transform.outline import ConceptOutline


def test_analyzer_returns_outline(canned_agent, outline_json_response):
    canned_agent.recipes["Identify the atomic concepts"] = outline_json_response
    analyzer = ConceptAnalyzer(agent=canned_agent)

    outline, usage = analyzer.analyze(
        source_text="OAuth2 is a framework.",
        source_name="handbook.md",
    )

    assert isinstance(outline, ConceptOutline)
    assert len(outline) == 2
    names = [e.concept_name for e in outline]
    assert "oauth2-flow" in names
    assert "jwt-tokens" in names
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0


def test_analyzer_uses_haiku_low_effort(canned_agent, outline_json_response):
    canned_agent.recipes["Identify"] = outline_json_response
    analyzer = ConceptAnalyzer(agent=canned_agent)

    analyzer.analyze(source_text="x", source_name="doc")
    assert canned_agent.calls[-1]["model"] == "haiku"


def test_analyzer_rejects_malformed_json(canned_agent):
    canned_agent.default = "not valid json {{"
    analyzer = ConceptAnalyzer(agent=canned_agent)

    with pytest.raises(AnalyzerError):
        analyzer.analyze(source_text="x", source_name="doc")


def test_analyzer_strips_code_fences(canned_agent):
    """Models often wrap JSON in ```json fences; analyzer should tolerate this."""
    canned_agent.default = (
        "```json\n"
        + json.dumps({"entries": []})
        + "\n```"
    )
    analyzer = ConceptAnalyzer(agent=canned_agent)
    outline, _ = analyzer.analyze(source_text="x", source_name="doc")
    assert isinstance(outline, ConceptOutline)
    assert len(outline) == 0
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/transform/analyzer.py`**

```python
"""Analyzer — turns a raw source document into a ConceptOutline (JSON)."""
from __future__ import annotations

import json
import re

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.transform.outline import ConceptOutline
from builder.transform.prompts import analyzer_prompt


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)


class AnalyzerError(Exception):
    """Raised when the analyzer's response cannot be parsed."""


class ConceptAnalyzer:
    """Identifies atomic concepts in a source document via an LLM."""

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def analyze(
        self,
        source_text: str,
        source_name: str,
    ) -> tuple[ConceptOutline, AgentResponse]:
        prompt = analyzer_prompt(source_text, source_name)
        response = self._agent.call(prompt, model="haiku")
        outline = self._parse(response.text)
        return outline, response

    def _parse(self, text: str) -> ConceptOutline:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            cleaned = match.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise AnalyzerError(f"could not parse analyzer JSON: {e}") from e
        if not isinstance(data, dict) or "entries" not in data:
            raise AnalyzerError("analyzer JSON missing 'entries' key")
        return ConceptOutline.from_dict(data)
```

- [ ] **Step 4: Run → 4 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/transform/analyzer.py tests/builder/transform/test_analyzer.py
git commit -m "feat(builder/transform): ConceptAnalyzer (Haiku, low effort)"
```

---

## Task 5: ConceptExtractor

**Files:**
- Create: `src/builder/transform/extractor.py`
- Create: `tests/builder/transform/test_extractor.py`

- [ ] **Step 1: Write failing test**

```python
from builder.transform.extractor import ConceptExtractor


def test_extractor_returns_body_and_usage(canned_agent):
    canned_agent.recipes["Target concept"] = (
        "# OAuth2 Flow\n\nOAuth2 separates authn and authz.\n"
    )
    ext = ConceptExtractor(agent=canned_agent)

    body, usage = ext.extract(
        source_text="OAuth2 details...",
        source_name="handbook.md",
        concept_name="oauth2-flow",
        concept_title="OAuth2 Flow",
    )

    assert "OAuth2" in body
    assert usage.input_tokens > 0
    assert canned_agent.calls[-1]["model"] == "haiku"


def test_extractor_strips_code_fences(canned_agent):
    """Body responses wrapped in fences should be unwrapped."""
    canned_agent.recipes["Target"] = (
        "```markdown\n# Hello\n\nBody.\n```"
    )
    ext = ConceptExtractor(agent=canned_agent)
    body, _ = ext.extract(
        source_text="x", source_name="doc",
        concept_name="c", concept_title="C",
    )
    assert not body.startswith("```")
    assert "# Hello" in body
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/transform/extractor.py`**

```python
"""Extractor — produces one concept's markdown body from a source doc."""
from __future__ import annotations

import re

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.transform.prompts import extractor_prompt


CODE_FENCE = re.compile(
    r"^```(?:markdown|md)?\s*\n(.+?)\n```\s*$",
    re.DOTALL,
)


class ConceptExtractor:
    """Extracts the markdown body for one concept from a source document."""

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def extract(
        self,
        source_text: str,
        source_name: str,
        concept_name: str,
        concept_title: str,
    ) -> tuple[str, AgentResponse]:
        prompt = extractor_prompt(
            source_text=source_text,
            source_name=source_name,
            concept_name=concept_name,
            concept_title=concept_title,
        )
        response = self._agent.call(prompt, model="haiku")
        body = self._strip_fence(response.text)
        return body, response

    def _strip_fence(self, text: str) -> str:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            return match.group(1)
        return cleaned
```

- [ ] **Step 4: Run → 2 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/transform/extractor.py tests/builder/transform/test_extractor.py
git commit -m "feat(builder/transform): ConceptExtractor (Haiku, medium effort)"
```

---

## Task 6: CoverageChecker

**Files:**
- Create: `src/builder/transform/coverage.py`
- Create: `tests/builder/transform/test_coverage.py`

- [ ] **Step 1: Write failing test**

```python
import json

import pytest

from builder.transform.coverage import CoverageChecker, CoverageError


def test_coverage_returns_empty_when_complete(canned_agent):
    canned_agent.recipes["Source outline"] = json.dumps({"missed_topics": []})
    checker = CoverageChecker(agent=canned_agent)

    missed, usage = checker.check(
        source_outline=["Intro", "Auth"],
        extracted_titles=["Intro", "Auth"],
    )

    assert missed == []
    assert usage.input_tokens > 0


def test_coverage_returns_missed_topics(canned_agent):
    canned_agent.recipes["Source outline"] = json.dumps({
        "missed_topics": ["Edge Cases"],
    })
    checker = CoverageChecker(agent=canned_agent)

    missed, _ = checker.check(
        source_outline=["Intro", "Auth", "Edge Cases"],
        extracted_titles=["Intro", "Auth"],
    )

    assert missed == ["Edge Cases"]


def test_coverage_uses_haiku(canned_agent):
    canned_agent.recipes["Source outline"] = json.dumps({"missed_topics": []})
    checker = CoverageChecker(agent=canned_agent)
    checker.check(source_outline=[], extracted_titles=[])
    assert canned_agent.calls[-1]["model"] == "haiku"


def test_coverage_rejects_malformed(canned_agent):
    canned_agent.default = "not json"
    checker = CoverageChecker(agent=canned_agent)
    with pytest.raises(CoverageError):
        checker.check(source_outline=[], extracted_titles=[])
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/transform/coverage.py`**

```python
"""Coverage checker — verifies all source-outline topics got extracted."""
from __future__ import annotations

import json
import re

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.transform.prompts import coverage_prompt


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)


class CoverageError(Exception):
    """Raised when the coverage check response cannot be parsed."""


class CoverageChecker:
    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def check(
        self,
        source_outline: list[str],
        extracted_titles: list[str],
    ) -> tuple[list[str], AgentResponse]:
        prompt = coverage_prompt(
            source_outline=source_outline,
            extracted_concept_titles=extracted_titles,
        )
        response = self._agent.call(prompt, model="haiku")
        missed = self._parse(response.text)
        return missed, response

    def _parse(self, text: str) -> list[str]:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            cleaned = match.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise CoverageError(f"could not parse coverage JSON: {e}") from e
        if not isinstance(data, dict) or "missed_topics" not in data:
            raise CoverageError("coverage JSON missing 'missed_topics' key")
        return list(data["missed_topics"])
```

- [ ] **Step 4: Run → 4 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/transform/coverage.py tests/builder/transform/test_coverage.py
git commit -m "feat(builder/transform): CoverageChecker (Haiku, low effort)"
```

---

## Task 7: Transform Orchestrator

**Files:**
- Create: `src/builder/transform/orchestrator.py`
- Create: `tests/builder/transform/test_orchestrator.py`

The orchestrator coordinates analyzer → per-concept extractor → coverage check, writes concept pages to disk, integrates with Pipeline (record_item + record_cost), and tracks token usage.

- [ ] **Step 1: Write failing test `tests/builder/transform/test_orchestrator.py`**

```python
import json
from datetime import date
from pathlib import Path

from builder.ingest.protocols import ConvertResult
from builder.ingest.meta import DocumentMeta, ExtractionMethod
from builder.phases import Phase
from builder.pipeline import Pipeline
from builder.transform.orchestrator import TransformOrchestrator
from matter_expert import ConceptPage


def _convert_result(name: str, content: str = "body text"):
    return ConvertResult(
        content=content,
        meta=DocumentMeta(
            source_path=f"/x/{name}",
            source_type="md",
            extraction_method=ExtractionMethod.PASSTHROUGH,
            page_count=1,
            extracted_chars=len(content),
            extracted_images_count=0,
            outline=["A", "B"],
            language_detected="en",
            ingested=date(2026, 5, 10),
        ),
    )


def test_orchestrator_runs_full_pipeline_for_one_document(
    canned_agent, tmp_path, run_dir,
):
    canned_agent.recipes["Identify"] = json.dumps({"entries": [
        {"concept_name": "concept-a", "title": "Concept A",
         "source_sections": [], "estimated_tokens": 800},
    ]})
    canned_agent.recipes["Target concept"] = (
        "# Concept A\n\nBody of concept A.\n"
    )
    canned_agent.recipes["Source outline"] = json.dumps({"missed_topics": []})

    vault_dir = tmp_path / "vault"
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = TransformOrchestrator(agent=canned_agent, vault_dir=vault_dir)

    results = orch.transform(
        ingest_results={"doc1.md": _convert_result("doc1.md")},
        pipeline=pipeline,
    )

    assert "doc1.md" in results
    # One concept page written
    concept_path = vault_dir / "concepts" / "concept-a.md"
    assert concept_path.exists()
    # Concept page parses as a valid ConceptPage
    page = ConceptPage.read(concept_path)
    assert page.frontmatter.title == "Concept A"
    assert "Body of concept A" in page.body
    # Pipeline records item done and cost > 0
    item = pipeline.state.phases["transform"].items["doc1.md"]
    assert item.status == "done"
    assert pipeline.state.cost_tracker["per_phase"]["transform"] > 0


def test_orchestrator_marks_failed_on_analyzer_error(
    canned_agent, tmp_path, run_dir,
):
    canned_agent.default = "not valid json at all"

    vault_dir = tmp_path / "vault"
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = TransformOrchestrator(agent=canned_agent, vault_dir=vault_dir)

    results = orch.transform(
        ingest_results={"doc1.md": _convert_result("doc1.md")},
        pipeline=pipeline,
    )

    assert "doc1.md" not in results
    assert pipeline.state.phases["transform"].items["doc1.md"].status == "failed"


def test_orchestrator_writes_source_pages(
    canned_agent, tmp_path, run_dir,
):
    """Each source document is preserved under vault/sources/."""
    canned_agent.recipes["Identify"] = json.dumps({"entries": []})
    canned_agent.recipes["Source outline"] = json.dumps({"missed_topics": []})

    vault_dir = tmp_path / "vault"
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = TransformOrchestrator(agent=canned_agent, vault_dir=vault_dir)

    orch.transform(
        ingest_results={"doc1.md": _convert_result("doc1.md", content="original body")},
        pipeline=pipeline,
    )

    # Source page written under vault/sources/.
    source_path = vault_dir / "sources" / "doc1.md"
    assert source_path.exists()
    assert "original body" in source_path.read_text(encoding="utf-8")
```

Note: `run_dir` comes from `tests/builder/conftest.py`.

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/transform/orchestrator.py`**

```python
"""Transform orchestrator — runs analyzer → extractor → coverage per source doc."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from builder.cost_tracker import TokenUsage, estimate_cost
from builder.ingest.protocols import AgentCaller, ConvertResult
from builder.phases import Model, Phase
from builder.pipeline import Pipeline
from builder.transform.analyzer import AnalyzerError, ConceptAnalyzer
from builder.transform.coverage import CoverageChecker
from builder.transform.extractor import ConceptExtractor
from matter_expert import (
    ConceptFrontmatter,
    ConceptPage,
    MOCPage,
    Source,
    SourceFrontmatter,
    SourcePage,
    VaultPaths,
)


class TransformOrchestrator:
    """Runs analyzer → extractor → coverage per ingest result; writes vault pages."""

    def __init__(self, agent: AgentCaller, vault_dir: Path) -> None:
        self._analyzer = ConceptAnalyzer(agent=agent)
        self._extractor = ConceptExtractor(agent=agent)
        self._coverage = CoverageChecker(agent=agent)
        self._vault_dir = vault_dir
        self._paths = VaultPaths(root=vault_dir)

    def transform(
        self,
        ingest_results: dict[str, ConvertResult],
        pipeline: Pipeline,
    ) -> dict[str, list[str]]:
        """Run transform on each ingest result.

        Returns map: source_id → list of concept names written.
        Records items and costs to Pipeline.
        """
        outputs: dict[str, list[str]] = {}
        # Ensure vault directories exist.
        self._paths.concepts.mkdir(parents=True, exist_ok=True)
        self._paths.sources.mkdir(parents=True, exist_ok=True)

        for source_id, convert_result in ingest_results.items():
            try:
                concepts = self._transform_one(source_id, convert_result, pipeline)
            except Exception as e:
                pipeline.record_item(
                    Phase.TRANSFORM, source_id,
                    status="failed", error=str(e),
                )
                continue
            outputs[source_id] = concepts
            pipeline.record_item(
                Phase.TRANSFORM, source_id,
                status="done",
                concepts_count=len(concepts),
            )
        return outputs

    def _transform_one(
        self,
        source_id: str,
        convert: ConvertResult,
        pipeline: Pipeline,
    ) -> list[str]:
        # 1. Analyze
        outline, usage = self._analyzer.analyze(
            source_text=convert.content,
            source_name=source_id,
        )
        self._record_cost(pipeline, usage)

        # 2. Write the source page
        self._write_source_page(source_id, convert)

        # 3. Extract each concept
        concept_names: list[str] = []
        extracted_titles: list[str] = []
        for entry in outline:
            body, ex_usage = self._extractor.extract(
                source_text=convert.content,
                source_name=source_id,
                concept_name=entry.concept_name,
                concept_title=entry.title,
            )
            self._record_cost(pipeline, ex_usage)
            self._write_concept_page(entry, body, convert, source_id)
            concept_names.append(entry.concept_name)
            extracted_titles.append(entry.title)

        # 4. Coverage check
        _missed, cov_usage = self._coverage.check(
            source_outline=convert.meta.outline,
            extracted_titles=extracted_titles,
        )
        self._record_cost(pipeline, cov_usage)
        return concept_names

    def _record_cost(self, pipeline: Pipeline, usage) -> None:
        """`usage` is an AgentResponse — convert to TokenUsage + record."""
        from builder.cost_tracker import TokenUsage
        token_usage = TokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_input_tokens=getattr(usage, "cached_input_tokens", 0),
        )
        cost = estimate_cost(Model.HAIKU, token_usage)
        pipeline.record_cost(Phase.TRANSFORM, cost)

    def _write_concept_page(
        self,
        entry,
        body: str,
        convert: ConvertResult,
        source_id: str,
    ) -> None:
        fm = ConceptFrontmatter(
            title=entry.title,
            sources=[Source(file=source_id, sections=list(entry.source_sections))],
            tags=[],
            created=datetime.now(timezone.utc).date(),
        )
        page = ConceptPage(
            frontmatter=fm,
            body=body,
            path=self._paths.concept_for(entry.concept_name),
        )
        page.write()

    def _write_source_page(self, source_id: str, convert: ConvertResult) -> None:
        """Mirror the original ingest output under vault/sources/."""
        stem = Path(source_id).stem
        # Map ingest extraction_method to source page's extraction_method literal
        method = convert.meta.extraction_method.value
        # Some methods aren't part of SourceFrontmatter's Literal — coerce.
        if method not in {"text", "vision_fallback", "hybrid"}:
            method = "text"
        fm = SourceFrontmatter(
            title=stem,
            original_file=convert.meta.source_path,
            original_format=convert.meta.source_type,
            page_count=convert.meta.page_count,
            extraction_method=method,  # type: ignore[arg-type]
            language_detected=convert.meta.language_detected,
            ingested=convert.meta.ingested,
        )
        page = SourcePage(
            frontmatter=fm,
            body=convert.content,
            path=self._paths.source_for(stem),
        )
        page.write()
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/transform/orchestrator.py tests/builder/transform/test_orchestrator.py
git commit -m "feat(builder/transform): orchestrator wires analyzer/extractor/coverage to vault + Pipeline"
```

---

## Task 8: Public API

**Files:**
- Modify: `src/builder/transform/__init__.py`
- Create: `tests/builder/transform/test_public_api.py`

- [ ] **Step 1: Update `__init__.py`**

```python
"""Transform phase — translates and chunks raw markdown into vault pages."""
from builder.transform.outline import ConceptOutline, OutlineEntry
from builder.transform.chunk_size import (
    MIN_CHUNK_TOKENS,
    MAX_CHUNK_TOKENS,
    classify_chunk_size,
    estimate_tokens,
)
from builder.transform.analyzer import AnalyzerError, ConceptAnalyzer
from builder.transform.extractor import ConceptExtractor
from builder.transform.coverage import CoverageChecker, CoverageError
from builder.transform.orchestrator import TransformOrchestrator

__all__ = [
    "ConceptOutline", "OutlineEntry",
    "MIN_CHUNK_TOKENS", "MAX_CHUNK_TOKENS",
    "classify_chunk_size", "estimate_tokens",
    "AnalyzerError", "ConceptAnalyzer",
    "ConceptExtractor",
    "CoverageChecker", "CoverageError",
    "TransformOrchestrator",
]
```

- [ ] **Step 2: Write `tests/builder/transform/test_public_api.py`**

```python
def test_transform_public_api():
    from builder.transform import (
        ConceptOutline, OutlineEntry,
        MIN_CHUNK_TOKENS, MAX_CHUNK_TOKENS,
        classify_chunk_size, estimate_tokens,
        AnalyzerError, ConceptAnalyzer,
        ConceptExtractor,
        CoverageChecker, CoverageError,
        TransformOrchestrator,
    )
    assert MIN_CHUNK_TOKENS == 500
    assert callable(classify_chunk_size)
```

- [ ] **Step 3: Run all tests, commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pytest
git add src/builder/transform/__init__.py tests/builder/transform/test_public_api.py
git commit -m "feat(builder/transform): public API exports"
```

---

## Done

After completing all 8 tasks, the Transform phase provides:
- ConceptOutline / OutlineEntry types
- ConceptAnalyzer (Haiku, low) — produces JSON outline
- ConceptExtractor (Haiku, medium) — produces concept page body
- CoverageChecker (Haiku, low) — flags missed topics
- ChunkSize heuristics (estimate_tokens, classify_chunk_size)
- TransformOrchestrator — writes vault/concepts/*.md + vault/sources/*.md, records to Pipeline
