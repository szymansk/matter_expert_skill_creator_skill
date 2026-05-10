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
