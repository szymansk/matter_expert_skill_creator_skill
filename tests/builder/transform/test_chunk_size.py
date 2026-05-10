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
