# Link Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Build the Link phase — clusters and deduplicates concepts written by Transform, assigns the 5 typed link types between concept pairs, generates MOC pages.

**Architecture:** `src/builder/link/`. Reads all concept pages from `vault/concepts/`, builds a compact "concept inventory" (name + 1-sentence summary), uses the LLM (Sonnet, high effort) to identify clusters of duplicate/near-duplicate concepts, merges them, then iterates over remaining concepts to assign typed links. Finally generates MOC pages grouped by tag. Enforces cardinality limits (8/5/6/4/3 for related/prereq/examples/contrasts/refines).

**Tech Stack:** Python 3.11+ stdlib + matter_expert + builder.{phases, cost_tracker, pipeline}.

---

## File Structure

```
src/builder/link/
├── __init__.py
├── inventory.py        # ConceptSummary + build_inventory (1-sentence summaries)
├── clusters.py         # Cluster dataclass + ClusterIdentifier (LLM)
├── merger.py           # ConceptMerger (LLM) — merges a cluster's concepts
├── linker.py           # LinkAgent (LLM) — assigns typed links per concept
├── moc_generator.py    # MOCGenerator — groups concepts by tag → MOC pages
├── cardinality.py      # enforce_cardinality_limits helper
├── prompts.py          # Prompt templates for cluster/merge/link
└── orchestrator.py     # LinkOrchestrator — wires everything to Pipeline

tests/builder/link/
├── __init__.py
├── conftest.py         # canned_agent (or reuse), concept-fixture builder
└── test_*.py (one per module)
```

---

## Task 1: Inventory — ConceptSummary + build_inventory

**Files:**
- Create: `src/builder/link/__init__.py` (empty)
- Create: `src/builder/link/inventory.py`
- Create: `tests/builder/link/__init__.py` (empty)
- Create: `tests/builder/link/test_inventory.py`

- [ ] **Step 1: Write failing test `tests/builder/link/test_inventory.py`**

```python
from datetime import date
from pathlib import Path

from builder.link.inventory import ConceptSummary, build_inventory
from matter_expert import ConceptFrontmatter, ConceptPage, Source


def _make_concept(tmp_path: Path, name: str, title: str, body: str, tags=None):
    fm = ConceptFrontmatter(
        title=title,
        sources=[Source(file=f"{name}-source.md", sections=[])],
        tags=list(tags or []),
        created=date(2026, 5, 10),
    )
    concepts_dir = tmp_path / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    page = ConceptPage(frontmatter=fm, body=body, path=concepts_dir / f"{name}.md")
    page.write()
    return page


def test_summary_construction():
    s = ConceptSummary(
        name="oauth2-flow",
        title="OAuth2 Flow",
        summary="An authorization framework using access tokens.",
        tags=["auth", "oauth2"],
    )
    assert s.name == "oauth2-flow"
    assert "authorization" in s.summary


def test_build_inventory_extracts_first_sentence(tmp_path: Path):
    _make_concept(
        tmp_path, "oauth2-flow", "OAuth2 Flow",
        body="# OAuth2 Flow\n\nOAuth2 is an authorization framework using "
             "access and refresh tokens. It is widely used.\n",
        tags=["auth", "oauth2"],
    )

    inv = build_inventory(tmp_path / "concepts")

    assert len(inv) == 1
    entry = inv[0]
    assert entry.name == "oauth2-flow"
    assert entry.title == "OAuth2 Flow"
    assert "authorization framework" in entry.summary
    assert entry.tags == ["auth", "oauth2"]


def test_build_inventory_handles_empty_body(tmp_path: Path):
    _make_concept(tmp_path, "empty", "Empty Concept", body="")
    inv = build_inventory(tmp_path / "concepts")
    assert inv[0].summary == ""


def test_build_inventory_strips_heading_markers(tmp_path: Path):
    _make_concept(
        tmp_path, "x", "X",
        body="# Heading\n\nFirst sentence here. Second sentence.\n",
    )
    inv = build_inventory(tmp_path / "concepts")
    assert "First sentence" in inv[0].summary
    assert not inv[0].summary.startswith("#")


def test_build_inventory_alphabetical_order(tmp_path: Path):
    _make_concept(tmp_path, "z-concept", "Z", body="zz")
    _make_concept(tmp_path, "a-concept", "A", body="aa")
    inv = build_inventory(tmp_path / "concepts")
    assert [s.name for s in inv] == ["a-concept", "z-concept"]
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/link/inventory.py`**

