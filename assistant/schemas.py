from typing import Literal

from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    status: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    # The client generates `conversation_id` once and sends it every turn, so
    # memory survives a page reload.
    conversation_id: str
    message: str
