# Builder Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Wire all 5 phases (Ingest → Transform → Link → QA → Emit) into a single end-to-end orchestrator with a CLI, pre-build cost estimation, real Anthropic API agent caller, real HTTP fetcher, and the user-facing `docs-to-skill` SKILL.md.

**Architecture:** `src/builder/integration/` holds the top-level orchestrator and CLI. The production AgentCaller (`AnthropicAgent`) wraps the Anthropic SDK; the production HTTPFetcher (`HTTPXFetcher`) wraps stdlib `urllib`. Tests use the existing CannedAgent/MockFetcher patterns. End-to-end integration test runs Ingest→Transform→Link→QA→Emit with mocks against a tiny fixture corpus and verifies a valid plugin appears.

**Tech Stack:** Python 3.11+ stdlib + matter_expert + all builder phase modules. The production AgentCaller imports the Anthropic SDK lazily so tests don't require it.

---

## File Structure

```
src/builder/integration/
├── __init__.py
├── builder.py              # BuilderOrchestrator — chains all 5 phases
├── cost_estimator.py       # Pre-build cost estimate from input directory
├── anthropic_agent.py      # AnthropicAgent (production AgentCaller)
├── http_fetcher.py         # UrllibFetcher (production HTTPFetcher)
└── cli.py                  # argparse CLI: create / resume / replay

tests/builder/integration/
├── __init__.py
├── conftest.py
├── test_cost_estimator.py
├── test_builder.py
└── test_cli.py             # CLI subprocess tests
```

Plus the top-level skill itself:
```
docs-to-skill/                 # The user-facing skill
├── SKILL.md                   # Triggers on "build a skill from documents..."
└── (nothing else — invokes the CLI)
```

---

## Task 1: Cost Estimator

**Files:**
- Create: `src/builder/integration/__init__.py` (empty)
- Create: `src/builder/integration/cost_estimator.py`
- Create: `tests/builder/integration/__init__.py` (empty)
- Create: `tests/builder/integration/test_cost_estimator.py`

- [ ] **Step 1: Write failing test**

```python
from pathlib import Path

from builder.integration.cost_estimator import (
    CostEstimate, PhaseEstimate, estimate_build_cost,
)
from builder.phases import Phase


def test_phase_estimate_construction():
    e = PhaseEstimate(phase=Phase.INGEST, low_usd=0.0, high_usd=1.20)
    assert e.low_usd == 0.0
    assert e.high_usd == 1.20


def test_cost_estimate_total():
    estimate = CostEstimate(
        per_phase=[
            PhaseEstimate(Phase.INGEST, 0.0, 1.20),
            PhaseEstimate(Phase.TRANSFORM, 4.50, 5.80),
        ],
        buffer_pct=0.20,
    )
    # low = 0.0 + 4.50 = 4.50; high = 1.20 + 5.80 = 7.00
    # buffer (high) = 0.20 * 7.00 = 1.40 → totals 8.40
    assert estimate.total_low_usd == 4.50 * 1.20  # +20% buffer
    assert estimate.total_high_usd == 7.00 * 1.20


def test_estimate_from_input_dir(tmp_path: Path):
    """A directory with N text files produces non-zero estimates for all phases."""
    (tmp_path / "a.md").write_text("# X\n" + "word " * 500)
    (tmp_path / "b.txt").write_text("plain text content " * 200)

    estimate = estimate_build_cost(input_dir=tmp_path, url_list=[])
    assert len(estimate.per_phase) == 5
    # Ingest is cheap (or zero) for text-only inputs.
    ingest = next(p for p in estimate.per_phase if p.phase == Phase.INGEST)
    assert ingest.low_usd == 0.0
    # Transform/Link/Emit should have positive estimates.
    transform = next(p for p in estimate.per_phase if p.phase == Phase.TRANSFORM)
    assert transform.high_usd > 0


def test_estimate_includes_urls(tmp_path: Path):
    """URL list adds to Ingest estimate."""
    estimate_no_urls = estimate_build_cost(input_dir=tmp_path, url_list=[])
    estimate_with_urls = estimate_build_cost(
        input_dir=tmp_path,
        url_list=["https://example.com/a", "https://example.com/b"],
    )
    # URLs touch Ingest (vision fallback heuristic for HTML pages).
    no_ingest = next(p for p in estimate_no_urls.per_phase if p.phase == Phase.INGEST)
    with_ingest = next(p for p in estimate_with_urls.per_phase if p.phase == Phase.INGEST)
    assert with_ingest.high_usd > no_ingest.high_usd


def test_estimate_formatted_breakdown():
    """`format()` produces a human breakdown matching design spec §7.1."""
    estimate = CostEstimate(
        per_phase=[
            PhaseEstimate(Phase.INGEST, 0.0, 1.20),
            PhaseEstimate(Phase.TRANSFORM, 4.50, 5.80),
            PhaseEstimate(Phase.LINK, 2.10, 2.10),
            PhaseEstimate(Phase.QA, 0.80, 0.80),
            PhaseEstimate(Phase.EMIT, 0.40, 0.40),
        ],
        buffer_pct=0.20,
    )
    output = estimate.format()
    assert "Ingest" in output
    assert "Buffer" in output
    assert "Total" in output
    assert "20%" in output
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/integration/cost_estimator.py`**

