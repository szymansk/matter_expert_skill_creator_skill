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
    calls: list[int] = []

    @with_retry(max_attempts=3, backoff_base=0.0)
    def f() -> str:
        calls.append(1)
        raise PipelineError("bad input", FailureClass.RECOVERABLE)

    with pytest.raises(PipelineError):
        f()
    assert len(calls) == 1


def test_with_retry_does_not_retry_critical():
    calls: list[int] = []

    @with_retry(max_attempts=3, backoff_base=0.0)
    def f() -> str:
        calls.append(1)
        raise PipelineError("model unavailable", FailureClass.CRITICAL)

    with pytest.raises(PipelineError):
        f()
    assert len(calls) == 1


def test_with_retry_does_not_retry_non_pipeline_errors():
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
