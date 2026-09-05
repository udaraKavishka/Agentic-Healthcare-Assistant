import asyncio
import time
from dataclasses import dataclass, field

from assistant.config import settings
from assistant.logging import logger
from assistant.prompts import prompt

WINDOW_SECONDS = 60.0


@dataclass
class Budget:
    """What the free tier allows in a rolling minute, tracked before spending it.

    Requests and tokens are limited separately upstream, so both are counted
    here. Waiting for room is what keeps a burst from becoming a wall of 429s.
    """

    requests_per_minute: int = settings.REQUESTS_PER_MINUTE
    tokens_per_minute: int = settings.TOKENS_PER_MINUTE
    _spent: list[tuple[float, int]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def reserve(self, tokens: int) -> None:
        async with self._lock:
            wait = self._wait_for(tokens)

            if wait > settings.MAX_LIMIT_WAIT_SECONDS:
                logger.info("Shedding a turn: %.0fs of headroom needed", wait)
                raise TimeoutError(prompt("busy", wait=f"Give me {wait:.0f} seconds"))

            if wait > 0:
                logger.info("Rate limit reached, waiting %.1fs", wait)
                await asyncio.sleep(wait)

            self._spent.append((time.monotonic(), tokens))

    def _wait_for(self, tokens: int) -> float:
        self._forget_old()

        requests = len(self._spent)
        spent = sum(count for _, count in self._spent)

        if (
            requests < self.requests_per_minute
            and spent + tokens <= self.tokens_per_minute
        ):
            return 0.0

        if not self._spent:
            logger.warning(
                "A single call asked for %s tokens against a %s limit",
                tokens,
                self.tokens_per_minute,
            )
            raise TimeoutError(prompt("failed"))

        oldest, _ = self._spent[0]
        return max(0.0, WINDOW_SECONDS - (time.monotonic() - oldest))

    def _forget_old(self) -> None:
        cutoff = time.monotonic() - WINDOW_SECONDS
        self._spent = [entry for entry in self._spent if entry[0] > cutoff]


budget = Budget()


def estimate_tokens(messages: list[dict[str, str]], max_output: int) -> int:
    """Roughly four characters per token, which is close enough to reserve on.

    The exact count is only known after the call, and reserving too little is
    what produces the 429 this exists to avoid, so it rounds against us.
    """
    characters = sum(len(message.get("content", "")) for message in messages)
    return characters // 4 + max_output
