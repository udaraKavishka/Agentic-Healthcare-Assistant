import httpx
import pytest
from groq import BadRequestError

from assistant.llm import client


async def test_a_rejected_generation_is_read_rather_than_lost(
    monkeypatch: pytest.MonkeyPatch,
):
    """`tool_use_failed` carries the text the provider refused to return.

    Offered no tools, the model sometimes answers by calling one anyway. The
    reply is in the error body, so a turn that would otherwise die can still be
    routed.
    """
    routed = '{"route": "sql", "question": "Who are your cardiologists?"}'
    body = {"error": {"code": "tool_use_failed", "failed_generation": routed}}

    async def reject(**_: object) -> object:
        raise BadRequestError(
            "tool choice is none, but model called a tool",
            response=httpx.Response(400, request=httpx.Request("POST", "http://x")),
            body=body,
        )

    monkeypatch.setattr(client, "_reserve", _nothing)
    monkeypatch.setattr(client, "_client", lambda: _Stub(reject))

    assert await client.complete([], model="m") == routed


async def _nothing(*_: object, **__: object) -> None:
    return None


class _Stub:
    def __init__(self, create):
        self.chat = type(
            "C", (), {"completions": type("D", (), {"create": staticmethod(create)})}
        )