```python
"""Pre-build cost estimation per design spec §7.1."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from builder.cost_tracker import (
    MODEL_PRICES_USD_PER_MILLION, TokenUsage, estimate_cost,
)
from builder.phases import Model, Phase


# Tunable per-phase multipliers (rough heuristics).
TRANSLATION_TOKENS_PER_CHAR = 1.0  # 1 token per source char post-trans
LINK_TOKENS_PER_CONCEPT = 600      # rough per-concept link prompt size
QA_TOKENS_PER_SAMPLE = 800
EMIT_FIXED_OUTPUT_TOKENS = 1000

VISION_FALLBACK_FRACTION_LOW = 0.0
VISION_FALLBACK_FRACTION_HIGH = 0.30
URL_TOKENS_PER_PAGE = 2000

CONCEPTS_PER_SOURCE_LOW = 3
CONCEPTS_PER_SOURCE_HIGH = 10


@dataclass(frozen=True)
class PhaseEstimate:
    phase: Phase
    low_usd: float
    high_usd: float


@dataclass(frozen=True)
class CostEstimate:
    per_phase: list[PhaseEstimate]
    buffer_pct: float

    @property
    def subtotal_low_usd(self) -> float:
        return sum(p.low_usd for p in self.per_phase)

    @property
    def subtotal_high_usd(self) -> float:
        return sum(p.high_usd for p in self.per_phase)

    @property
    def total_low_usd(self) -> float:
        return round(self.subtotal_low_usd * (1 + self.buffer_pct), 4)

    @property
    def total_high_usd(self) -> float:
        return round(self.subtotal_high_usd * (1 + self.buffer_pct), 4)

    def format(self) -> str:
        lines = ["Estimated costs:"]
        for est in self.per_phase:
            if est.low_usd == est.high_usd:
                lines.append(f"  {est.phase.value:<10} ${est.high_usd:>6.2f}")
            else:
                lines.append(
                    f"  {est.phase.value:<10} ${est.low_usd:>6.2f} - ${est.high_usd:>6.2f}"
                )
        buffer_low = self.subtotal_low_usd * self.buffer_pct
        buffer_high = self.subtotal_high_usd * self.buffer_pct
        lines.append(
            f"  {'Buffer':<10} ${buffer_low:>6.2f} - ${buffer_high:>6.2f} "
            f"  ({int(self.buffer_pct * 100)}%)"
        )
        lines.append(f"  {'─' * 17}")
        lines.append(
            f"  {'Total':<10} ${self.total_low_usd:>6.2f} - ${self.total_high_usd:>6.2f}"
        )
        return "\n".join(lines)


def _file_size_chars(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, UnicodeDecodeError):
        return path.stat().st_size  # rough byte fallback


def estimate_build_cost(
    input_dir: Path,
    url_list: list[str],
    buffer_pct: float = 0.20,
) -> CostEstimate:
    """Estimate cost-per-phase for an upcoming build."""
    # Total input character count.
    total_chars = 0
    file_count = 0
    pdf_count = 0
    for path in input_dir.glob("*") if input_dir.exists() else []:
        if not path.is_file():
            continue
        file_count += 1
        total_chars += _file_size_chars(path)
        if path.suffix.lower() == ".pdf":
            pdf_count += 1

    # Ingest cost: text-only files are free. PDFs MAY require vision (Sonnet).
    vision_pages_low = int(pdf_count * VISION_FALLBACK_FRACTION_LOW)
    vision_pages_high = int(pdf_count * VISION_FALLBACK_FRACTION_HIGH)
    vision_cost_low = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=vision_pages_low * 1500,
                    output_tokens=vision_pages_low * 500),
    )
    vision_cost_high = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=vision_pages_high * 1500,
                    output_tokens=vision_pages_high * 500),
    )
    # URL fetch + parse: Ingest doesn't call LLM, but vision can be triggered
    # by URL pages with little body. Cost is essentially 0 for the URL-only path.
    url_cost = 0.0  # urllib + html parser, no LLM at ingest
    ingest = PhaseEstimate(
        Phase.INGEST,
        low_usd=round(vision_cost_low + url_cost, 4),
        high_usd=round(vision_cost_high + url_cost + 0.05 * len(url_list), 4),
    )

    # Transform cost: input chars → input tokens → Haiku translation + per-concept extract
    input_tokens = total_chars  # 1 token per char post-trans approximation
    estimated_concepts_low = file_count * CONCEPTS_PER_SOURCE_LOW
    estimated_concepts_high = file_count * CONCEPTS_PER_SOURCE_HIGH
    transform_low = estimate_cost(
        Model.HAIKU,
        TokenUsage(input_tokens=input_tokens * estimated_concepts_low // file_count
                    if file_count else 0,
                    output_tokens=estimated_concepts_low * 1500),
    )
    transform_high = estimate_cost(
        Model.HAIKU,
        TokenUsage(input_tokens=input_tokens * estimated_concepts_high // max(file_count, 1),
                    output_tokens=estimated_concepts_high * 1500),
    )
    transform = PhaseEstimate(
        Phase.TRANSFORM,
        low_usd=round(transform_low, 4),
        high_usd=round(transform_high, 4),
    )

    # Link cost: Sonnet, one prompt per concept (link assignment) + one cluster pass
    link_low = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=estimated_concepts_low * LINK_TOKENS_PER_CONCEPT,
                    output_tokens=estimated_concepts_low * 200),
    )
    link_high = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=estimated_concepts_high * LINK_TOKENS_PER_CONCEPT,
                    output_tokens=estimated_concepts_high * 200),
    )
    link = PhaseEstimate(
        Phase.LINK,
        low_usd=round(link_low, 4),
        high_usd=round(link_high, 4),
    )

    # QA cost: ~30% of concepts sampled across all LLM validators (Sonnet)
    qa_samples_low = int(estimated_concepts_low * 0.30)
    qa_samples_high = int(estimated_concepts_high * 0.30)
    qa_low = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=qa_samples_low * QA_TOKENS_PER_SAMPLE,
                    output_tokens=qa_samples_low * 100),
    )
    qa_high = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=qa_samples_high * QA_TOKENS_PER_SAMPLE,
                    output_tokens=qa_samples_high * 100),
    )
    qa = PhaseEstimate(
        Phase.QA,
        low_usd=round(qa_low, 4),
        high_usd=round(qa_high, 4),
    )

    # Emit cost: one Sonnet call for the SKILL.md trigger description
    emit_cost = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=2000, output_tokens=EMIT_FIXED_OUTPUT_TOKENS),
    )
    emit = PhaseEstimate(
        Phase.EMIT,
        low_usd=round(emit_cost, 4),
        high_usd=round(emit_cost, 4),
    )

    return CostEstimate(
        per_phase=[ingest, transform, link, qa, emit],
        buffer_pct=buffer_pct,
    )
```