```python
"""Build a compact 'concept inventory' for the Link Agent.

Each entry is one concept reduced to its name, title, 1-sentence summary,
and tags — small enough for the agent to cluster hundreds of concepts at
once without exceeding context limits.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from matter_expert import ConceptPage


SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ConceptSummary:
    """Compact representation of a concept for clustering/linking."""
    name: str
    title: str
    summary: str
    tags: list[str]


def _first_sentence(body: str) -> str:
    """Return the first sentence of the body, stripping heading lines."""
    # Skip blank lines and heading lines at the top.
    lines = body.splitlines()
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("#")):
        lines.pop(0)
    if not lines:
        return ""
    # Reflow remaining lines until first sentence boundary.
    paragraph = " ".join(lines).strip()
    if not paragraph:
        return ""
    parts = SENTENCE_END.split(paragraph, maxsplit=1)
    return parts[0].strip()


def build_inventory(concepts_dir: Path) -> list[ConceptSummary]:
    """Build a sorted-by-name inventory of all concept pages under `concepts_dir`."""
    summaries: list[ConceptSummary] = []
    for path in sorted(concepts_dir.glob("*.md")):
        page = ConceptPage.read(path)
        summaries.append(ConceptSummary(
            name=page.name,
            title=page.frontmatter.title,
            summary=_first_sentence(page.body),
            tags=list(page.frontmatter.tags),
        ))
    return summaries
```

- [ ] **Step 4: Run → 5 pass**

- [ ] **Step 5: Commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
git add src/builder/link/ tests/builder/link/
git commit -m "feat(builder/link): ConceptSummary + build_inventory"
```

---

## Task 2: Cardinality Enforcer

**Files:**
- Create: `src/builder/link/cardinality.py`
- Create: `tests/builder/link/test_cardinality.py`

- [ ] **Step 1: Write failing test**

```python
from builder.link.cardinality import (
    MAX_RELATED, MAX_PREREQUISITES, MAX_EXAMPLES,
    MAX_CONTRASTS, MAX_REFINES,
    enforce_link_cardinality,
)


def test_constants_match_design_spec():
    assert MAX_RELATED == 8
    assert MAX_PREREQUISITES == 5
    assert MAX_EXAMPLES == 6
    assert MAX_CONTRASTS == 4
    assert MAX_REFINES == 3


def test_under_limit_unchanged():
    links = {
        "related": ["a", "b"],
        "prerequisites": ["c"],
        "examples": [],
        "contrasts": [],
        "refines": [],
    }
    assert enforce_link_cardinality(links) == links


def test_over_limit_trimmed_to_max():
    links = {
        "related": [f"r{i}" for i in range(12)],
        "prerequisites": [],
        "examples": [],
        "contrasts": [],
        "refines": [],
    }
    result = enforce_link_cardinality(links)
    assert len(result["related"]) == MAX_RELATED
    assert result["related"] == [f"r{i}" for i in range(MAX_RELATED)]


def test_all_link_types_enforced():
    over = {
        "related": [f"a{i}" for i in range(20)],
        "prerequisites": [f"b{i}" for i in range(10)],
        "examples": [f"c{i}" for i in range(10)],
        "contrasts": [f"d{i}" for i in range(10)],
        "refines": [f"e{i}" for i in range(10)],
    }
    result = enforce_link_cardinality(over)
    assert len(result["related"]) == MAX_RELATED
    assert len(result["prerequisites"]) == MAX_PREREQUISITES
    assert len(result["examples"]) == MAX_EXAMPLES
    assert len(result["contrasts"]) == MAX_CONTRASTS
    assert len(result["refines"]) == MAX_REFINES
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/link/cardinality.py`**

```python
"""Enforce per-link-type maximum cardinality (design spec §4.4)."""
from __future__ import annotations


MAX_RELATED = 8
MAX_PREREQUISITES = 5
MAX_EXAMPLES = 6
MAX_CONTRASTS = 4
MAX_REFINES = 3


_LIMITS = {
    "related": MAX_RELATED,
    "prerequisites": MAX_PREREQUISITES,
    "examples": MAX_EXAMPLES,
    "contrasts": MAX_CONTRASTS,
    "refines": MAX_REFINES,
}


def enforce_link_cardinality(links: dict[str, list[str]]) -> dict[str, list[str]]:
    """Trim each link list to its max-recommended count.

    Returns a new dict; the input is not mutated. Preserves order — the
    first N entries are kept (callers must order by importance).
    """
    return {
        key: list(values[:_LIMITS.get(key, len(values))])
        for key, values in links.items()
    }
```

- [ ] **Step 4: Run → 4 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/link/cardinality.py tests/builder/link/test_cardinality.py
git commit -m "feat(builder/link): enforce_link_cardinality"
```

---

## Task 3: Prompts + Conftest

**Files:**
- Create: `src/builder/link/prompts.py`
- Create: `tests/builder/link/conftest.py`

- [ ] **Step 1: Write `src/builder/link/prompts.py`**

