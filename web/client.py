import json
from collections.abc import Iterator
from dataclasses import dataclass

import httpx

from assistant.api.stream import DONE

TIMEOUT = httpx.Timeout(10.0, read=120.0)


@dataclass
class Event:
    kind: str
    value: str
    detail: str = ""


def ask(api_url: str, conversation_id: str, message: str) -> Iterator[Event]:
    """Read the server-sent events the API emits, one frame at a time.

    Streaming rather than waiting for the whole answer: the routing decision
    and the source being queried arrive before the first token, so the page can
    show what the assistant is doing while it does it.
    """
    body = {"conversation_id": conversation_id, "message": message}

    with (
        httpx.Client(timeout=TIMEOUT) as http,
        http.stream("POST", f"{api_url}/chat", json=body) as response,
    ):
        response.raise_for_status()

        for line in response.iter_lines():
            event = _decode(line)
            if event:
                yield event


def _decode(line: str) -> Event | None:
    if not line.startswith("data: "):
        return None

    payload = line.removeprefix("data: ").strip()
    if not payload or payload == DONE:
        return None

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    return Event(kind=data["type"], value=data["value"], detail=data.get("detail", ""))