- [ ] **Step 4: Run → 5 pass**

- [ ] **Step 5: Commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
git add src/builder/integration/ tests/builder/integration/
git commit -m "feat(builder/integration): pre-build cost estimator (spec §7.1)"
```

---

## Task 2: HTTPX Fetcher (production HTTPFetcher)

**Files:**
- Create: `src/builder/integration/http_fetcher.py`
- Create: `tests/builder/integration/test_http_fetcher.py`

Production HTTPFetcher using stdlib `urllib.request` (so we don't add a dependency).

- [ ] **Step 1: Write failing test**

```python
from unittest.mock import patch, MagicMock

import pytest

from builder.integration.http_fetcher import UrllibFetcher


def test_fetcher_returns_response_body():
    fake_response = MagicMock()
    fake_response.read.return_value = b"<html>body</html>"
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = lambda *a: None
    fake_response.headers.get_content_charset.return_value = "utf-8"

    with patch("builder.integration.http_fetcher.urllib.request.urlopen",
                return_value=fake_response):
        f = UrllibFetcher()
        text = f.fetch("https://example.com/x")
    assert text == "<html>body</html>"


def test_fetcher_handles_non_utf8():
    fake = MagicMock()
    fake.read.return_value = "héllo".encode("latin-1")
    fake.__enter__ = lambda s: s
    fake.__exit__ = lambda *a: None
    fake.headers.get_content_charset.return_value = "latin-1"

    with patch("builder.integration.http_fetcher.urllib.request.urlopen",
                return_value=fake):
        f = UrllibFetcher()
        text = f.fetch("https://x")
    assert text == "héllo"


