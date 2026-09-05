from fastapi.responses import JSONResponse


class APIException(Exception):
    """An error the client is meant to see.

    The body mirrors FastAPI's own validation error shape, so the UI has one
    error contract to read rather than two.
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={"detail": [{"type": self.code, "msg": self.message}]},
        )


class UnsafeQueryError(Exception):
    """A query that will not be sent to the database."""


class UpstreamBusyError(Exception):
    """The model provider is rate limiting and the wait is too long to hold."""
