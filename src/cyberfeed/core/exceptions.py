"""Custom exceptions and FastAPI exception handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class CyberFeedError(Exception):
    """Base exception for CyberFeed."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(CyberFeedError):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", status_code=404)


class AuthenticationError(CyberFeedError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationError(CyberFeedError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)


class ValidationError(CyberFeedError):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=422)


class CollectorError(CyberFeedError):
    def __init__(self, message: str = "Collection failed"):
        super().__init__(message, status_code=502)


class SummarizerError(CyberFeedError):
    def __init__(self, message: str = "Summarization failed"):
        super().__init__(message, status_code=502)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CyberFeedError)
    async def cyberfeed_error_handler(_request: Request, exc: CyberFeedError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
