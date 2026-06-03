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
