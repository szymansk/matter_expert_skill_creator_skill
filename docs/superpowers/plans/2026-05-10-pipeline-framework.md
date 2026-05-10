# Pipeline Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the orchestration shell for the docs-to-skill builder pipeline — state persistence, run create/resume/replay, model+effort routing per phase, cost tracking, and failure classification — without any actual phase implementation.

**Architecture:** A new `src/builder/` package with 5 modules: `phases` (config types), `cost_tracker` (pricing), `failures` (retry/classification), `state` (PipelineState + JSON I/O under `~/.docs-to-skill/<run-id>/`), and `pipeline` (the orchestrator class). The framework provides a Pipeline class that records what each phase did without knowing what any phase actually does — phases (subprojects 4-8) plug in by calling `pipeline.mark_phase_started(...)`, `pipeline.record_item(...)`, `pipeline.record_cost(...)`, etc.

**Tech Stack:** Python 3.11+, stdlib (`json`, `dataclasses`, `enum`, `pathlib`, `datetime`, `time`, `functools`), pytest. May import from `matter_expert` if useful but does not need to.

---

## Task 1: Builder Package Scaffolding

**Files:**
- Create: `src/builder/__init__.py`
- Create: `tests/builder/__init__.py`
- Create: `tests/builder/test_smoke.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Update `pyproject.toml` to discover the new `builder` package**

Replace the `[tool.setuptools.packages.find]` section with:

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["matter_expert*", "runtime*", "builder*"]
```

- [ ] **Step 2: Create `src/builder/__init__.py`**

```python
"""Builder pipeline framework and phases.

Subproject 3 (this code) ships the orchestration shell only:
state, cost tracking, failure handling, model routing.
Subprojects 4-8 add the actual phase implementations.
"""

__version__ = "0.0.1"
```

- [ ] **Step 3: Create empty `tests/builder/__init__.py`** (empty file)

- [ ] **Step 4: Write smoke test `tests/builder/test_smoke.py`**

```python
import builder


def test_builder_package_importable():
    assert builder.__version__ == "0.0.1"
```

- [ ] **Step 5: Reinstall package and run smoke test**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/builder/ -v
```

Expected: 1 test passes.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/builder/ tests/builder/__init__.py tests/builder/test_smoke.py
git commit -m "chore: scaffold builder package for subproject 3"
```

---

## Task 2: Phase, Model, Effort Enums + PhaseConfig

**Files:**
- Create: `src/builder/phases.py`
- Create: `tests/builder/test_phases.py`

- [ ] **Step 1: Write failing test `tests/builder/test_phases.py`**

```python
from builder.phases import (
    Phase,
    Model,
    Effort,
    PhaseConfig,
    DEFAULT_CONFIGS,
    config_for_phase,
)


def test_phase_enum_has_five_values():
    """The 5 pipeline phases per the design spec."""
    assert {p.value for p in Phase} == {
        "ingest", "transform", "link", "qa", "emit"
    }


def test_phase_enum_iteration_order_matches_pipeline_order():
    """Iteration order is the order phases run."""
    assert list(Phase) == [
        Phase.INGEST,
        Phase.TRANSFORM,
        Phase.LINK,
        Phase.QA,
        Phase.EMIT,
    ]


def test_model_enum_values():
    assert {m.value for m in Model} == {"haiku", "sonnet", "opus"}


def test_effort_enum_values():
    assert {e.value for e in Effort} == {"low", "medium", "high"}


def test_phase_config_construction():
    cfg = PhaseConfig(phase=Phase.INGEST, model=Model.HAIKU, effort=Effort.LOW)
    assert cfg.phase == Phase.INGEST
    assert cfg.model == Model.HAIKU
    assert cfg.effort == Effort.LOW


def test_default_configs_have_one_per_phase():
    """Every phase has exactly one default config."""
    phases_in_defaults = {cfg.phase for cfg in DEFAULT_CONFIGS}
    assert phases_in_defaults == set(Phase)
    assert len(DEFAULT_CONFIGS) == 5


def test_default_configs_match_design_spec():
    """Per spec section 4.1: model and effort per phase."""
    by_phase = {cfg.phase: cfg for cfg in DEFAULT_CONFIGS}
    assert by_phase[Phase.INGEST].model == Model.HAIKU
    assert by_phase[Phase.INGEST].effort == Effort.LOW
    assert by_phase[Phase.TRANSFORM].model == Model.HAIKU
    assert by_phase[Phase.TRANSFORM].effort == Effort.MEDIUM
    assert by_phase[Phase.LINK].model == Model.SONNET
    assert by_phase[Phase.LINK].effort == Effort.HIGH
    assert by_phase[Phase.EMIT].model == Model.SONNET
    assert by_phase[Phase.EMIT].effort == Effort.HIGH


def test_config_for_phase_lookup():
    cfg = config_for_phase(Phase.LINK, DEFAULT_CONFIGS)
    assert cfg.phase == Phase.LINK
    assert cfg.model == Model.SONNET


def test_config_for_phase_missing_raises():
    import pytest
    custom = [PhaseConfig(Phase.INGEST, Model.HAIKU, Effort.LOW)]
    with pytest.raises(KeyError):
        config_for_phase(Phase.LINK, custom)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/test_phases.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/builder/phases.py`**

```python
"""Pipeline phase definitions and per-phase model/effort configuration."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Phase(Enum):
    """The 5 phases of the docs-to-skill builder pipeline.

    Iteration order matches execution order.
    """
    INGEST = "ingest"
    TRANSFORM = "transform"
    LINK = "link"
    QA = "qa"
    EMIT = "emit"


class Model(Enum):
    """Anthropic model identifiers used by phase agents."""
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


class Effort(Enum):
    """Effort levels controlling extended-thinking budget and prompt depth."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class PhaseConfig:
    """Model + effort assignment for a single phase."""
    phase: Phase
    model: Model
    effort: Effort


# Default per-phase configuration per design spec section 4.1.
# QA is "mixed" in practice — most validators run locally or on Haiku.
# This default is the QA-Agent's effort level (the meta-orchestrator).
DEFAULT_CONFIGS: list[PhaseConfig] = [
    PhaseConfig(Phase.INGEST, Model.HAIKU, Effort.LOW),
    PhaseConfig(Phase.TRANSFORM, Model.HAIKU, Effort.MEDIUM),
    PhaseConfig(Phase.LINK, Model.SONNET, Effort.HIGH),
    PhaseConfig(Phase.QA, Model.SONNET, Effort.MEDIUM),
    PhaseConfig(Phase.EMIT, Model.SONNET, Effort.HIGH),
]


def config_for_phase(phase: Phase, configs: list[PhaseConfig]) -> PhaseConfig:
    """Return the PhaseConfig for `phase` from a list of configs.

    Raises:
        KeyError: if no config matches.
    """
    for cfg in configs:
        if cfg.phase == phase:
            return cfg
    raise KeyError(f"no config for phase {phase}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/test_phases.py -v`
Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/builder/phases.py tests/builder/test_phases.py
git commit -m "feat(builder): Phase/Model/Effort enums + PhaseConfig"
```

---

## Task 3: Cost Tracker — TokenUsage + Pricing

**Files:**
- Create: `src/builder/cost_tracker.py`
- Create: `tests/builder/test_cost_tracker.py`

- [ ] **Step 1: Write failing test `tests/builder/test_cost_tracker.py`**

```python
from builder.cost_tracker import (
    TokenUsage,
    MODEL_PRICES_USD_PER_MILLION,
    estimate_cost,
    format_cost_breakdown,
)
from builder.phases import Model, Phase


