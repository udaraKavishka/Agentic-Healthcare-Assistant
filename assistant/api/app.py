from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from assistant.api.routes import router
from assistant.config import settings
from assistant.exceptions import APIException


def route_operation_id(route: APIRoute) -> str:
    return route.name


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Hybrid agentic healthcare assistant.",
    generate_unique_id_function=route_operation_id,
    openapi_url=None if settings.is_production else "/openapi.json",
    redoc_url=None if settings.is_production else "/redoc",
)


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException) -> object:
    return exc.to_response()


app.include_router(router)
# Nothing sends cookies or an Authorization header, so credentials stay off and
# the method list is only what the UI actually uses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
