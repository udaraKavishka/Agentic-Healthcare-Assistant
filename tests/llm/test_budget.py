import time

import pytest

from assistant.config import settings
from assistant.llm.budget import WINDOW_SECONDS, Budget, estimate_tokens


async def test_calls_within_the_budget_do_not_wait():
    budget = Budget(requests_per_minute=5, tokens_per_minute=1000)

    for _ in range(5):
        await budget.reserve(100)


async def test_exhausting_the_request_count_forces_a_wait():
    budget = Budget(requests_per_minute=1, tokens_per_minute=10_000)
    await budget.reserve(10)

    with pytest.raises(TimeoutError):
        await budget.reserve(10)


async def test_exhausting_the_token_count_forces_a_wait():
    budget = Budget(requests_per_minute=100, tokens_per_minute=500)
    await budget.reserve(400)

    with pytest.raises(TimeoutError):
        await budget.reserve(200)


async def test_a_caller_willing_to_wait_is_allowed_to(monkeypatch: pytest.MonkeyPatch):
    """The spend is aged relative to now, not pinned to an absolute timestamp.

    `time.monotonic()` counts from an arbitrary origin, so a fixed 0.0 is
    minutes old on a long-running machine and seconds old on a fresh CI runner.
    """
    monkeypatch.setattr(settings, "MAX_LIMIT_WAIT_SECONDS", 1.0)
    budget = Budget(requests_per_minute=1, tokens_per_minute=10_000)
    budget._spent = [(time.monotonic() - WINDOW_SECONDS + 0.05, 10)]

    await budget.reserve(10)


def test_the_estimate_covers_the_prompt_and_the_reply():
    messages = [{"role": "user", "content": "a" * 400}]

    assert estimate_tokens(messages, max_output=50) == 150


async def test_a_request_larger_than_the_minute_is_refused_not_crashed():
    """Waiting cannot free room that the limit never had.

    With nothing queued there is no entry to expire, so the wait calculation has
    no oldest spend to work from and has to say so rather than index an empty
    window.
    """
    budget = Budget(requests_per_minute=30, tokens_per_minute=100)

    with pytest.raises(TimeoutError, match="more than the 100"):
        await budget.reserve(500)