def test_token_usage_construction():
    usage = TokenUsage(input_tokens=1000, output_tokens=500)
    assert usage.input_tokens == 1000
    assert usage.output_tokens == 500
    assert usage.cached_input_tokens == 0


def test_token_usage_with_cached_tokens():
    usage = TokenUsage(
        input_tokens=1000,
        output_tokens=500,
        cached_input_tokens=200,
    )
    assert usage.cached_input_tokens == 200


def test_model_prices_cover_all_models():
    for model in Model:
        assert model in MODEL_PRICES_USD_PER_MILLION
        assert "input" in MODEL_PRICES_USD_PER_MILLION[model]
        assert "output" in MODEL_PRICES_USD_PER_MILLION[model]


def test_estimate_cost_haiku():
    """Haiku at default prices: 1k input + 500 output @ $1/$5 per million."""
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    cost = estimate_cost(Model.HAIKU, usage)
    expected = (
        MODEL_PRICES_USD_PER_MILLION[Model.HAIKU]["input"]
        + MODEL_PRICES_USD_PER_MILLION[Model.HAIKU]["output"]
    )
    assert cost == expected


def test_estimate_cost_zero_tokens():
    cost = estimate_cost(Model.SONNET, TokenUsage(input_tokens=0, output_tokens=0))
    assert cost == 0.0


def test_estimate_cost_cached_input_is_cheaper():
    """Cached input tokens cost 10% of regular input tokens."""
    regular = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=1_000_000, output_tokens=0),
    )
    cached = estimate_cost(
        Model.SONNET,
        TokenUsage(
            input_tokens=0,
            output_tokens=0,
            cached_input_tokens=1_000_000,
        ),
    )
    assert cached < regular
    assert cached == regular * 0.1


def test_format_cost_breakdown_simple():
    breakdown = {
        Phase.INGEST: 0.50,
        Phase.TRANSFORM: 4.20,
        Phase.LINK: 1.80,
        Phase.QA: 0.60,
        Phase.EMIT: 0.30,
    }
    output = format_cost_breakdown(breakdown, buffer_pct=0.20)

    # Output should mention each phase, the buffer, and the total
    assert "ingest" in output.lower()
    assert "transform" in output.lower()
    assert "link" in output.lower()
    assert "qa" in output.lower()
    assert "emit" in output.lower()
    assert "buffer" in output.lower() or "puffer" in output.lower()
    # Buffer is 20% of subtotal 7.40 = 1.48
    # Total is 7.40 + 1.48 = 8.88
    assert "8.88" in output


def test_format_cost_breakdown_zero_buffer():
    breakdown = {Phase.INGEST: 1.0, Phase.EMIT: 1.0}
    output = format_cost_breakdown(breakdown, buffer_pct=0.0)
    assert "2.00" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/test_cost_tracker.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/builder/cost_tracker.py`**

```python
"""Cost estimation and tracking for the builder pipeline.

Pricing constants reflect Anthropic's per-million-token rates. Cached
input tokens cost 10% of normal input tokens (per Anthropic's prompt
caching docs). Adjust `MODEL_PRICES_USD_PER_MILLION` if prices change.
"""
from __future__ import annotations

from dataclasses import dataclass

from builder.phases import Model, Phase


CACHED_INPUT_DISCOUNT = 0.10  # cached input tokens cost 10% of normal


# Per-million-token prices in USD.
MODEL_PRICES_USD_PER_MILLION: dict[Model, dict[str, float]] = {
    Model.HAIKU: {"input": 1.0, "output": 5.0},
    Model.SONNET: {"input": 3.0, "output": 15.0},
    Model.OPUS: {"input": 15.0, "output": 75.0},
}


@dataclass(frozen=True)
class TokenUsage:
    """Token consumption of a single agent call."""
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0


def estimate_cost(model: Model, usage: TokenUsage) -> float:
    """Estimate USD cost for `usage` on `model`."""
    prices = MODEL_PRICES_USD_PER_MILLION[model]
    per_million = 1_000_000

    input_cost = usage.input_tokens * prices["input"] / per_million
    output_cost = usage.output_tokens * prices["output"] / per_million
    cached_cost = (
        usage.cached_input_tokens
        * prices["input"] * CACHED_INPUT_DISCOUNT
        / per_million
    )
    return input_cost + output_cost + cached_cost


