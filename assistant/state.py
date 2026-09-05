from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Route(StrEnum):
    FAQ = "faq"
    VECTOR = "vector"
    SQL = "sql"
    BOTH = "both"
    REFUSE = "refuse"


class RouteDecision(BaseModel):
    """What the routing call returns.

    `question` is the rewritten, self-contained form. A follow-up like "and his
    fee?" cannot be routed until the pronoun is resolved, which is why
    rewriting and routing happen in one call rather than in sequence.
    """

    route: Route
    question: str = Field(description="The rewritten, self-contained question.")
    reason: str = Field(default="", description="Why this route, for the trace log.")


class Passage(BaseModel):
    """One piece of evidence, whatever produced it.

    `origin` survives into the answer prompt so a citation can name the page or
    record behind a claim, and so a `both` answer keeps its two sources
    distinguishable after they are merged.
    """

    origin: Literal["vector", "sql"]
    content: str
    citation: str