def test_fetcher_uses_default_user_agent():
    """Requests include a User-Agent header (some servers reject default Python UA)."""
    fake_response = MagicMock()
    fake_response.read.return_value = b"ok"
    fake_response.__enter__ = lambda s: s
    fake_response.__exit__ = lambda *a: None
    fake_response.headers.get_content_charset.return_value = "utf-8"

    captured = {}
    def capture_open(req, **kw):
        captured["headers"] = dict(req.headers)
        return fake_response

    with patch("builder.integration.http_fetcher.urllib.request.urlopen",
                side_effect=capture_open):
        UrllibFetcher().fetch("https://x")

    assert any("User-agent" in k or "User-Agent" in k for k in captured["headers"])
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/integration/http_fetcher.py`**

```python
"""Production HTTPFetcher using stdlib urllib (no third-party HTTP client)."""
from __future__ import annotations

import urllib.request


DEFAULT_USER_AGENT = "matter-expert-builder/0.0.1"
DEFAULT_TIMEOUT_SECONDS = 30


class UrllibFetcher:
    """Fetch a URL and return the decoded text body."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._user_agent = user_agent
        self._timeout = timeout

    def fetch(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self._user_agent},
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            data: bytes = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace")
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/integration/http_fetcher.py tests/builder/integration/test_http_fetcher.py
git commit -m "feat(builder/integration): UrllibFetcher (production HTTPFetcher)"
```

---

## Task 3: Anthropic Agent (production AgentCaller, lazy import)

**Files:**
- Create: `src/builder/integration/anthropic_agent.py`
- Create: `tests/builder/integration/test_anthropic_agent.py`

Production AgentCaller that wraps the Anthropic SDK. Imports the SDK lazily so tests don't require it.

- [ ] **Step 1: Write failing test**

```python
from unittest.mock import MagicMock, patch

import pytest

from builder.integration.anthropic_agent import (
    AnthropicAgent,
    MODEL_ID_MAP,
)


def test_model_id_map_covers_all_models():
    assert "haiku" in MODEL_ID_MAP
    assert "sonnet" in MODEL_ID_MAP
    assert "opus" in MODEL_ID_MAP


def test_call_invokes_sdk_with_correct_model():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="response text")]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.usage.cache_read_input_tokens = 0
    mock_client.messages.create.return_value = mock_response

    agent = AnthropicAgent(client=mock_client, api_key="sk-x")
    response = agent.call("test prompt", model="haiku")

    assert response.text == "response text"
    assert response.input_tokens == 100
    assert response.output_tokens == 50
    # Called with the mapped Haiku model ID
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == MODEL_ID_MAP["haiku"]


def test_call_includes_images_when_provided():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="ok")]
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 10
    mock_response.usage.cache_read_input_tokens = 0
    mock_client.messages.create.return_value = mock_response

    agent = AnthropicAgent(client=mock_client, api_key="sk-x")
    response = agent.call("describe this", model="sonnet",
                            images=[b"\x89PNG\r\n\x1a\n"])

    assert response.text == "ok"
    # Image content block included
    messages = mock_client.messages.create.call_args.kwargs["messages"]
    content = messages[0]["content"]
    assert any(
        block.get("type") == "image" for block in content if isinstance(block, dict)
    )


def test_call_propagates_cached_input_tokens():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="ok")]
    mock_response.usage.input_tokens = 0
    mock_response.usage.output_tokens = 100
    mock_response.usage.cache_read_input_tokens = 500
    mock_client.messages.create.return_value = mock_response

    agent = AnthropicAgent(client=mock_client, api_key="sk-x")
    response = agent.call("prompt", model="haiku")

    assert response.cached_input_tokens == 500
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/integration/anthropic_agent.py`**

```python
"""Production AgentCaller using the Anthropic SDK (imported lazily)."""
from __future__ import annotations

import base64
import os

from builder.ingest.protocols import AgentResponse


# Map our model identifier → Anthropic API model ID. These map to current
# stable model versions; update when newer models are released.
MODEL_ID_MAP = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
}


DEFAULT_MAX_TOKENS = 4096


class AnthropicAgent:
    """AgentCaller that delegates to the Anthropic Messages API."""

    def __init__(
        self,
        client=None,
        api_key: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        if client is None:
            # Lazy import so test envs without the SDK still work.
            import anthropic
            client = anthropic.Anthropic(
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            )
        self._client = client
        self._max_tokens = max_tokens

    def call(
        self,
        prompt: str,
        *,
        model: str = "haiku",
        images: list[bytes] | None = None,
    ) -> AgentResponse:
        sdk_model = MODEL_ID_MAP.get(model, model)
        content_blocks: list[dict] = []
        for img in images or []:
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(img).decode("ascii"),
                },
            })
        content_blocks.append({"type": "text", "text": prompt})

        response = self._client.messages.create(
            model=sdk_model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": content_blocks}],
        )
        text = "".join(
            block.text for block in response.content
            if getattr(block, "text", None)
        )
        return AgentResponse(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cached_input_tokens=getattr(
                response.usage, "cache_read_input_tokens", 0,
            ) or 0,
        )
```

- [ ] **Step 4: Run → 4 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/integration/anthropic_agent.py tests/builder/integration/test_anthropic_agent.py
git commit -m "feat(builder/integration): AnthropicAgent (production AgentCaller)"
```

---

## Task 4: BuilderOrchestrator (chains all 5 phases)

**Files:**
- Create: `src/builder/integration/builder.py`
- Create: `tests/builder/integration/conftest.py`
- Create: `tests/builder/integration/test_builder.py`

End-to-end orchestrator that runs Ingest → Transform → Link → QA → Emit.

- [ ] **Step 1: Write `tests/builder/integration/conftest.py`**

```python
"""Fixtures for integration tests.

