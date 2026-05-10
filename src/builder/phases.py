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
