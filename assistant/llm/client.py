from collections.abc import AsyncIterator
from functools import lru_cache

from groq import APIStatusError, AsyncGroq, BadRequestError, RateLimitError
from groq.types.chat import ChatCompletionMessageToolCall

from assistant.config import settings
from assistant.exceptions import UpstreamBusyError
from assistant.llm.budget import budget, estimate_tokens
from assistant.logging import logger

# gpt-oss models spend completion tokens on reasoning before answering, so a
# cap that only covers the answer leaves nothing to say it with.
REASONING_EFFORT = "low"


@lru_cache(maxsize=1)
def _client() -> AsyncGroq:
    return AsyncGroq(api_key=settings.GROQ_API_KEY)


async def complete(
    messages: list[dict[str, str]], model: str, max_output: int = 1024
) -> str:
    await _reserve(messages, max_output)

    try:
        response = await _client().chat.completions.create(
            model=model,
            messages=messages,  # pyright: ignore[reportArgumentType]
            max_completion_tokens=max_output,
            reasoning_effort=REASONING_EFFORT,
        )
    except RateLimitError as error:
        raise UpstreamBusyError(_busy_message(error)) from error

    return response.choices[0].message.content or ""


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
    retry_after = error.response.headers.get("retry-after", "")
    logger.warning("Upstream rate limited, retry-after %ss", retry_after or "unknown")

    if retry_after:
        return f"The assistant is busy. Try again in {retry_after} seconds."

    return "The assistant is busy. Try again shortly."