Reuses CannedAgent and a small input directory fixture.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from builder.ingest.protocols import AgentResponse


@dataclass
class CannedAgent:
    recipes: dict[str, str] = field(default_factory=dict)
    default: str = "{}"
    canned_input_tokens: int = 100
    canned_output_tokens: int = 50
    calls: list[dict] = field(default_factory=list)

    def call(self, prompt, *, model="haiku", images=None) -> AgentResponse:
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


@dataclass
class MockFetcher:
    responses: dict[str, str] = field(default_factory=dict)

    def fetch(self, url: str) -> str:
        return self.responses.get(url, "<html><body>default</body></html>")


@pytest.fixture
def canned_agent() -> CannedAgent:
    return CannedAgent()


@pytest.fixture
def mock_fetcher() -> MockFetcher:
    return MockFetcher()


@pytest.fixture
def sample_input_dir(tmp_path: Path) -> Path:
    """A directory with one markdown document for an end-to-end build."""
    d = tmp_path / "inputs"
    d.mkdir()
    (d / "handbook.md").write_text(
        "# Handbook\n\n"
        "## Authentication\n\n"
        "Authentication verifies who you are.\n\n"
        "## Authorization\n\n"
        "Authorization decides what you can do.\n",
        encoding="utf-8",
    )
    return d


def _outline_json() -> str:
    return json.dumps({"entries": [
        {"concept_name": "authentication", "title": "Authentication",
         "source_sections": [], "estimated_tokens": 600},
        {"concept_name": "authorization", "title": "Authorization",
         "source_sections": [], "estimated_tokens": 600},
    ]})


@pytest.fixture
def full_pipeline_agent(canned_agent: CannedAgent) -> CannedAgent:
    """Pre-loaded CannedAgent with recipes for a full end-to-end build."""
    canned_agent.recipes["Identify the atomic concepts"] = _outline_json()
    canned_agent.recipes["Target concept"] = "# Concept\n\nBody.\n"
    canned_agent.recipes["Source outline"] = json.dumps({"missed_topics": []})
    canned_agent.recipes["Inventory"] = json.dumps({"clusters": []})
    canned_agent.recipes["Target concept:"] = json.dumps({
        "related": [], "prerequisites": [], "examples": [],
        "contrasts": [], "refines": [],
    })
    # QA validators: all pass
    canned_agent.default = json.dumps({
        "verdict": "pass", "reasons": [],
        "missed_topics": [], "unsupported_claims": [], "issues": [],
    })
    return canned_agent
```

- [ ] **Step 2: Write failing test `tests/builder/integration/test_builder.py`**

```python
from pathlib import Path

from builder.integration.builder import BuilderOrchestrator, BuildConfig
from builder.phases import Phase


def test_end_to_end_build_produces_plugin(
    sample_input_dir: Path, full_pipeline_agent, mock_fetcher, tmp_path,
):
    config = BuildConfig(
        run_id="2026-05-10-test",
        input_dir=sample_input_dir,
        url_list=[],
        run_dir=tmp_path / "run",
        plugin_root=tmp_path / "plugin",
        plugin_name="test-skill",
        plugin_version="0.1.0",
        plugin_description="Test expert skill.",
        author="builder",
    )
    builder = BuilderOrchestrator(
        agent=full_pipeline_agent,
        fetcher=mock_fetcher,
    )
    pipeline = builder.build(config=config)

    # All 5 phases complete.
    for phase in Phase:
        assert pipeline.is_phase_complete(phase), f"phase {phase} not complete"

    # Plugin produced.
    assert (config.plugin_root / ".claude-plugin" / "plugin.json").exists()
    assert (config.plugin_root / "skills" / "test-skill" / "SKILL.md").exists()
    assert (config.plugin_root / "skills" / "test-skill" / "vault" / "concepts").exists()


