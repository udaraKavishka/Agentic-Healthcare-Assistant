from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from assistant.api.stream import HEADERS, encode
from assistant.pipeline import run
from assistant.schemas import ChatRequest, HealthCheckResponse

router = APIRouter()


@router.get("/health", tags=["meta"])
async def health() -> HealthCheckResponse:
    return HealthCheckResponse(status="healthy")


@router.post("/chat", tags=["chat"])
async def chat(chat_request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        encode(run(chat_request.conversation_id, chat_request.message)),
        media_type="text/event-stream",
        headers=HEADERS,
    )
