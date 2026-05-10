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
            assert last_error is not None
            raise last_error
        return wrapper  # type: ignore[return-value]
    return decorator