```python
"""Prompt templates for the Link phase agents."""
from __future__ import annotations


CLUSTER_SYSTEM = (
    "You analyze a flat list of concept inventories and identify CLUSTERS of "
    "concepts that describe the same thing (different names, identical "
    "underlying concept). Return JSON: {\"clusters\": [{\"members\": "
    "[concept_name, concept_name, ...]}]}. Singleton concepts (no duplicates) "
    "must NOT be included. Be conservative — only group concepts whose summaries "
    "describe the same thing."
)


def cluster_prompt(inventory_json: str) -> str:
    return f"Inventory (JSON):\n\n{inventory_json}\n\nReturn JSON only."


MERGE_SYSTEM = (
    "You are given several concept pages that describe the same underlying "
    "concept and must produce ONE merged page. The merged body should keep "
    "the most complete and accurate content from each source, NOT just "
    "concatenate them. When sources disagree, mark the disagreement explicitly "
    "with a > Note: blockquote pointing at the conflicting source."
)


def merge_prompt(concepts: list[dict]) -> str:
    """concepts is a list of {name, title, body, sources}."""
    parts = []
    for c in concepts:
        parts.append(f"=== {c['name']} (title: {c['title']}) ===\n{c['body']}")
    body = "\n\n".join(parts)
    return (
        "Merge the following concept pages into one. Return the merged "
        f"markdown body only.\n\n{body}"
    )


LINK_SYSTEM = (
    "You assign typed links between concepts. Given a target concept and the "
    "full inventory of other concepts, decide which other concepts belong in "
    "each of 5 lists: related, prerequisites, examples, contrasts, refines. "
    "Return JSON: {\"related\": [...], \"prerequisites\": [...], ...}. "
    "Use the concept_name (kebab-case), NEVER the title. "
    "Be selective — fewer high-quality links is better."
)


def link_prompt(target_summary: dict, inventory_json: str) -> str:
    return (
        f"Target concept:\n{target_summary['name']} — {target_summary['title']}\n"
        f"Summary: {target_summary['summary']}\n\n"
        f"Full inventory (JSON):\n{inventory_json}\n\n"
        f"Return typed-link JSON only."
    )
```

- [ ] **Step 2: Write `tests/builder/link/conftest.py`**

```python
"""Fixtures for link tests. Reuses CannedAgent pattern from transform."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from builder.ingest.protocols import AgentResponse


@dataclass
class CannedAgent:
    recipes: dict[str, str] = field(default_factory=dict)
    default: str = "MOCK_DEFAULT"
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
        self.calls.append({"prompt": prompt, "model": model})
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
```

- [ ] **Step 3: Run pytest, commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pytest tests/builder/link -v
git add src/builder/link/prompts.py tests/builder/link/conftest.py
git commit -m "feat(builder/link): prompts + conftest with CannedAgent"
```

---

## Task 4: ClusterIdentifier

**Files:**
- Create: `src/builder/link/clusters.py`
- Create: `tests/builder/link/test_clusters.py`

- [ ] **Step 1: Write failing test**

```python
import json
import pytest

from builder.link.clusters import Cluster, ClusterIdentifier, ClusterError
from builder.link.inventory import ConceptSummary


def test_cluster_construction():
    c = Cluster(members=["oauth2-flow", "oauth-overview"])
    assert len(c.members) == 2


def test_identify_returns_clusters(canned_agent):
    canned_agent.recipes["Inventory"] = json.dumps({
        "clusters": [{"members": ["oauth2-flow", "oauth-overview"]}]
    })
    identifier = ClusterIdentifier(agent=canned_agent)
    inv = [
        ConceptSummary("oauth2-flow", "OAuth2", "OAuth2 framework.", []),
        ConceptSummary("oauth-overview", "OAuth Overview", "Overview of OAuth.", []),
        ConceptSummary("jwt-tokens", "JWT", "JSON Web Tokens.", []),
    ]
    clusters, usage = identifier.identify(inv)

    assert len(clusters) == 1
    assert set(clusters[0].members) == {"oauth2-flow", "oauth-overview"}
    assert usage.input_tokens > 0
    assert canned_agent.calls[-1]["model"] == "sonnet"


def test_identify_handles_no_clusters(canned_agent):
    canned_agent.recipes["Inventory"] = json.dumps({"clusters": []})
    identifier = ClusterIdentifier(agent=canned_agent)
    clusters, _ = identifier.identify([])
    assert clusters == []


def test_identify_rejects_malformed(canned_agent):
    canned_agent.default = "not json"
    identifier = ClusterIdentifier(agent=canned_agent)
    with pytest.raises(ClusterError):
        identifier.identify([])


