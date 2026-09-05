import json
from collections.abc import AsyncIterator

from assistant.pipeline import Event

# Server-sent events, so the browser gets tokens as they are produced. Route and
# tool activity travel as their own events rather than being flattened into the
# answer text, which is what lets the UI show which source was chosen.
HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Without this an nginx-style proxy buffers ~16KB and streaming silently
    # stops looking like streaming.
    "X-Accel-Buffering": "no",
}
DONE = "[DONE]"


async def encode(events: AsyncIterator[Event]) -> AsyncIterator[str]:
    async for event in events:
        payload = {"type": event.kind, "value": event.value}

        if event.detail:
            payload["detail"] = event.detail

        yield f"data: {json.dumps(payload)}\n\n"

    yield f"data: {DONE}\n\n"
