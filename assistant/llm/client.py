from collections.abc import AsyncIterator
from functools import lru_cache

from groq import APIStatusError, AsyncGroq, BadRequestError, RateLimitError
from groq.types.chat import ChatCompletionMessageToolCall

from assistant.config import settings
from assistant.exceptions import UpstreamBusyError
from assistant.llm.budget import budget, estimate_tokens
from assistant.logging import logger
from assistant.prompts import prompt

# gpt-oss models spend completion tokens on reasoning before answering, so a
# cap that only covers the answer leaves nothing to say it with.
REASONING_EFFORT = "low"


@lru_cache(maxsize=1)
def _client() -> AsyncGroq:
    return AsyncGroq(api_key=settings.GROQ_API_KEY)


async def complete(
    messages: list[dict[str, str]], model: str, max_output: int = 1024
) -> str:
    """Ask for one JSON object back.

    JSON mode is not only about parsing. Offered no tools, `gpt-oss` sometimes
    answers by calling one anyway, and the provider rejects the whole request
    with `tool_use_failed` rather than returning the text. Constraining the
    reply to an object stops it reaching for a tool that was never there.
    """
    await _reserve(messages, max_output)

    try:
        response = await _client().chat.completions.create(
            model=model,
            messages=messages,  # pyright: ignore[reportArgumentType]
            max_completion_tokens=max_output,
            reasoning_effort=REASONING_EFFORT,
            response_format={"type": "json_object"},
        )
    except RateLimitError as error:
        raise UpstreamBusyError(_busy_message(error)) from error
    except BadRequestError as error:
        return _rejected_content(error)

    return response.choices[0].message.content or ""


def _rejected_content(error: BadRequestError) -> str:
    """Recover the reply the provider refused to return.

    A `tool_use_failed` body carries the text it rejected under
    `failed_generation`. Salvaging it turns a dead turn into a routed one.
    """
    logger.warning("The model produced an unusable reply: %s", error)
    body = error.body if isinstance(error.body, dict) else {}
    failed = body.get("error", {})

    return failed.get("failed_generation", "") if isinstance(failed, dict) else ""


async def choose_tools(
    messages: list[dict[str, str]],
    model: str,
    tools: list[dict],
    max_output: int = 512,
) -> list[ChatCompletionMessageToolCall]:
    """Ask the model which queries to run, and with what arguments."""
    await _reserve(messages, max_output)

    try:
        response = await _client().chat.completions.create(
            model=model,
            messages=messages,  # pyright: ignore[reportArgumentType]
            tools=tools,  # pyright: ignore[reportArgumentType]
            max_completion_tokens=max_output,
            reasoning_effort=REASONING_EFFORT,
        )
    except RateLimitError as error:
        raise UpstreamBusyError(_busy_message(error)) from error
    except BadRequestError as error:
        logger.warning("The model proposed an unusable tool call: %s", error)
        return []

    return response.choices[0].message.tool_calls or []


async def stream(
    messages: list[dict[str, str]], model: str, max_output: int = 1024
) -> AsyncIterator[str]:
    await _reserve(messages, max_output)

    try:
        # The streaming overload is selected by `stream=True`, which the checker
        # cannot connect to loosely typed message dicts.
        completion = await _client().chat.completions.create(  # pyright: ignore[reportCallIssue]
            model=model,
            messages=messages,  # pyright: ignore[reportArgumentType]
            max_completion_tokens=max_output,
            reasoning_effort=REASONING_EFFORT,
            stream=True,
        )
    except RateLimitError as error:
        raise UpstreamBusyError(_busy_message(error)) from error

    # `async with` closes the response when a caller stops reading early, which
    # is the normal case here: a browser that navigates away mid-answer.
    async with completion:
        async for chunk in completion:
            content = chunk.choices[0].delta.content
            if content:
                yield content


async def _reserve(messages: list[dict[str, str]], max_output: int) -> None:
    try:
        await budget.reserve(estimate_tokens(messages, max_output))
    except TimeoutError as error:
        raise UpstreamBusyError(str(error)) from error


def _busy_message(error: APIStatusError) -> str:
    """A wait, described as load rather than as a rate limit.

    "Rate limit" is a fact about our billing tier, not about the patient's
    question, and the number of seconds is the only part they can act on.
    """
    retry_after = error.response.headers.get("retry-after", "")
    logger.warning("Upstream rate limited, retry-after %ss", retry_after or "unknown")
    wait = f"Give me {retry_after} seconds" if retry_after else "Give me a few seconds"

    return prompt("busy", wait=wait)