def test_identify_strips_singleton_clusters(canned_agent):
    """A 'cluster' with one member is not a duplication — drop it."""
    canned_agent.recipes["Inventory"] = json.dumps({
        "clusters": [
            {"members": ["a"]},
            {"members": ["b", "c"]},
        ]
    })
    identifier = ClusterIdentifier(agent=canned_agent)
    clusters, _ = identifier.identify([])
    # Only the 2-member cluster survives.
    assert len(clusters) == 1
    assert set(clusters[0].members) == {"b", "c"}
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/link/clusters.py`**

```python
"""Identify clusters of duplicate/near-duplicate concepts via the LLM."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.link.inventory import ConceptSummary
from builder.link.prompts import cluster_prompt


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)


class ClusterError(Exception):
    pass


@dataclass(frozen=True)
class Cluster:
    members: list[str]


class ClusterIdentifier:
    """Identifies groups of concepts that describe the same underlying thing."""

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def identify(
        self,
        inventory: list[ConceptSummary],
    ) -> tuple[list[Cluster], AgentResponse]:
        inv_payload = [
            {"name": s.name, "title": s.title, "summary": s.summary, "tags": s.tags}
            for s in inventory
        ]
        prompt = cluster_prompt(json.dumps(inv_payload))
        response = self._agent.call(prompt, model="sonnet")
        clusters = self._parse(response.text)
        return clusters, response

    def _parse(self, text: str) -> list[Cluster]:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            cleaned = match.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ClusterError(f"could not parse cluster JSON: {e}") from e
        raw = data.get("clusters", [])
        clusters: list[Cluster] = []
        for entry in raw:
            members = list(entry.get("members", []))
            if len(members) > 1:
                clusters.append(Cluster(members=members))
        return clusters
```

- [ ] **Step 4: Run → 5 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/link/clusters.py tests/builder/link/test_clusters.py
git commit -m "feat(builder/link): ClusterIdentifier (Sonnet, high effort)"
```

---

## Task 5: ConceptMerger

**Files:**
- Create: `src/builder/link/merger.py`
- Create: `tests/builder/link/test_merger.py`

- [ ] **Step 1: Write failing test**

```python
import re

from builder.link.merger import ConceptMerger


def test_merger_returns_merged_body_and_aggregated_sources(canned_agent, tmp_path):
    canned_agent.recipes["Merge"] = "# OAuth2 Flow\n\nMerged content.\n"
    merger = ConceptMerger(agent=canned_agent)

    concepts = [
        {"name": "oauth2-flow", "title": "OAuth2 Flow",
         "body": "Body 1", "sources": [{"file": "a.pdf", "sections": ["1"]}]},
        {"name": "oauth-overview", "title": "OAuth Overview",
         "body": "Body 2", "sources": [{"file": "b.pdf", "sections": ["2"]}]},
    ]
    result, usage = merger.merge(concepts)

    assert "Merged content" in result["body"]
    # Sources from both inputs aggregated
    files = {s["file"] for s in result["sources"]}
    assert files == {"a.pdf", "b.pdf"}
    # Used sonnet for merging
    assert canned_agent.calls[-1]["model"] == "sonnet"


def test_merger_strips_code_fences(canned_agent):
    canned_agent.recipes["Merge"] = "```markdown\n# Merged\n\nBody.\n```"
    merger = ConceptMerger(agent=canned_agent)
    result, _ = merger.merge([
        {"name": "a", "title": "A", "body": "x", "sources": []},
        {"name": "b", "title": "B", "body": "y", "sources": []},
    ])
    assert not result["body"].startswith("```")
    assert "# Merged" in result["body"]


def test_merger_preserves_merged_from(canned_agent):
    """The merged concept records the names of the originals in merged_from."""
    canned_agent.recipes["Merge"] = "Body."
    merger = ConceptMerger(agent=canned_agent)
    result, _ = merger.merge([
        {"name": "a", "title": "A", "body": "x", "sources": []},
        {"name": "b", "title": "B", "body": "y", "sources": []},
    ])
    assert set(result["merged_from"]) == {"a", "b"}
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/link/merger.py`**

```python
"""Merge multiple concept pages into a single canonical page."""
from __future__ import annotations

import re

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.link.prompts import merge_prompt


CODE_FENCE = re.compile(
    r"^```(?:markdown|md)?\s*\n(.+?)\n```\s*$", re.DOTALL,
)


class ConceptMerger:
    """Merges a cluster of duplicate concept pages into one canonical page."""

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def merge(
        self,
        concepts: list[dict],
    ) -> tuple[dict, AgentResponse]:
        """Merge the given concept pages.

        Each item: {name, title, body, sources}.
        Returns ({body, sources, merged_from}, usage).
        """
        prompt = merge_prompt(concepts)
        response = self._agent.call(prompt, model="sonnet")
        body = self._strip_fence(response.text)

        # Aggregate sources from all input concepts.
        seen_files = set()
        aggregated: list[dict] = []
        for c in concepts:
            for src in c.get("sources", []):
                key = src.get("file")
                if key and key not in seen_files:
                    seen_files.add(key)
                    aggregated.append(src)

        merged_from = [c["name"] for c in concepts]
        return ({"body": body, "sources": aggregated, "merged_from": merged_from},
                response)

    def _strip_fence(self, text: str) -> str:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            return match.group(1)
        return cleaned
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/link/merger.py tests/builder/link/test_merger.py
git commit -m "feat(builder/link): ConceptMerger (Sonnet, high effort)"
```

---

## Task 6: LinkAgent

**Files:**
- Create: `src/builder/link/linker.py`
- Create: `tests/builder/link/test_linker.py`

The LinkAgent assigns the 5 typed links for one target concept, given the inventory.

- [ ] **Step 1: Write failing test**

```python
import json

import pytest

from builder.link.inventory import ConceptSummary
from builder.link.linker import LinkAgent, LinkError


def test_link_returns_typed_links(canned_agent):
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": ["jwt-tokens"],
        "prerequisites": ["http-basics"],
        "examples": ["oauth2-google-flow"],
        "contrasts": ["basic-auth"],
        "refines": [],
    })
    linker = LinkAgent(agent=canned_agent)

    target = ConceptSummary("oauth2-flow", "OAuth2 Flow", "An auth framework.", [])
    inventory = [target, ConceptSummary("jwt-tokens", "JWT", "Tokens.", [])]
    links, usage = linker.assign(target, inventory)

    assert links["related"] == ["jwt-tokens"]
    assert links["prerequisites"] == ["http-basics"]
    assert canned_agent.calls[-1]["model"] == "sonnet"


def test_link_excludes_self(canned_agent):
    """If the LLM tries to link a concept to itself, it should be filtered out."""
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": ["oauth2-flow", "jwt-tokens"],
        "prerequisites": [], "examples": [], "contrasts": [], "refines": [],
    })
    linker = LinkAgent(agent=canned_agent)
    target = ConceptSummary("oauth2-flow", "OAuth2", "...", [])
    links, _ = linker.assign(target, [target])
    assert "oauth2-flow" not in links["related"]
    assert "jwt-tokens" in links["related"]


def test_link_enforces_cardinality(canned_agent):
    """A response with too many 'related' entries is trimmed to the max."""
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": [f"x{i}" for i in range(15)],
        "prerequisites": [], "examples": [], "contrasts": [], "refines": [],
    })
    linker = LinkAgent(agent=canned_agent)
    target = ConceptSummary("self", "self", "...", [])
    links, _ = linker.assign(target, [])
    assert len(links["related"]) == 8  # MAX_RELATED


def test_link_rejects_malformed(canned_agent):
    canned_agent.default = "not json"
    linker = LinkAgent(agent=canned_agent)
    target = ConceptSummary("self", "S", "...", [])
    with pytest.raises(LinkError):
        linker.assign(target, [])


def test_link_fills_missing_keys_with_empty_lists(canned_agent):
    """If the LLM omits a key, the result still has all 5 keys."""
    canned_agent.recipes["Target"] = json.dumps({"related": ["a"]})
    linker = LinkAgent(agent=canned_agent)
    target = ConceptSummary("self", "S", "...", [])
    links, _ = linker.assign(target, [])
    for key in ("related", "prerequisites", "examples", "contrasts", "refines"):
        assert key in links
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/link/linker.py`**

```python
"""Assign typed links (related, prerequisites, examples, contrasts, refines)
for a single concept based on the full inventory."""
from __future__ import annotations

import json
import re

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.link.cardinality import enforce_link_cardinality
from builder.link.inventory import ConceptSummary
from builder.link.prompts import link_prompt


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)
LINK_KEYS = ("related", "prerequisites", "examples", "contrasts", "refines")


class LinkError(Exception):
    pass


class LinkAgent:
    """Assigns typed links for a single target concept."""

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def assign(
        self,
        target: ConceptSummary,
        inventory: list[ConceptSummary],
    ) -> tuple[dict[str, list[str]], AgentResponse]:
        inv_payload = [
            {"name": s.name, "title": s.title, "summary": s.summary}
            for s in inventory if s.name != target.name
        ]
        prompt = link_prompt(
            target_summary={
                "name": target.name, "title": target.title,
                "summary": target.summary,
            },
            inventory_json=json.dumps(inv_payload),
        )
        response = self._agent.call(prompt, model="sonnet")
        links = self._parse(response.text, target.name)
        return links, response

    def _parse(self, text: str, target_name: str) -> dict[str, list[str]]:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            cleaned = match.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise LinkError(f"could not parse link JSON: {e}") from e
        if not isinstance(data, dict):
            raise LinkError("link JSON must be an object")

        # Fill missing keys with empty lists, drop self-references, dedupe.
        result: dict[str, list[str]] = {}
        for key in LINK_KEYS:
            raw_list = data.get(key, [])
            seen: set[str] = set()
            cleaned_list: list[str] = []
            for item in raw_list:
                if item == target_name or item in seen:
                    continue
                seen.add(item)
                cleaned_list.append(item)
            result[key] = cleaned_list
        return enforce_link_cardinality(result)
```

- [ ] **Step 4: Run → 5 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/link/linker.py tests/builder/link/test_linker.py
git commit -m "feat(builder/link): LinkAgent assigns typed links (Sonnet, high effort)"
```

---

## Task 7: MOCGenerator

**Files:**
- Create: `src/builder/link/moc_generator.py`
- Create: `tests/builder/link/test_moc_generator.py`

Groups concepts by primary tag and generates MOC pages.

- [ ] **Step 1: Write failing test**

```python
from datetime import date
from pathlib import Path

from builder.link.inventory import ConceptSummary
from builder.link.moc_generator import MOCGenerator
from matter_expert import MOCPage


def test_generates_moc_per_tag(tmp_path: Path):
    inventory = [
        ConceptSummary("oauth2-flow", "OAuth2", "x", tags=["auth", "oauth2"]),
        ConceptSummary("jwt-tokens", "JWT", "y", tags=["auth"]),
        ConceptSummary("encryption-fundamentals", "Encryption", "z", tags=["crypto"]),
    ]
    mocs_dir = tmp_path / "MOCs"
    gen = MOCGenerator()
    written = gen.generate(inventory, mocs_dir)

    # Two MOCs: auth, crypto. oauth2 has only one concept → not a separate MOC.
    moc_names = {m.name for m in written}
    assert "auth" in moc_names
    assert "crypto" in moc_names
    # Each written file is readable as an MOCPage
    auth_moc = MOCPage.read(mocs_dir / "auth.md")
    assert set(auth_moc.frontmatter.children) == {"oauth2-flow", "jwt-tokens"}


def test_singleton_tags_are_skipped(tmp_path: Path):
    """Tags appearing on only one concept don't get their own MOC."""
    inventory = [
        ConceptSummary("a", "A", "", tags=["solo"]),
        ConceptSummary("b", "B", "", tags=["shared"]),
        ConceptSummary("c", "C", "", tags=["shared"]),
    ]
    mocs_dir = tmp_path / "MOCs"
    gen = MOCGenerator()
    written = gen.generate(inventory, mocs_dir)
    names = {m.name for m in written}
    assert "shared" in names
    assert "solo" not in names


