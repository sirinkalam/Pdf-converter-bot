from datetime import date

import pytest

from pdf_converter_bot.rate_limit import DailyRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_limit() -> None:
    limiter = DailyRateLimiter(limit_per_user=2, today_fn=lambda: date(2026, 4, 1))

    first_allowed, _ = await limiter.try_consume(123)
    second_allowed, _ = await limiter.try_consume(123)
    third_allowed, _ = await limiter.try_consume(123)

    assert first_allowed
    assert second_allowed
    assert not third_allowed


@pytest.mark.asyncio
async def test_rate_limiter_resets_next_day() -> None:
    current_day = date(2026, 4, 1)

    def today_fn() -> date:
        return current_day

    limiter = DailyRateLimiter(limit_per_user=1, today_fn=today_fn)
    allowed_today, _ = await limiter.try_consume(456)
    blocked_today, _ = await limiter.try_consume(456)

    assert allowed_today
    assert not blocked_today

    current_day = date(2026, 4, 2)
    allowed_next_day, _ = await limiter.try_consume(456)
    assert allowed_next_day
