"""Sampling fractions and helpers (design spec §4.5)."""
from __future__ import annotations

import random
from typing import TypeVar


SAMPLE_FRACTION_TRANSLATION = 0.05
SAMPLE_MIN_TRANSLATION = 10
SAMPLE_FRACTION_CITATION = 0.10
SAMPLE_FRACTION_COHERENCE = 0.15


T = TypeVar("T")


def sample_items(
    items: list[T],
    fraction: float,
    minimum: int = 0,
    maximum: int | None = None,
    seed: int = 0,
) -> list[T]:
    """Return a random sample of `items` sized by fraction, bounded.

    - At least `minimum` items (or all of them if input is smaller).
    - At most `maximum` if given.
    - `seed` makes the sample deterministic.
    """
    target = max(int(len(items) * fraction), minimum)
    target = min(target, len(items))
    if maximum is not None:
        target = min(target, maximum)
    rng = random.Random(seed)
    return rng.sample(items, target)
