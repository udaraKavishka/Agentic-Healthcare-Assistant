from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from assistant.tools import sql_templates


@dataclass(frozen=True)
class Tool:
    """A query the model may call, paired with the function that runs it.

    The name comes from the function, so the schema the model is shown and the
    code that answers the call cannot drift apart.
    """

    run: Callable[..., list[dict[str, Any]]]
    description: str
    parameters: dict[str, Any]

    @property
    def name(self) -> str:
        return self.run.__name__

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": self.parameters},
            },
        }


TOOLS = (
    Tool(
        run=sql_templates.find_doctors,
        description=(
            "Doctors, their speciality, qualifications and consultation fee."
            " Use for who practises what, and what a consultation costs."
            " Omit both arguments to list every doctor."
        ),
        parameters={
            "specialty": {
                "type": ["string", "null"],
                "description": "Speciality name or part of one, e.g. Cardio",
            },
            "max_fee": {
                "type": ["number", "null"],
                "description": "Highest consultation fee in rupees",
            },
        },
    ),
    Tool(
        run=sql_templates.get_schedule,
        description=(
            "Channeling sessions for one doctor: day, start and end time, room"
            " and fee. Use for when a named doctor is available."
        ),
        parameters={
            "doctor_name": {
                "type": "string",
                "description": "The doctor's name as the patient gave it",
            },
            "day": {
                "type": ["string", "null"],
                "description": "A weekday name, if the question names one",
            },
        },
    ),
    Tool(
        run=sql_templates.find_lab_tests,
        description=(
            "Lab tests: code, name, category, price, fasting hours, preparation"
            " instructions and report turnaround. Search by the name of the"
            " test, not by a word from the question: for 'do I need to fast"
            " before a lipid profile' pass 'lipid profile'. Omit the query to"
            " list every test."
        ),
        parameters={
            "query": {
                "type": ["string", "null"],
                "description": "Test name, code or category",
            }
        },
    ),
    Tool(
        run=sql_templates.find_health_packages,
        description=(
            "Health packages: name, category, price, who they are for, and the"
            " full list of tests each includes. The contents are stored as"
            " prose, so search by the thing being looked for: for 'which package"
            " includes a Pap smear' pass 'Pap smear'. Omit the query to list"
            " every package."
        ),
        parameters={
            "query": {
                "type": ["string", "null"],
                "description": "A package name, audience, or a test it includes",
            }
        },
    ),
)

SCHEMAS = [tool.schema() for tool in TOOLS]
BY_NAME = {tool.name: tool for tool in TOOLS}