def test_moc_body_lists_children_as_wikilinks(tmp_path: Path):
    inventory = [
        ConceptSummary("a", "A", "", tags=["t"]),
        ConceptSummary("b", "B", "", tags=["t"]),
    ]
    mocs_dir = tmp_path / "MOCs"
    gen = MOCGenerator()
    gen.generate(inventory, mocs_dir)

    body = (mocs_dir / "t.md").read_text(encoding="utf-8")
    assert "[[a]]" in body
    assert "[[b]]" in body
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/link/moc_generator.py`**

```python
"""Generate MOC pages by grouping concepts on shared tags."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from builder.link.inventory import ConceptSummary
from matter_expert import MOCFrontmatter, MOCPage


class MOCGenerator:
    """Generates a MOC per tag (skipping singleton tags)."""

    def generate(
        self,
        inventory: list[ConceptSummary],
        mocs_dir: Path,
    ) -> list[MOCPage]:
        """Write one MOC per shared tag. Returns the list of written MOCPages."""
        mocs_dir.mkdir(parents=True, exist_ok=True)
        # Group concepts by tag.
        by_tag: dict[str, list[str]] = defaultdict(list)
        for s in inventory:
            for t in s.tags:
                by_tag[t].append(s.name)

        written: list[MOCPage] = []
        for tag in sorted(by_tag):
            children = sorted(by_tag[tag])
            if len(children) < 2:
                continue
            fm = MOCFrontmatter(
                title=tag.title(),
                children=children,
                parents=[],
                related_mocs=[],
                created=datetime.now(timezone.utc).date(),
            )
            body = (
                f"# {tag.title()} MOC\n\n"
                f"## Concepts\n\n"
                + "\n".join(f"- [[{name}]]" for name in children)
                + "\n"
            )
            page = MOCPage(frontmatter=fm, body=body, path=mocs_dir / f"{tag}.md")
            page.write()
            written.append(page)
        return written
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/link/moc_generator.py tests/builder/link/test_moc_generator.py
git commit -m "feat(builder/link): MOCGenerator groups concepts by tag"
```

---

## Task 8: LinkOrchestrator

**Files:**
- Create: `src/builder/link/orchestrator.py`
- Create: `tests/builder/link/test_orchestrator.py`

- [ ] **Step 1: Write failing test**

```python
import json
from datetime import date
from pathlib import Path

from builder.link.orchestrator import LinkOrchestrator
from builder.phases import Phase
from builder.pipeline import Pipeline
from matter_expert import ConceptFrontmatter, ConceptPage, Source, VaultPaths


def _seed_concept(vault: VaultPaths, name: str, title: str, tags=None):
    fm = ConceptFrontmatter(
        title=title,
        sources=[Source(file=f"{name}.md", sections=[])],
        tags=list(tags or []),
        created=date(2026, 5, 10),
    )
    vault.concepts.mkdir(parents=True, exist_ok=True)
    ConceptPage(
        frontmatter=fm,
        body=f"# {title}\n\nBody of {title}.\n",
        path=vault.concept_for(name),
    ).write()


def test_orchestrator_runs_full_link_pipeline(canned_agent, tmp_path, run_dir):
    vault = VaultPaths(root=tmp_path / "vault")
    _seed_concept(vault, "oauth2-flow", "OAuth2 Flow", tags=["auth"])
    _seed_concept(vault, "jwt-tokens", "JWT", tags=["auth"])

    # No clusters; per-concept link assignments
    canned_agent.recipes["Inventory"] = json.dumps({"clusters": []})
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": [],
        "prerequisites": [],
        "examples": [],
        "contrasts": [],
        "refines": [],
    })

    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = LinkOrchestrator(agent=canned_agent, vault_dir=vault.root)
    orch.link(pipeline=pipeline)

    # Concepts still on disk
    assert vault.concept_for("oauth2-flow").exists()
    # One MOC generated for the "auth" tag
    assert (vault.root / "MOCs" / "auth.md").exists()
    # Pipeline marked complete with cost > 0
    assert pipeline.state.phases["link"].status in ("in_progress", "completed", "pending")
    assert pipeline.state.cost_tracker["per_phase"].get("link", 0) > 0


def test_orchestrator_merges_clustered_concepts(canned_agent, tmp_path, run_dir):
    vault = VaultPaths(root=tmp_path / "vault")
    _seed_concept(vault, "oauth-a", "OAuth A", tags=["auth"])
    _seed_concept(vault, "oauth-b", "OAuth B", tags=["auth"])

    # Cluster the two oauth concepts; merge them; no links assigned.
    canned_agent.recipes["Inventory"] = json.dumps({
        "clusters": [{"members": ["oauth-a", "oauth-b"]}]
    })
    canned_agent.recipes["Merge"] = (
        "# Merged OAuth\n\nMerged body.\n"
    )
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": [], "prerequisites": [], "examples": [],
        "contrasts": [], "refines": [],
    })

    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = LinkOrchestrator(agent=canned_agent, vault_dir=vault.root)
    orch.link(pipeline=pipeline)

    # Originals removed; one merged page exists
    assert not vault.concept_for("oauth-b").exists()
    # The merged page uses the first member's name (oauth-a) as canonical
    survivor = ConceptPage.read(vault.concept_for("oauth-a"))
    assert "Merged" in survivor.body
    assert set(survivor.frontmatter.merged_from) == {"oauth-a", "oauth-b"}


def test_orchestrator_writes_typed_links_to_concept_frontmatter(
    canned_agent, tmp_path, run_dir,
):
    vault = VaultPaths(root=tmp_path / "vault")
    _seed_concept(vault, "oauth2-flow", "OAuth2", tags=["auth"])
    _seed_concept(vault, "jwt-tokens", "JWT", tags=["auth"])

    canned_agent.recipes["Inventory"] = json.dumps({"clusters": []})
    # The LinkAgent will be invoked once per concept. It produces the same
    # mock response for both, but we filter self-refs in LinkAgent.
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": ["jwt-tokens", "oauth2-flow"],
        "prerequisites": [], "examples": [], "contrasts": [], "refines": [],
    })

    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = LinkOrchestrator(agent=canned_agent, vault_dir=vault.root)
    orch.link(pipeline=pipeline)

    oauth = ConceptPage.read(vault.concept_for("oauth2-flow"))
    jwt = ConceptPage.read(vault.concept_for("jwt-tokens"))
    # Self-refs filtered out
    assert "oauth2-flow" not in oauth.frontmatter.related
    assert "jwt-tokens" in oauth.frontmatter.related
    assert "jwt-tokens" not in jwt.frontmatter.related
    assert "oauth2-flow" in jwt.frontmatter.related
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/link/orchestrator.py`**

```python
"""Link orchestrator — clustering → merging → typed link assignment → MOCs."""
from __future__ import annotations

from pathlib import Path

from builder.cost_tracker import TokenUsage, estimate_cost
from builder.ingest.protocols import AgentCaller
from builder.link.clusters import ClusterIdentifier
from builder.link.inventory import build_inventory
from builder.link.linker import LinkAgent
from builder.link.merger import ConceptMerger
from builder.link.moc_generator import MOCGenerator
from builder.phases import Model, Phase
from builder.pipeline import Pipeline
from matter_expert import ConceptPage, Source, VaultPaths


class LinkOrchestrator:
    """Runs the full Link phase across vault/concepts/."""

    def __init__(self, agent: AgentCaller, vault_dir: Path) -> None:
        self._clusters = ClusterIdentifier(agent=agent)
        self._merger = ConceptMerger(agent=agent)
        self._linker = LinkAgent(agent=agent)
        self._mocs = MOCGenerator()
        self._paths = VaultPaths(root=vault_dir)

    def link(self, pipeline: Pipeline) -> None:
        pipeline.mark_phase_started(Phase.LINK)

        # 1. Build inventory from current vault state.
        inventory = build_inventory(self._paths.concepts)
        if not inventory:
            pipeline.mark_phase_completed(Phase.LINK)
            return

        # 2. Identify clusters of duplicate concepts.
        clusters, usage = self._clusters.identify(inventory)
        self._record_cost(pipeline, usage)

        # 3. Merge each cluster.
        for cluster in clusters:
            self._merge_cluster(cluster, pipeline)

        # 4. Rebuild inventory after merges.
        inventory = build_inventory(self._paths.concepts)

        # 5. Assign typed links to each surviving concept.
        for summary in inventory:
            self._assign_links(summary, inventory, pipeline)

        # 6. Generate MOCs from final inventory.
        self._mocs.generate(inventory, self._paths.mocs)

        pipeline.mark_phase_completed(Phase.LINK)

    def _merge_cluster(self, cluster, pipeline: Pipeline) -> None:
        """Merge a cluster into the first member's filename."""
        member_pages: list[ConceptPage] = []
        for name in cluster.members:
            path = self._paths.concept_for(name)
            if path.exists():
                member_pages.append(ConceptPage.read(path))
        if len(member_pages) < 2:
            return

        merge_input = [
            {"name": p.name, "title": p.frontmatter.title, "body": p.body,
             "sources": [s.to_dict() for s in p.frontmatter.sources]}
            for p in member_pages
        ]
        merged, usage = self._merger.merge(merge_input)
        self._record_cost(pipeline, usage)

        # Survivor = first member's page (preserves canonical name).
        survivor = member_pages[0]
        new_sources = [
            Source(file=s["file"], sections=list(s.get("sections", [])))
            for s in merged["sources"]
        ]
        survivor.frontmatter.sources = new_sources
        survivor.frontmatter.merged_from = list(merged["merged_from"])
        survivor.body = merged["body"]
        survivor.write()

        # Delete all other members.
        for p in member_pages[1:]:
            p.path.unlink()
            pipeline.record_item(
                Phase.LINK, p.name, status="done",
                action="merged_into", into=survivor.name,
            )

    def _assign_links(
        self,
        target,
        inventory: list,
        pipeline: Pipeline,
    ) -> None:
        links, usage = self._linker.assign(target, inventory)
        self._record_cost(pipeline, usage)

        path = self._paths.concept_for(target.name)
        page = ConceptPage.read(path)
        page.frontmatter.related = list(links["related"])
        page.frontmatter.prerequisites = list(links["prerequisites"])
        page.frontmatter.examples = list(links["examples"])
        page.frontmatter.contrasts = list(links["contrasts"])
        page.frontmatter.refines = list(links["refines"])
        page.write()
        pipeline.record_item(Phase.LINK, target.name, status="done")

    def _record_cost(self, pipeline: Pipeline, usage) -> None:
        token_usage = TokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_input_tokens=getattr(usage, "cached_input_tokens", 0),
        )
        cost = estimate_cost(Model.SONNET, token_usage)
        pipeline.record_cost(Phase.LINK, cost)
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/link/orchestrator.py tests/builder/link/test_orchestrator.py
git commit -m "feat(builder/link): orchestrator wires clustering/merge/link/MOCs to Pipeline"
```

---

## Task 9: Public API

**Files:**
- Modify: `src/builder/link/__init__.py`
- Create: `tests/builder/link/test_public_api.py`

- [ ] **Step 1: Update `__init__.py`**

```python
"""Link phase — clusters, dedupes, assigns typed links, generates MOCs."""
from builder.link.cardinality import (
    MAX_RELATED,
    MAX_PREREQUISITES,
    MAX_EXAMPLES,
    MAX_CONTRASTS,
    MAX_REFINES,
    enforce_link_cardinality,
)
from builder.link.inventory import ConceptSummary, build_inventory
from builder.link.clusters import Cluster, ClusterError, ClusterIdentifier
from builder.link.merger import ConceptMerger
from builder.link.linker import LinkAgent, LinkError
from builder.link.moc_generator import MOCGenerator
from builder.link.orchestrator import LinkOrchestrator

__all__ = [
    "MAX_RELATED", "MAX_PREREQUISITES", "MAX_EXAMPLES",
    "MAX_CONTRASTS", "MAX_REFINES", "enforce_link_cardinality",
    "ConceptSummary", "build_inventory",
    "Cluster", "ClusterError", "ClusterIdentifier",
    "ConceptMerger",
    "LinkAgent", "LinkError",
    "MOCGenerator",
    "LinkOrchestrator",
]
```

- [ ] **Step 2: Write `tests/builder/link/test_public_api.py`**

```python
def test_link_public_api():
    from builder.link import (
        MAX_RELATED, MAX_PREREQUISITES, MAX_EXAMPLES,
        MAX_CONTRASTS, MAX_REFINES, enforce_link_cardinality,
        ConceptSummary, build_inventory,
        Cluster, ClusterError, ClusterIdentifier,
        ConceptMerger,
        LinkAgent, LinkError,
        MOCGenerator,
        LinkOrchestrator,
    )
    assert MAX_RELATED == 8
    assert callable(enforce_link_cardinality)
```

- [ ] **Step 3: Run all tests, commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pytest
git add src/builder/link/__init__.py tests/builder/link/test_public_api.py
git commit -m "feat(builder/link): public API exports"
```
