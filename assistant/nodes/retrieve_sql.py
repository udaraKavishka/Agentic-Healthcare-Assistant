import json
from typing import Any

from assistant.config import settings
from assistant.llm import client
from assistant.logging import logger
from assistant.state import Passage
from assistant.tools import sql_templates
from assistant.tools.definitions import BY_NAME, SCHEMAS, Tool

CITATION = "Hospital database"
MAX_OUTPUT = 500
INSTRUCTION = (
    "Choose the queries that answer the patient's question about Nawaloka"
    " Hospitals. Call more than one when the question needs it."
)


async def retrieve(question: str) -> list[Passage]:
    """Let the model choose which query to run, and with what arguments.

    The arguments are what matter: "which package includes a Pap smear" has to
    reach the template as "Pap smear", not as a word lifted from the sentence.
    """
    calls = await _chosen(question)
    rows = []

    for name, arguments in calls:
        tool = BY_NAME.get(name)

        if tool is None:
            logger.warning("Model asked for an unknown query: %s", name)
            continue

        rows += _run(tool, arguments)

    if not rows and not calls:
        rows = sql_templates.find_doctors()

    return sql_templates.to_passages(rows, CITATION)


async def _chosen(question: str) -> list[tuple[str, dict]]:
    messages = [
        {"role": "system", "content": INSTRUCTION},
        {"role": "user", "content": question},
    ]
    calls = await client.choose_tools(
        messages, model=settings.ROUTER_MODEL, tools=SCHEMAS, max_output=MAX_OUTPUT
    )

    return [(call.function.name, _arguments(call.function.arguments)) for call in calls]


def _arguments(raw: str) -> dict:
    """Parse the arguments, dropping the ones the model left empty.

    A template's optional argument means "not filtered by this"; passing an
    explicit null says the same thing less clearly.
    """
    try:
        given = json.loads(raw or "{}")
    except json.JSONDecodeError:
        logger.warning("Tool arguments were not JSON: %r", raw)
        return {}

    return {key: value for key, value in given.items() if value is not None}


def _run(tool: Tool, arguments: dict) -> list[dict[str, Any]]:
    try:
        return tool.run(**arguments)
    except TypeError as error:
        logger.warning("%s rejected %s: %s", tool.name, arguments, error)
        return []
