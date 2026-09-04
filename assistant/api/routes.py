from fastapi import APIRouter

from assistant.schemas import HealthCheckResponse

router = APIRouter()


@router.get("/health", tags=["meta"])
async def health() -> HealthCheckResponse:
    return HealthCheckResponse(status="healthy")