def format_cost_breakdown(
    per_phase_usd: dict[Phase, float],
    buffer_pct: float = 0.20,
) -> str:
    """Format a per-phase USD breakdown plus buffer + total as a human string."""
    lines = ["Estimated costs:"]
    subtotal = 0.0
    for phase in Phase:
        amount = per_phase_usd.get(phase, 0.0)
        lines.append(f"  {phase.value:<10} ${amount:>6.2f}")
        subtotal += amount

    buffer = subtotal * buffer_pct
    total = subtotal + buffer

    lines.append(f"  {'Buffer':<10} ${buffer:>6.2f}  ({int(buffer_pct * 100)}%)")
    lines.append(f"  {'─' * 17}")
    lines.append(f"  {'Total':<10} ${total:>6.2f}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/test_cost_tracker.py -v`
Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/builder/cost_tracker.py tests/builder/test_cost_tracker.py
git commit -m "feat(builder): cost tracker with per-model pricing + breakdown formatter"
```

---

## Task 4: Failure Classification + Retry Decorator

**Files:**
- Create: `src/builder/failures.py`
- Create: `tests/builder/test_failures.py`

- [ ] **Step 1: Write failing test `tests/builder/test_failures.py`**

```python
import time

import pytest

from builder.failures import (
    FailureClass,
    PipelineError,
    with_retry,
)


def test_failure_class_enum():
    assert FailureClass.TRANSIENT.value == "transient"
    assert FailureClass.RECOVERABLE.value == "recoverable"
    assert FailureClass.CRITICAL.value == "critical"
    assert FailureClass.DATA.value == "data"


def test_pipeline_error_carries_classification():
    err = PipelineError("rate limited", FailureClass.TRANSIENT)
    assert str(err) == "rate limited"
    assert err.classification == FailureClass.TRANSIENT


def test_with_retry_succeeds_on_first_try():
    calls: list[int] = []

    @with_retry(max_attempts=3, backoff_base=0.0)
    def f() -> str:
        calls.append(1)
        return "ok"

    assert f() == "ok"
    assert len(calls) == 1


def test_with_retry_retries_transient_failures():
    """A function that raises TRANSIENT should be retried up to max_attempts."""
    calls: list[int] = []

    @with_retry(max_attempts=3, backoff_base=0.0)
    def f() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise PipelineError("network blip", FailureClass.TRANSIENT)
        return "ok"

    assert f() == "ok"
    assert len(calls) == 3


def test_with_retry_gives_up_after_max_attempts():
    calls: list[int] = []

    @with_retry(max_attempts=2, backoff_base=0.0)
    def f() -> str:
        calls.append(1)
        raise PipelineError("permanent network failure", FailureClass.TRANSIENT)

    with pytest.raises(PipelineError) as exc_info:
        f()
    assert exc_info.value.classification == FailureClass.TRANSIENT
    assert len(calls) == 2


def test_with_retry_does_not_retry_recoverable():
    """RECOVERABLE failures bubble up immediately — caller decides."""
    calls: list[int] = []

    @with_retry(max_attempts=3, backoff_base=0.0)
    def f() -> str:
        calls.append(1)
        raise PipelineError("bad input", FailureClass.RECOVERABLE)

    with pytest.raises(PipelineError):
        f()
    assert len(calls) == 1


def test_with_retry_does_not_retry_critical():
    """CRITICAL failures bubble up immediately — pipeline must pause."""
    calls: list[int] = []

    @with_retry(max_attempts=3, backoff_base=0.0)
    def f() -> str:
        calls.append(1)
        raise PipelineError("model unavailable", FailureClass.CRITICAL)

    with pytest.raises(PipelineError):
        f()
    assert len(calls) == 1


def test_with_retry_does_not_retry_non_pipeline_errors():
    """Plain Python exceptions are not retried."""
    calls: list[int] = []

    @with_retry(max_attempts=3, backoff_base=0.0)
    def f() -> str:
        calls.append(1)
        raise ValueError("programmer error")

    with pytest.raises(ValueError):
        f()
    assert len(calls) == 1


def test_with_retry_exponential_backoff_timing(monkeypatch):
    """Backoff is base * 2^attempt — verify by capturing sleep durations."""
    sleep_calls: list[float] = []

    def fake_sleep(d: float) -> None:
        sleep_calls.append(d)

    monkeypatch.setattr("builder.failures.time.sleep", fake_sleep)

    calls: list[int] = []

    @with_retry(max_attempts=4, backoff_base=1.0)
    def f() -> str:
        calls.append(1)
        if len(calls) < 4:
            raise PipelineError("blip", FailureClass.TRANSIENT)
        return "ok"

    assert f() == "ok"
    # Three retries → three sleeps: 1.0, 2.0, 4.0
    assert sleep_calls == [1.0, 2.0, 4.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/test_failures.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/builder/failures.py`**

```python
"""Failure classification and retry behavior for pipeline operations."""
from __future__ import annotations

import functools
import time
from enum import Enum
from typing import Any, Callable, TypeVar


class FailureClass(Enum):
    """How a failure should be handled by the caller / decorator."""
    TRANSIENT = "transient"      # auto-retry with exponential backoff
    RECOVERABLE = "recoverable"  # bubble up; caller decides per-item handling
    CRITICAL = "critical"        # bubble up; pipeline must pause for user input
    DATA = "data"                # bubble up; caller tags item as warning


class PipelineError(Exception):
    """An error with a FailureClass attached so the caller can decide policy."""

    def __init__(self, message: str, classification: FailureClass) -> None:
        super().__init__(message)
        self.classification = classification


F = TypeVar("F", bound=Callable[..., Any])


def with_retry(max_attempts: int = 3, backoff_base: float = 1.0) -> Callable[[F], F]:
    """Decorator: retry on TRANSIENT failures with exponential backoff.

    backoff schedule: base * 2^attempt (where attempt is 0-indexed).
    Only `PipelineError` with `FailureClass.TRANSIENT` triggers retry.
    All other exceptions (including other PipelineError classifications)
    bubble up on first occurrence.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: PipelineError | None = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except PipelineError as e:
                    if e.classification != FailureClass.TRANSIENT:
                        raise
                    last_error = e
                    if attempt + 1 < max_attempts:
                        time.sleep(backoff_base * (2 ** attempt))
            assert last_error is not None  # max_attempts >= 1
            raise last_error
        return wrapper  # type: ignore[return-value]
    return decorator
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/test_failures.py -v`
Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/builder/failures.py tests/builder/test_failures.py
git commit -m "feat(builder): failure classification + retry decorator"
```

---

## Task 5: ItemState + PhaseState Dataclasses

**Files:**
- Create: `src/builder/state.py`
- Create: `tests/builder/test_state.py`

- [ ] **Step 1: Write failing test `tests/builder/test_state.py`**

```python
from builder.state import ItemState, PhaseState


def test_item_state_default_pending():
    item = ItemState()
    assert item.status == "pending"
    assert item.completed_at is None
    assert item.error is None
    assert item.metadata == {}


def test_item_state_to_dict_round_trip():
    item = ItemState(
        status="done",
        completed_at="2026-05-10T10:00:00Z",
        error=None,
        metadata={"method": "text", "extracted_chars": 12000},
    )
    assert ItemState.from_dict(item.to_dict()) == item


def test_phase_state_default_pending():
    phase = PhaseState(name="ingest")
    assert phase.name == "ingest"
    assert phase.status == "pending"
    assert phase.started_at is None
    assert phase.completed_at is None
    assert phase.items == {}


def test_phase_state_to_dict_round_trip():
    phase = PhaseState(
        name="transform",
        status="in_progress",
        started_at="2026-05-10T10:00:00Z",
        completed_at=None,
        items={
            "doc_001.pdf": ItemState(status="done", completed_at="2026-05-10T10:30:00Z"),
            "doc_002.pdf": ItemState(status="in_progress"),
        },
    )
    assert PhaseState.from_dict(phase.to_dict()) == phase


def test_phase_state_from_dict_accepts_missing_optional_fields():
    """Older state files may omit fields; from_dict must tolerate that."""
    minimal = {"name": "qa", "status": "pending"}
    phase = PhaseState.from_dict(minimal)
    assert phase.name == "qa"
    assert phase.status == "pending"
    assert phase.items == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/test_state.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/builder/state.py` (initial: ItemState + PhaseState only)**

```python
"""Pipeline state types and on-disk JSON serialization.

The state lives at ~/.docs-to-skill/<run-id>/pipeline_state.json and is
the single source of truth for which phase/items have completed, what
they cost, and what failed. All serialization uses stdlib json + sort_keys
so commits and diffs are deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ItemState:
    """Status of a single work-item within a phase (e.g., one input PDF).

    status: "pending" | "in_progress" | "done" | "failed"
    metadata: arbitrary phase-specific info (e.g., {"method": "vision_fallback"})
    """
    status: str = "pending"
    completed_at: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemState":
        return cls(
            status=data.get("status", "pending"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


@dataclass
class PhaseState:
    """Status of an entire pipeline phase.

    status: "pending" | "in_progress" | "completed" | "failed"
    items: per-item states keyed by stable item id
    """
    name: str
    status: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    items: dict[str, ItemState] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PhaseState":
        return cls(
            name=data["name"],
            status=data.get("status", "pending"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            items={
                k: ItemState.from_dict(v)
                for k, v in data.get("items", {}).items()
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "items": {k: v.to_dict() for k, v in self.items.items()},
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/test_state.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/builder/state.py tests/builder/test_state.py
git commit -m "feat(builder): ItemState + PhaseState dataclasses"
```

---

## Task 6: PipelineState + JSON Read/Write

**Files:**
- Modify: `src/builder/state.py`
- Modify: `tests/builder/test_state.py`

- [ ] **Step 1: Append tests to `tests/builder/test_state.py`**

```python
import json
from pathlib import Path

from builder.state import PipelineState


def test_pipeline_state_default_initialization():
    state = PipelineState(
        run_id="2026-05-10-test",
        input_dir="/tmp/inputs",
        url_list=[],
        started="2026-05-10T10:00:00Z",
    )
    # All 5 phase states should be pre-populated.
    assert set(state.phases.keys()) == {
        "ingest", "transform", "link", "qa", "emit"
    }
    for phase_state in state.phases.values():
        assert phase_state.status == "pending"
    assert state.cost_tracker == {
        "estimated_total_usd": 0.0,
        "actual_so_far_usd": 0.0,
        "per_phase": {},
    }


def test_pipeline_state_round_trip_through_disk(tmp_path: Path):
    state = PipelineState(
        run_id="2026-05-10-test",
        input_dir="/tmp/inputs",
        url_list=["https://example.com/spec"],
        started="2026-05-10T10:00:00Z",
    )
    state.phases["ingest"].status = "completed"
    state.cost_tracker["actual_so_far_usd"] = 0.42
    state.cost_tracker["per_phase"]["ingest"] = 0.42

    file = tmp_path / "pipeline_state.json"
    state.write(file)

    reloaded = PipelineState.read(file)
    assert reloaded == state


def test_pipeline_state_write_creates_parent_dirs(tmp_path: Path):
    state = PipelineState(
        run_id="x",
        input_dir="/tmp",
        url_list=[],
        started="2026-05-10T10:00:00Z",
    )
    nested = tmp_path / "deep" / "nested" / "pipeline_state.json"
    state.write(nested)
    assert nested.exists()


def test_pipeline_state_disk_is_json_with_sorted_keys(tmp_path: Path):
    state = PipelineState(
        run_id="x",
        input_dir="/tmp",
        url_list=[],
        started="2026-05-10T10:00:00Z",
    )
    file = tmp_path / "ps.json"
    state.write(file)
    raw = json.loads(file.read_text(encoding="utf-8"))
    assert raw["run_id"] == "x"
    assert "phases" in raw
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/builder/test_state.py -v -k pipeline_state`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Append PipelineState to `src/builder/state.py`**

```python
import json
from pathlib import Path


@dataclass
class PipelineState:
    """The complete persistent state of a pipeline run.

    `phases` is initialized with one PhaseState per known pipeline phase
    so callers never need to pre-create them.
    """
    run_id: str
    input_dir: str
    url_list: list[str]
    started: str
    phases: dict[str, PhaseState] = field(default_factory=dict)
    cost_tracker: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Pre-populate phase states for the 5 known phases.
        # Importing Phase at module top would cause a circular dependency
        # with cost_tracker; do the import here (cheap) instead.
        from builder.phases import Phase
        if not self.phases:
            for phase in Phase:
                self.phases[phase.value] = PhaseState(name=phase.value)
        # Pre-populate cost tracker structure.
        if not self.cost_tracker:
            self.cost_tracker = {
                "estimated_total_usd": 0.0,
                "actual_so_far_usd": 0.0,
                "per_phase": {},
            }

    @classmethod
    def read(cls, path: Path) -> "PipelineState":
        raw = json.loads(path.read_text(encoding="utf-8"))
        state = cls(
            run_id=raw["run_id"],
            input_dir=raw["input_dir"],
            url_list=list(raw.get("url_list", [])),
            started=raw["started"],
            phases={
                k: PhaseState.from_dict(v)
                for k, v in raw.get("phases", {}).items()
            },
            cost_tracker=dict(raw.get("cost_tracker", {})),
        )
        return state

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            "run_id": self.run_id,
            "input_dir": self.input_dir,
            "url_list": list(self.url_list),
            "started": self.started,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "cost_tracker": dict(self.cost_tracker),
        }
        path.write_text(
            json.dumps(serializable, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
```

Note: imports `json` and `Path` at the top of the file. Add them to the existing imports if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/test_state.py -v`
Expected: 9 tests pass total (5 from Task 5 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add src/builder/state.py tests/builder/test_state.py
git commit -m "feat(builder): PipelineState with JSON round-trip"
```

---

## Task 7: Pipeline.create() — Fresh Run

**Files:**
- Create: `src/builder/pipeline.py`
- Create: `tests/builder/conftest.py`
- Create: `tests/builder/test_pipeline.py`

- [ ] **Step 1: Create `tests/builder/conftest.py`**

```python
from pathlib import Path

import pytest


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """A fresh per-run state directory under tmp_path/run."""
    d = tmp_path / "run"
    d.mkdir()
    return d
```

- [ ] **Step 2: Write failing test `tests/builder/test_pipeline.py`**

```python
from pathlib import Path

import pytest

from builder.pipeline import Pipeline
from builder.state import PipelineState


def test_create_writes_initial_state_to_disk(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="2026-05-10-test",
        input_dir=Path("/tmp/inputs"),
        url_list=["https://example.com/x"],
        run_dir=run_dir,
    )
    assert (run_dir / "pipeline_state.json").exists()


def test_create_sets_run_id_and_input_dir(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="2026-05-10-test",
        input_dir=Path("/tmp/inputs"),
        url_list=[],
        run_dir=run_dir,
    )
    assert pipeline.state.run_id == "2026-05-10-test"
    assert pipeline.state.input_dir == "/tmp/inputs"


def test_create_records_started_timestamp(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x",
        input_dir=Path("/tmp"),
        url_list=[],
        run_dir=run_dir,
    )
    # ISO 8601 UTC format
    assert pipeline.state.started.endswith("Z")
    assert "T" in pipeline.state.started


def test_create_initializes_all_5_phases_as_pending(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x",
        input_dir=Path("/tmp"),
        url_list=[],
        run_dir=run_dir,
    )
    for phase_name in ["ingest", "transform", "link", "qa", "emit"]:
        assert pipeline.state.phases[phase_name].status == "pending"


def test_create_fails_if_run_dir_already_has_state(run_dir: Path):
    Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    with pytest.raises(FileExistsError):
        Pipeline.create(
            run_id="y", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
        )
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/builder/test_pipeline.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement `src/builder/pipeline.py`**

```python
"""The Pipeline orchestrator class.

Owns the `pipeline_state.json` file under a run directory. Provides
methods to create a fresh run, resume an existing one, replay a phase,
and record progress (phase status, item status, cost).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from builder.phases import Phase
from builder.state import PipelineState


STATE_FILE_NAME = "pipeline_state.json"


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Pipeline:
    """Orchestrates a single pipeline run, persisting state to disk."""

    def __init__(self, run_dir: Path, state: PipelineState) -> None:
        self._run_dir = run_dir
        self._state = state
        self._state_path = run_dir / STATE_FILE_NAME

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    def _save(self) -> None:
        self._state.write(self._state_path)

    @classmethod
    def create(
        cls,
        run_id: str,
        input_dir: Path,
        url_list: list[str],
        run_dir: Path,
    ) -> "Pipeline":
        """Create a fresh pipeline run.

        Raises:
            FileExistsError: if `run_dir` already contains a pipeline_state.json.
        """
        state_path = run_dir / STATE_FILE_NAME
        if state_path.exists():
            raise FileExistsError(
                f"pipeline_state.json already exists at {run_dir} — use resume()"
            )
        state = PipelineState(
            run_id=run_id,
            input_dir=str(input_dir),
            url_list=list(url_list),
            started=_utc_iso_now(),
        )
        pipeline = cls(run_dir=run_dir, state=state)
        pipeline._save()
        return pipeline
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/builder/test_pipeline.py -v`
Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/builder/pipeline.py tests/builder/conftest.py tests/builder/test_pipeline.py
git commit -m "feat(builder): Pipeline.create — fresh run initialization"
```

---

## Task 8: Pipeline.resume()

**Files:**
- Modify: `src/builder/pipeline.py`
- Modify: `tests/builder/test_pipeline.py`

- [ ] **Step 1: Append tests to `tests/builder/test_pipeline.py`**

```python
def test_resume_loads_existing_state(run_dir: Path):
    original = Pipeline.create(
        run_id="2026-05-10-test",
        input_dir=Path("/tmp/inputs"),
        url_list=["https://example.com/x"],
        run_dir=run_dir,
    )

    resumed = Pipeline.resume(run_dir)
    assert resumed.state.run_id == "2026-05-10-test"
    assert resumed.state.input_dir == "/tmp/inputs"
    assert resumed.state.url_list == ["https://example.com/x"]


def test_resume_fails_if_state_missing(run_dir: Path):
    with pytest.raises(FileNotFoundError):
        Pipeline.resume(run_dir)


def test_resume_preserves_phase_progress(run_dir: Path):
    """If the state file shows ingest completed, resume reflects that."""
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.state.phases["ingest"].status = "completed"
    pipeline._save()

    resumed = Pipeline.resume(run_dir)
    assert resumed.state.phases["ingest"].status == "completed"
    assert resumed.state.phases["transform"].status == "pending"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/builder/test_pipeline.py -v -k resume`
Expected: FAIL with `AttributeError: type object 'Pipeline' has no attribute 'resume'`.

- [ ] **Step 3: Add `resume` classmethod to `Pipeline`**

Append to the `Pipeline` class:

```python
    @classmethod
    def resume(cls, run_dir: Path) -> "Pipeline":
        """Load an existing pipeline run from `run_dir/pipeline_state.json`.

        Raises:
            FileNotFoundError: if no state file is found.
        """
        state_path = run_dir / STATE_FILE_NAME
        if not state_path.exists():
            raise FileNotFoundError(
                f"no pipeline_state.json at {run_dir} — use create() instead"
            )
        state = PipelineState.read(state_path)
        return cls(run_dir=run_dir, state=state)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/test_pipeline.py -v`
Expected: 8 tests pass total.

- [ ] **Step 5: Commit**

```bash
git add src/builder/pipeline.py tests/builder/test_pipeline.py
git commit -m "feat(builder): Pipeline.resume — load existing run"
```

---

## Task 9: Phase Status Mutators + Item Recording

**Files:**
- Modify: `src/builder/pipeline.py`
- Modify: `tests/builder/test_pipeline.py`

- [ ] **Step 1: Append tests to `tests/builder/test_pipeline.py`**

```python
from builder.phases import Phase


def test_mark_phase_started_sets_status_and_timestamp(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)

    phase_state = pipeline.state.phases["ingest"]
    assert phase_state.status == "in_progress"
    assert phase_state.started_at is not None


def test_mark_phase_completed_sets_status_and_timestamp(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_completed(Phase.INGEST)

    phase_state = pipeline.state.phases["ingest"]
    assert phase_state.status == "completed"
    assert phase_state.completed_at is not None


def test_mark_phase_failed_records_error(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_failed(Phase.INGEST, error="model unavailable")

    phase_state = pipeline.state.phases["ingest"]
    assert phase_state.status == "failed"


def test_mark_phase_persists_to_disk(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)

    # Reload from disk and verify the change was persisted.
    reloaded = Pipeline.resume(run_dir)
    assert reloaded.state.phases["ingest"].status == "in_progress"


def test_record_item_creates_new_item(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_item(
        Phase.INGEST,
        item_id="doc_001.pdf",
        status="done",
        method="text",
        page_count=42,
    )

    item = pipeline.state.phases["ingest"].items["doc_001.pdf"]
    assert item.status == "done"
    assert item.completed_at is not None
    assert item.metadata["method"] == "text"
    assert item.metadata["page_count"] == 42


def test_record_item_updates_existing_item(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_item(Phase.INGEST, "doc_001.pdf", status="in_progress")
    pipeline.record_item(Phase.INGEST, "doc_001.pdf", status="done")

    item = pipeline.state.phases["ingest"].items["doc_001.pdf"]
    assert item.status == "done"


def test_record_item_failed_captures_error(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_item(
        Phase.INGEST,
        "doc_003.pdf",
        status="failed",
        error="extraction failed: no text recoverable",
    )

    item = pipeline.state.phases["ingest"].items["doc_003.pdf"]
    assert item.status == "failed"
    assert "extraction failed" in (item.error or "")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/builder/test_pipeline.py -v -k "mark_phase or record_item"`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Add the mutator methods to `Pipeline`**

Append to the `Pipeline` class:

```python
    def mark_phase_started(self, phase: Phase) -> None:
        """Set phase status to in_progress and record start timestamp."""
        ps = self._state.phases[phase.value]
        ps.status = "in_progress"
        ps.started_at = _utc_iso_now()
        self._save()

    def mark_phase_completed(self, phase: Phase) -> None:
        """Set phase status to completed and record completion timestamp."""
        ps = self._state.phases[phase.value]
        ps.status = "completed"
        ps.completed_at = _utc_iso_now()
        self._save()

    def mark_phase_failed(self, phase: Phase, error: str) -> None:
        """Set phase status to failed."""
        ps = self._state.phases[phase.value]
        ps.status = "failed"
        ps.completed_at = _utc_iso_now()
        # Phase-level error is conventionally stored as item-id "_phase".
        from builder.state import ItemState
        ps.items["_phase"] = ItemState(
            status="failed",
            completed_at=ps.completed_at,
            error=error,
        )
        self._save()

    def record_item(
        self,
        phase: Phase,
        item_id: str,
        status: str,
        error: str | None = None,
        **metadata: Any,
    ) -> None:
        """Record or update the state of a single item within a phase.

        New items are created on first call; subsequent calls update status,
        completed_at (if status == "done" or "failed"), error, and merge in
        new metadata.
        """
        from builder.state import ItemState
        ps = self._state.phases[phase.value]
        existing = ps.items.get(item_id, ItemState())
        existing.status = status
        if status in ("done", "failed"):
            existing.completed_at = _utc_iso_now()
        if error is not None:
            existing.error = error
        existing.metadata.update(metadata)
        ps.items[item_id] = existing
        self._save()
```

Add `from typing import Any` to the imports at the top of `pipeline.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/test_pipeline.py -v`
Expected: 15 tests pass total.

- [ ] **Step 5: Commit**

```bash
git add src/builder/pipeline.py tests/builder/test_pipeline.py
git commit -m "feat(builder): phase status mutators + item recording"
```

---

## Task 10: Cost Recording + Phase Completion Queries

**Files:**
- Modify: `src/builder/pipeline.py`
- Modify: `tests/builder/test_pipeline.py`

- [ ] **Step 1: Append tests to `tests/builder/test_pipeline.py`**

```python
def test_record_cost_adds_to_phase_total(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_cost(Phase.INGEST, 0.42)
    pipeline.record_cost(Phase.INGEST, 0.18)

    assert pipeline.state.cost_tracker["per_phase"]["ingest"] == 0.60
    assert pipeline.state.cost_tracker["actual_so_far_usd"] == 0.60


def test_record_cost_separate_phases(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_cost(Phase.INGEST, 0.40)
    pipeline.record_cost(Phase.TRANSFORM, 4.20)

    assert pipeline.state.cost_tracker["per_phase"]["ingest"] == 0.40
    assert pipeline.state.cost_tracker["per_phase"]["transform"] == 4.20
    assert pipeline.state.cost_tracker["actual_so_far_usd"] == 4.60


def test_record_cost_persists_to_disk(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_cost(Phase.LINK, 1.80)

    reloaded = Pipeline.resume(run_dir)
    assert reloaded.state.cost_tracker["per_phase"]["link"] == 1.80


def test_set_estimated_total_persists(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.set_estimated_total(11.80)

    reloaded = Pipeline.resume(run_dir)
    assert reloaded.state.cost_tracker["estimated_total_usd"] == 11.80


def test_is_phase_complete_initially_false(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    for phase in Phase:
        assert pipeline.is_phase_complete(phase) is False


def test_is_phase_complete_after_marking(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_completed(Phase.INGEST)
    assert pipeline.is_phase_complete(Phase.INGEST) is True
    assert pipeline.is_phase_complete(Phase.TRANSFORM) is False


def test_next_pending_phase_first_run(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    assert pipeline.next_pending_phase() == Phase.INGEST


def test_next_pending_phase_skips_completed(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_completed(Phase.INGEST)
    pipeline.mark_phase_started(Phase.TRANSFORM)
    pipeline.mark_phase_completed(Phase.TRANSFORM)

    assert pipeline.next_pending_phase() == Phase.LINK


def test_next_pending_phase_returns_none_when_all_done(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    for phase in Phase:
        pipeline.mark_phase_started(phase)
        pipeline.mark_phase_completed(phase)

    assert pipeline.next_pending_phase() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/builder/test_pipeline.py -v -k "cost or pending or is_phase"`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Add cost methods + queries to `Pipeline`**

Append to the `Pipeline` class:

```python
    def record_cost(self, phase: Phase, usd: float) -> None:
        """Add an incremental cost to the phase's total and the global running total."""
        per_phase = self._state.cost_tracker["per_phase"]
        per_phase[phase.value] = per_phase.get(phase.value, 0.0) + usd
        self._state.cost_tracker["actual_so_far_usd"] = (
            self._state.cost_tracker.get("actual_so_far_usd", 0.0) + usd
        )
        self._save()

    def set_estimated_total(self, usd: float) -> None:
        """Set the upfront cost estimate (called once after computing the breakdown)."""
        self._state.cost_tracker["estimated_total_usd"] = usd
        self._save()

    def is_phase_complete(self, phase: Phase) -> bool:
        """Return True iff the phase's status is `completed`."""
        return self._state.phases[phase.value].status == "completed"

    def next_pending_phase(self) -> Phase | None:
        """Return the first phase whose status is not `completed`, or None if all are."""
        for phase in Phase:
            if not self.is_phase_complete(phase):
                return phase
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/test_pipeline.py -v`
Expected: 24 tests pass total.

- [ ] **Step 5: Commit**

```bash
git add src/builder/pipeline.py tests/builder/test_pipeline.py
git commit -m "feat(builder): cost recording + phase completion queries"
```

---

## Task 11: Pipeline.replay_from()

**Files:**
- Modify: `src/builder/pipeline.py`
- Modify: `tests/builder/test_pipeline.py`

- [ ] **Step 1: Append tests to `tests/builder/test_pipeline.py`**

```python
def test_replay_from_resets_target_phase(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_completed(Phase.INGEST)
    pipeline.mark_phase_started(Phase.TRANSFORM)
    pipeline.mark_phase_completed(Phase.TRANSFORM)

    pipeline.replay_from(Phase.TRANSFORM)

    # Transform was reset to pending
    assert pipeline.state.phases["transform"].status == "pending"
    assert pipeline.state.phases["transform"].started_at is None
    assert pipeline.state.phases["transform"].completed_at is None


def test_replay_from_resets_all_later_phases(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    for phase in Phase:
        pipeline.mark_phase_started(phase)
        pipeline.mark_phase_completed(phase)

    pipeline.replay_from(Phase.LINK)

    # Link, qa, emit are all reset
    assert pipeline.state.phases["link"].status == "pending"
    assert pipeline.state.phases["qa"].status == "pending"
    assert pipeline.state.phases["emit"].status == "pending"
    # Earlier phases unchanged
    assert pipeline.state.phases["ingest"].status == "completed"
    assert pipeline.state.phases["transform"].status == "completed"


def test_replay_from_clears_items_in_reset_phases(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_item(Phase.LINK, "concept-a", status="done")
    pipeline.record_item(Phase.LINK, "concept-b", status="done")

    pipeline.replay_from(Phase.LINK)

    assert pipeline.state.phases["link"].items == {}


def test_replay_from_clears_costs_for_reset_phases(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_cost(Phase.INGEST, 0.40)
    pipeline.record_cost(Phase.TRANSFORM, 4.20)
    pipeline.record_cost(Phase.LINK, 1.80)

    pipeline.replay_from(Phase.LINK)

    # Link cost cleared, earlier costs preserved
    assert "link" not in pipeline.state.cost_tracker["per_phase"]
    assert pipeline.state.cost_tracker["per_phase"]["ingest"] == 0.40
    assert pipeline.state.cost_tracker["per_phase"]["transform"] == 4.20
    # actual_so_far_usd is recomputed from per_phase
    assert pipeline.state.cost_tracker["actual_so_far_usd"] == 4.60


def test_replay_from_persists_to_disk(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_completed(Phase.INGEST)

    pipeline.replay_from(Phase.INGEST)

    reloaded = Pipeline.resume(run_dir)
    assert reloaded.state.phases["ingest"].status == "pending"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/builder/test_pipeline.py -v -k replay`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Add `replay_from` method to `Pipeline`**

Append to the `Pipeline` class:

```python
    def replay_from(self, phase: Phase) -> None:
        """Reset the given phase and all later phases to pending.

        Clears their items and per-phase costs. Earlier phases are
        untouched. The aggregate `actual_so_far_usd` is recomputed
        from the surviving per-phase totals.
        """
        from builder.state import PhaseState
        # Identify the index of `phase` in the iteration order.
        phases_in_order = list(Phase)
        target_index = phases_in_order.index(phase)

        # Reset target and all later phases.
        for later in phases_in_order[target_index:]:
            name = later.value
            self._state.phases[name] = PhaseState(name=name)
            self._state.cost_tracker["per_phase"].pop(name, None)

        # Recompute aggregate cost.
        self._state.cost_tracker["actual_so_far_usd"] = sum(
            self._state.cost_tracker["per_phase"].values()
        )
        self._save()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/builder/test_pipeline.py -v`
Expected: 29 tests pass total.

- [ ] **Step 5: Commit**

```bash
git add src/builder/pipeline.py tests/builder/test_pipeline.py
git commit -m "feat(builder): Pipeline.replay_from — reset target + all later phases"
```

---

## Task 12: End-to-End Integration Test

**Files:**
- Create: `tests/builder/test_integration.py`

- [ ] **Step 1: Write the integration test `tests/builder/test_integration.py`**

```python
"""End-to-end integration test simulating a full pipeline run.

No actual phase logic is invoked — just the framework's state transitions.
This test verifies that all the pieces compose correctly into a realistic
lifecycle: create → run phases → record items → record costs → resume → replay.
"""
from pathlib import Path

from builder.cost_tracker import (
    MODEL_PRICES_USD_PER_MILLION,
    TokenUsage,
    estimate_cost,
)
from builder.failures import FailureClass, PipelineError, with_retry
from builder.phases import (
    DEFAULT_CONFIGS,
    Effort,
    Model,
    Phase,
    config_for_phase,
)
from builder.pipeline import Pipeline


def test_full_pipeline_lifecycle(run_dir: Path):
    """Simulate a complete pipeline run with all framework features."""
    # 1. Create a fresh run with an estimated budget.
    pipeline = Pipeline.create(
        run_id="2026-05-10-integration-test",
        input_dir=Path("/tmp/fake_inputs"),
        url_list=["https://example.com/spec"],
        run_dir=run_dir,
    )
    pipeline.set_estimated_total(11.80)
    assert pipeline.state.cost_tracker["estimated_total_usd"] == 11.80

    # 2. Run Ingest: process 3 documents.
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.record_item(Phase.INGEST, "doc_001.pdf", status="done", method="text")
    pipeline.record_item(Phase.INGEST, "doc_002.pdf", status="done", method="vision_fallback")
    pipeline.record_item(Phase.INGEST, "doc_003.pdf", status="failed",
                         error="unreadable")
    pipeline.record_cost(Phase.INGEST, 0.50)
    pipeline.mark_phase_completed(Phase.INGEST)

    assert pipeline.is_phase_complete(Phase.INGEST)
    assert pipeline.next_pending_phase() == Phase.TRANSFORM

    # 3. Run Transform with a configured model + estimated cost.
    config = config_for_phase(Phase.TRANSFORM, DEFAULT_CONFIGS)
    assert config.model == Model.HAIKU
    assert config.effort == Effort.MEDIUM

    pipeline.mark_phase_started(Phase.TRANSFORM)
    # Simulate cost computed from token usage.
    usage = TokenUsage(input_tokens=2_000_000, output_tokens=500_000)
    cost = estimate_cost(config.model, usage)
    pipeline.record_cost(Phase.TRANSFORM, cost)
    pipeline.mark_phase_completed(Phase.TRANSFORM)

    expected_transform_cost = (
        2.0 * MODEL_PRICES_USD_PER_MILLION[Model.HAIKU]["input"]
        + 0.5 * MODEL_PRICES_USD_PER_MILLION[Model.HAIKU]["output"]
    )
    assert (
        pipeline.state.cost_tracker["per_phase"]["transform"]
        == expected_transform_cost
    )

    # 4. Resume from disk in a separate Pipeline instance — state is preserved.
    resumed = Pipeline.resume(run_dir)
    assert resumed.state.phases["ingest"].status == "completed"
    assert resumed.state.phases["transform"].status == "completed"
    assert len(resumed.state.phases["ingest"].items) == 3
    assert resumed.state.phases["ingest"].items["doc_003.pdf"].status == "failed"

    # 5. Replay from Link onwards (the user noticed something off in Link logic).
    resumed.mark_phase_started(Phase.LINK)
    resumed.mark_phase_completed(Phase.LINK)
    resumed.record_cost(Phase.LINK, 1.80)
    cost_before_replay = resumed.state.cost_tracker["actual_so_far_usd"]

    resumed.replay_from(Phase.LINK)

    assert resumed.state.phases["link"].status == "pending"
    assert "link" not in resumed.state.cost_tracker["per_phase"]
    assert resumed.state.cost_tracker["actual_so_far_usd"] < cost_before_replay
    assert resumed.next_pending_phase() == Phase.LINK


def test_retry_decorator_with_real_pipeline_error():
    """A function that raises a TRANSIENT PipelineError gets retried."""
    attempts: list[int] = []

    @with_retry(max_attempts=3, backoff_base=0.0)
    def flaky_agent_call() -> str:
        attempts.append(1)
        if len(attempts) < 2:
            raise PipelineError("rate limit", FailureClass.TRANSIENT)
        return "agent_response"

    assert flaky_agent_call() == "agent_response"
    assert len(attempts) == 2
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/builder/test_integration.py -v`
Expected: 2 tests pass.

- [ ] **Step 3: Run the full builder test suite to ensure nothing regressed**

Run: `pytest tests/builder/ -v`
Expected: all builder tests pass (>=31).

- [ ] **Step 4: Commit**

```bash
git add tests/builder/test_integration.py
git commit -m "test(builder): end-to-end integration test for full pipeline lifecycle"
```

---

## Task 13: Public API Exports + README Section

**Files:**
- Modify: `src/builder/__init__.py`
- Create: `tests/builder/test_public_api.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing test `tests/builder/test_public_api.py`**

```python
def test_builder_public_api_exports():
    from builder import (
        # Phases
        Phase,
        Model,
        Effort,
        PhaseConfig,
        DEFAULT_CONFIGS,
        config_for_phase,
        # Cost tracker
        TokenUsage,
        MODEL_PRICES_USD_PER_MILLION,
        estimate_cost,
        format_cost_breakdown,
        # Failures
        FailureClass,
        PipelineError,
        with_retry,
        # State
        ItemState,
        PhaseState,
        PipelineState,
        # Pipeline
        Pipeline,
    )

    # Smoke check: each is the expected kind of thing
    assert issubclass(Phase, object)
    assert callable(estimate_cost)
    assert callable(with_retry)
    assert hasattr(Pipeline, "create")
    assert hasattr(Pipeline, "resume")
    assert hasattr(Pipeline, "replay_from")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/builder/test_public_api.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Update `src/builder/__init__.py`**

```python
"""Builder pipeline framework and phases.

Subproject 3 (this code) ships the orchestration shell only:
state, cost tracking, failure handling, model routing.
Subprojects 4-8 add the actual phase implementations.

Public API:
- Phases: Phase, Model, Effort, PhaseConfig, DEFAULT_CONFIGS, config_for_phase
- Costs:  TokenUsage, MODEL_PRICES_USD_PER_MILLION, estimate_cost,
          format_cost_breakdown
- Errors: FailureClass, PipelineError, with_retry
- State:  ItemState, PhaseState, PipelineState
- Orchestrator: Pipeline
"""

__version__ = "0.0.1"

from builder.phases import (
    Phase,
    Model,
    Effort,
    PhaseConfig,
    DEFAULT_CONFIGS,
    config_for_phase,
)
from builder.cost_tracker import (
    TokenUsage,
    MODEL_PRICES_USD_PER_MILLION,
    estimate_cost,
    format_cost_breakdown,
)
from builder.failures import FailureClass, PipelineError, with_retry
from builder.state import ItemState, PhaseState, PipelineState
from builder.pipeline import Pipeline

__all__ = [
    "Phase", "Model", "Effort", "PhaseConfig", "DEFAULT_CONFIGS", "config_for_phase",
    "TokenUsage", "MODEL_PRICES_USD_PER_MILLION", "estimate_cost",
    "format_cost_breakdown",
    "FailureClass", "PipelineError", "with_retry",
    "ItemState", "PhaseState", "PipelineState",
    "Pipeline",
]
```

- [ ] **Step 4: Append a "Builder Pipeline Framework" section to `README.md`**

Append at the end of `README.md`:

```markdown

## Builder Pipeline Framework (Subproject 3)

The orchestration shell that subprojects 4–8 plug their phase agents into. Lives
under `src/builder/` and persists run state to `~/.docs-to-skill/<run-id>/pipeline_state.json`.

### Public API

```python
from pathlib import Path
from builder import (
    Pipeline, Phase, Model, Effort,
    DEFAULT_CONFIGS, config_for_phase,
    TokenUsage, estimate_cost, format_cost_breakdown,
    FailureClass, PipelineError, with_retry,
)

# Create a fresh run
pipeline = Pipeline.create(
    run_id="2026-05-10-knowledge-base",
    input_dir=Path("/path/to/inputs"),
    url_list=["https://example.com/spec"],
    run_dir=Path.home() / ".docs-to-skill" / "2026-05-10-knowledge-base",
)
pipeline.set_estimated_total(11.80)

# Phase implementations call:
pipeline.mark_phase_started(Phase.INGEST)
pipeline.record_item(Phase.INGEST, "doc_001.pdf", status="done", method="text")
pipeline.record_cost(Phase.INGEST, 0.42)
pipeline.mark_phase_completed(Phase.INGEST)

# Resume after a crash:
pipeline = Pipeline.resume(Path.home() / ".docs-to-skill" / "2026-05-10-knowledge-base")

# Replay a phase (and discard later phases' work):
pipeline.replay_from(Phase.LINK)
```

### Status

This is Subproject 3 of the matter-expert skill creator.
See `docs/superpowers/plans/2026-05-10-pipeline-framework.md` for this plan.
```

- [ ] **Step 5: Run all tests**

Run: `pytest`
Expected: all tests pass across all modules (matter_expert + runtime + builder).

- [ ] **Step 6: Commit**

```bash
git add src/builder/__init__.py README.md tests/builder/test_public_api.py
git commit -m "feat(builder): public API exports and README section"
```

---

## Done — what you have after this plan

After completing all 13 tasks, the builder framework provides:

1. **Pipeline state schema** — JSON-serializable PipelineState with PhaseState + ItemState, persisted to `pipeline_state.json`
2. **Run lifecycle** — `Pipeline.create()`, `Pipeline.resume()`, `Pipeline.replay_from(phase)`
3. **Progress tracking** — `mark_phase_started/completed/failed`, `record_item`, `record_cost`
4. **Phase queries** — `is_phase_complete`, `next_pending_phase`
5. **Model routing** — `Phase`, `Model`, `Effort`, `PhaseConfig`, `DEFAULT_CONFIGS`, `config_for_phase`
6. **Cost estimation** — `TokenUsage`, `MODEL_PRICES_USD_PER_MILLION`, `estimate_cost`, `format_cost_breakdown`
7. **Failure handling** — `FailureClass`, `PipelineError`, `with_retry` decorator with exponential backoff
8. **Documented public API** — single import surface

This is enough for subprojects 4–8 (the 5 phase implementations) to plug in directly: each phase calls the framework's `mark_*`, `record_*`, and uses `with_retry` around its agent calls.
