import pytest

from builder.qa.thresholds import (
    SAMPLE_FRACTION_CITATION,
    SAMPLE_FRACTION_COHERENCE,
    SAMPLE_FRACTION_TRANSLATION,
    SAMPLE_MIN_TRANSLATION,
    sample_items,
)


def test_translation_fraction():
    assert SAMPLE_FRACTION_TRANSLATION == 0.05
    assert SAMPLE_MIN_TRANSLATION == 10


def test_citation_fraction():
    assert SAMPLE_FRACTION_CITATION == 0.10


def test_coherence_fraction():
    assert SAMPLE_FRACTION_COHERENCE == 0.15


def test_sample_items_returns_fraction():
    items = list(range(200))
    sampled = sample_items(items, fraction=0.10)
    assert len(sampled) == 20


def test_sample_items_respects_minimum():
    items = list(range(20))
    sampled = sample_items(items, fraction=0.05, minimum=10)
    # 5% of 20 = 1 → bumped to minimum 10
    assert len(sampled) == 10


def test_sample_items_respects_maximum_size_of_input():
    items = list(range(5))
    sampled = sample_items(items, fraction=0.05, minimum=10)
    # min 10 but only 5 items exist → returns all 5
    assert len(sampled) == 5


def test_sample_items_deterministic_with_seed():
    items = list(range(100))
    a = sample_items(items, fraction=0.20, seed=42)
    b = sample_items(items, fraction=0.20, seed=42)
    assert a == b


def test_sample_items_different_seeds_yield_different_samples():
    items = list(range(100))
    a = sample_items(items, fraction=0.20, seed=42)
    b = sample_items(items, fraction=0.20, seed=99)
    assert a != b
