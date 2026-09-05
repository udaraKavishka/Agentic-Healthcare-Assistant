import json
from collections.abc import Callable
from typing import Any

from assistant.config import settings
from assistant.llm import client
from assistant.logging import logger
from assistant.state import Passage
from assistant.tools import sql_templates
from assistant.tools.definitions import TOOLS

CITATION = "Hospital database"
MAX_OUTPUT = 500
INSTRUCTION = (
    "Choose the queries that answer the patient's question about Nawaloka"
    " Hospitals. Call more than one when the question needs it."
)

TEMPLATES = {
    "find_doctors": sql_templates.find_doctors,
    "get_schedule": sql_templates.get_schedule,
    "find_lab_tests": sql_templates.find_lab_tests,
    "find_health_packages": sql_templates.find_health_packages,
}


async def retrieve(question: str) -> list[Passage]:
    """Let the model choose which query to run, and with what arguments.

    The arguments are what matter: "which package includes a Pap smear" has to
    reach the template as "Pap smear", not as a word lifted from the sentence.
    """
    calls = await _chosen(question)
    rows = []

    for name, arguments in calls:
        template = TEMPLATES.get(name)

        if template is None:
            logger.warning("Model asked for an unknown query: %s", name)
            continue

        rows += _run(template, name, arguments)

    if not rows and not calls:
        rows = sql_templates.find_doctors()

    return sql_templates.to_passages(rows, CITATION)


async def _chosen(question: str) -> list[tuple[str, dict]]:
    messages = [
        {"role": "system", "content": INSTRUCTION},
        {"role": "user", "content": question},
    ]
    calls = await client.choose_tools(
        messages, model=settings.ROUTER_MODEL, tools=TOOLS, max_output=MAX_OUTPUT
    )

    return [(call.function.name, _arguments(call.function.arguments)) for call in calls]


def _arguments(raw: str) -> dict:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        logger.warning("Tool arguments were not JSON: %r", raw)
        return {}


def _run(
    template: Callable[..., list[dict[str, Any]]], name: str, arguments: dict
) -> list[dict[str, Any]]:
    try:
        return template(**arguments)
    except TypeError as error:
        logger.warning("%s rejected %s: %s", name, arguments, error)
        return []
