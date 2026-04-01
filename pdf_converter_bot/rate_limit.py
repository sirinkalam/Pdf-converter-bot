from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Callable


class DailyRateLimiter:
    def __init__(self, limit_per_user: int, today_fn: Callable[[], date] | None = None) -> None:
        self.limit_per_user = max(1, limit_per_user)
        self._today_fn = today_fn or (lambda: datetime.now(timezone.utc).date())
        self._counts: dict[int, tuple[date, int]] = {}
        self._lock = asyncio.Lock()

    async def try_consume(self, user_id: int) -> tuple[bool, int]:
        async with self._lock:
            today = self._today_fn()
            self._discard_stale(today)

            _, current_count = self._counts.get(user_id, (today, 0))
            if current_count >= self.limit_per_user:
                return False, 0

            new_count = current_count + 1
            self._counts[user_id] = (today, new_count)
            return True, self.limit_per_user - new_count

    def _discard_stale(self, today: date) -> None:
        stale_keys = [user_id for user_id, (day, _) in self._counts.items() if day != today]
        for user_id in stale_keys:
            del self._counts[user_id]