def test_resume_skips_already_completed_phases(
    sample_input_dir: Path, full_pipeline_agent, mock_fetcher, tmp_path,
):
    """Calling build() twice with the same run_dir resumes — completed phases
    do not re-run."""
    config = BuildConfig(
        run_id="x", input_dir=sample_input_dir, url_list=[],
        run_dir=tmp_path / "run",
        plugin_root=tmp_path / "plugin",
        plugin_name="x", plugin_version="0.1.0",
        plugin_description="d", author="a",
    )
    builder = BuilderOrchestrator(agent=full_pipeline_agent, fetcher=mock_fetcher)
    first = builder.build(config=config)
    calls_before = len(full_pipeline_agent.calls)

    # Build again; the second invocation should resume — but since all
    # phases already completed, no additional agent calls are made.
    second = builder.build(config=config)
    calls_after = len(full_pipeline_agent.calls)

    # No extra calls because resume sees all phases as completed.
    assert calls_after == calls_before


def test_build_replays_target_phase_when_requested(
    sample_input_dir: Path, full_pipeline_agent, mock_fetcher, tmp_path,
):
    config = BuildConfig(
        run_id="x", input_dir=sample_input_dir, url_list=[],
        run_dir=tmp_path / "run",
        plugin_root=tmp_path / "plugin",
        plugin_name="x", plugin_version="0.1.0",
        plugin_description="d", author="a",
        replay_from=Phase.LINK,
    )
    builder = BuilderOrchestrator(agent=full_pipeline_agent, fetcher=mock_fetcher)
    # First a clean build...
    builder.build(config=BuildConfig(
        run_id=config.run_id, input_dir=config.input_dir, url_list=[],
        run_dir=config.run_dir, plugin_root=config.plugin_root,
        plugin_name=config.plugin_name, plugin_version=config.plugin_version,
        plugin_description=config.plugin_description, author=config.author,
    ))
    calls_before = len(full_pipeline_agent.calls)

    # Now replay from LINK onwards.
    builder.build(config=config)
    # Replay re-runs Link + QA + Emit → at least Emit's SKILL.md call should fire.
    assert len(full_pipeline_agent.calls) > calls_before
```

- [ ] **Step 3: Run → fail**

- [ ] **Step 4: Implement `src/builder/integration/builder.py`**

```python
"""End-to-end builder orchestrator chaining Ingest → Transform → Link → QA → Emit."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from builder.emit.orchestrator import EmitConfig, EmitOrchestrator
from builder.ingest.orchestrator import IngestOrchestrator
from builder.ingest.protocols import AgentCaller, HTTPFetcher
from builder.link.orchestrator import LinkOrchestrator
from builder.phases import Phase
from builder.pipeline import Pipeline
from builder.qa.orchestrator import QAOrchestrator
from builder.transform.orchestrator import TransformOrchestrator
from matter_expert import VaultPaths


@dataclass
class BuildConfig:
    run_id: str
    input_dir: Path
    url_list: list[str]
    run_dir: Path
    plugin_root: Path
    plugin_name: str
    plugin_version: str
    plugin_description: str
    author: str
    replay_from: Phase | None = None


class BuilderOrchestrator:
    """End-to-end builder. Chains all 5 phases with Pipeline state mgmt."""

    def __init__(self, agent: AgentCaller, fetcher: HTTPFetcher) -> None:
        self._agent = agent
        self._fetcher = fetcher

    def build(self, config: BuildConfig) -> Pipeline:
        # Resume if state file exists; otherwise create.
        state_file = config.run_dir / "pipeline_state.json"
        if state_file.exists():
            pipeline = Pipeline.resume(config.run_dir)
        else:
            config.run_dir.mkdir(parents=True, exist_ok=True)
            pipeline = Pipeline.create(
                run_id=config.run_id,
                input_dir=config.input_dir,
                url_list=list(config.url_list),
                run_dir=config.run_dir,
            )

        if config.replay_from is not None:
            pipeline.replay_from(config.replay_from)

        # Working directories.
        work_root = config.run_dir / "work"
        work_root.mkdir(parents=True, exist_ok=True)
        vault_dir = work_root / "vault"
        ingest_state_file = work_root / "ingest_results.json"

        vault = VaultPaths(root=vault_dir)
        ingest_results = None

        # Phase 1: Ingest
        if not pipeline.is_phase_complete(Phase.INGEST):
            pipeline.mark_phase_started(Phase.INGEST)
            ingest = IngestOrchestrator(agent=self._agent, fetcher=self._fetcher)
            file_results = ingest.ingest_directory(
                directory=config.input_dir, pipeline=pipeline,
            )
            url_results = ingest.ingest_urls(
                urls=list(config.url_list), pipeline=pipeline,
            )
            ingest_results = {**file_results, **url_results}
            # Persist a lightweight summary of ingest results — what Transform needs.
            self._persist_ingest_summary(ingest_results, ingest_state_file)
            pipeline.mark_phase_completed(Phase.INGEST)
        elif ingest_state_file.exists():
            # Resume path: re-hydrate ingest_results from disk.
            ingest_results = self._load_ingest_summary(ingest_state_file)

        # Phase 2: Transform
        if not pipeline.is_phase_complete(Phase.TRANSFORM):
            if ingest_results is None:
                raise RuntimeError(
                    "transform phase cannot run: ingest results not available "
                    "(neither in-memory nor persisted)"
                )
            pipeline.mark_phase_started(Phase.TRANSFORM)
            transform = TransformOrchestrator(
                agent=self._agent, vault_dir=vault_dir,
            )
            transform.transform(
                ingest_results=ingest_results, pipeline=pipeline,
            )
            pipeline.mark_phase_completed(Phase.TRANSFORM)

        # Phase 3: Link
        if not pipeline.is_phase_complete(Phase.LINK):
            linker = LinkOrchestrator(agent=self._agent, vault_dir=vault_dir)
            linker.link(pipeline=pipeline)
            # link.link() already marks completed

        # Phase 4: QA
        if not pipeline.is_phase_complete(Phase.QA):
            qa_dir = work_root / "qa"
            qa = QAOrchestrator(agent=self._agent, source_outlines={})
            qa.run(
                vault=vault, pipeline=pipeline,
                report_path=qa_dir / "qa_report.json",
            )
            # qa.run() already marks completed

        # Phase 5: Emit
        if not pipeline.is_phase_complete(Phase.EMIT):
            emit_cfg = EmitConfig(
                plugin_name=config.plugin_name,
                plugin_version=config.plugin_version,
                plugin_description=config.plugin_description,
                author=config.author,
            )
            emitter = EmitOrchestrator(agent=self._agent, config=emit_cfg)
            emitter.emit(
                vault=vault, plugin_root=config.plugin_root,
                pipeline=pipeline,
            )

        return pipeline

    def _persist_ingest_summary(self, results: dict, path: Path) -> None:
        """Save ingest_results to disk so resume can re-hydrate."""
        path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            source_id: {
                "content": r.content,
                "meta": r.meta.to_dict(),
            }
            for source_id, r in results.items()
        }
        path.write_text(
            json.dumps(serializable, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_ingest_summary(self, path: Path) -> dict:
        from builder.ingest.meta import DocumentMeta
        from builder.ingest.protocols import ConvertResult
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {
            sid: ConvertResult(
                content=item["content"],
                meta=DocumentMeta.from_dict(item["meta"]),
            )
            for sid, item in raw.items()
        }
```

- [ ] **Step 5: Run → 3 pass**

- [ ] **Step 6: Commit**

```bash
git add src/builder/integration/builder.py tests/builder/integration/conftest.py \
        tests/builder/integration/test_builder.py
git commit -m "feat(builder/integration): BuilderOrchestrator chains all 5 phases"
```

---

## Task 5: CLI

**Files:**
- Create: `src/builder/integration/cli.py`
- Create: `tests/builder/integration/test_cli.py`

`python -m builder.integration.cli build --input ... --output ... --name ...`

- [ ] **Step 1: Write failing test `tests/builder/integration/test_cli.py`**

```python
import subprocess
import sys

from pathlib import Path


def test_cli_estimate_subcommand(sample_input_dir, tmp_path):
    """`estimate` produces a cost breakdown without running the build."""
    result = subprocess.run(
        [
            sys.executable, "-m", "builder.integration.cli",
            "estimate",
            "--input", str(sample_input_dir),
        ],
        capture_output=True, text=True, check=True,
    )
    assert "Estimated costs" in result.stdout
    assert "Ingest" in result.stdout
    assert "Total" in result.stdout


def test_cli_help_lists_subcommands():
    result = subprocess.run(
        [sys.executable, "-m", "builder.integration.cli", "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "estimate" in result.stdout
    assert "build" in result.stdout
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/integration/cli.py`**

```python
"""CLI entry point for the docs-to-skill builder."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from builder.integration.cost_estimator import estimate_build_cost
from builder.phases import Phase


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docs-to-skill",
        description="Build an expert skill from a directory of documents.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # estimate
    est = sub.add_parser("estimate", help="Print pre-build cost estimate.")
    est.add_argument("--input", type=Path, required=True)
    est.add_argument("--url", action="append", default=[],
                     help="URL to include (may be passed multiple times)")

    # build
    build = sub.add_parser("build", help="Run the full builder pipeline.")
    build.add_argument("--input", type=Path, required=True)
    build.add_argument("--url", action="append", default=[])
    build.add_argument("--run-dir", type=Path, required=True)
    build.add_argument("--plugin-root", type=Path, required=True)
    build.add_argument("--name", required=True)
    build.add_argument("--version", default="0.1.0")
    build.add_argument("--description", default="Generated expert skill.")
    build.add_argument("--author", default="docs-to-skill")
    build.add_argument("--replay-from", choices=[p.value for p in Phase],
                       default=None)
    build.add_argument("--yes", action="store_true",
                       help="Skip cost confirmation prompt.")

    args = parser.parse_args(argv)

    if args.cmd == "estimate":
        estimate = estimate_build_cost(
            input_dir=args.input, url_list=list(args.url),
        )
        print(estimate.format())
        return 0

    if args.cmd == "build":
        # Show cost estimate and confirm unless --yes.
        estimate = estimate_build_cost(
            input_dir=args.input, url_list=list(args.url),
        )
        print(estimate.format())
        if not args.yes:
            reply = input("\nProceed? [Y/n] ").strip().lower()
            if reply and reply not in ("y", "yes"):
                print("Aborted.")
                return 1

        run_id = args.run_dir.name
        from builder.integration.anthropic_agent import AnthropicAgent
        from builder.integration.builder import (
            BuilderOrchestrator, BuildConfig,
        )
        from builder.integration.http_fetcher import UrllibFetcher

        config = BuildConfig(
            run_id=run_id,
            input_dir=args.input,
            url_list=list(args.url),
            run_dir=args.run_dir,
            plugin_root=args.plugin_root,
            plugin_name=args.name,
            plugin_version=args.version,
            plugin_description=args.description,
            author=args.author,
            replay_from=Phase(args.replay_from) if args.replay_from else None,
        )
        builder = BuilderOrchestrator(
            agent=AnthropicAgent(), fetcher=UrllibFetcher(),
        )
        pipeline = builder.build(config=config)
        print(f"\nDone. Plugin written to {args.plugin_root}.")
        actual = pipeline.state.cost_tracker.get("actual_so_far_usd", 0.0)
        print(f"Actual cost: ${actual:.2f}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run → 2 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/integration/cli.py tests/builder/integration/test_cli.py
git commit -m "feat(builder/integration): CLI with estimate + build subcommands"
```

---

## Task 6: docs-to-skill SKILL.md + Public API + README

**Files:**
- Create: `docs-to-skill/SKILL.md`
- Modify: `src/builder/integration/__init__.py`
- Create: `tests/builder/integration/test_public_api.py`
- Modify: `README.md`

- [ ] **Step 1: Create `docs-to-skill/SKILL.md` (the user-facing skill)**

```markdown
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
```

- [ ] **Step 2: Update `src/builder/integration/__init__.py`**

```python
"""End-to-end builder integration: orchestrator + CLI + production adapters."""
from builder.integration.cost_estimator import (
    CostEstimate, PhaseEstimate, estimate_build_cost,
)
from builder.integration.http_fetcher import UrllibFetcher
from builder.integration.anthropic_agent import AnthropicAgent, MODEL_ID_MAP
from builder.integration.builder import BuildConfig, BuilderOrchestrator

__all__ = [
    "CostEstimate", "PhaseEstimate", "estimate_build_cost",
    "UrllibFetcher",
    "AnthropicAgent", "MODEL_ID_MAP",
    "BuildConfig", "BuilderOrchestrator",
]
```

- [ ] **Step 3: Write `tests/builder/integration/test_public_api.py`**

```python
def test_integration_public_api():
    from builder.integration import (
        CostEstimate, PhaseEstimate, estimate_build_cost,
        UrllibFetcher,
        AnthropicAgent, MODEL_ID_MAP,
        BuildConfig, BuilderOrchestrator,
    )
    assert callable(estimate_build_cost)
    assert "haiku" in MODEL_ID_MAP
```

- [ ] **Step 4: Append "End-to-end builder" section to README.md**

```markdown

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
```

- [ ] **Step 5: Run all tests, commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pytest
git add docs-to-skill/ src/builder/integration/__init__.py \
        tests/builder/integration/test_public_api.py README.md
git commit -m "feat(builder/integration): public API, docs-to-skill SKILL.md, README section"
```
