"""
Custom exceptions and FastAPI exception handlers for the writing service.

Centralising this here means every error in the system returns a
consistent JSON shape. Clients should never see raw Python tracebacks
or inconsistent error formats — those are a security leak and a
debugging nightmare.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception classes
# ---------------------------------------------------------------------------

class LinguaMentorException(Exception):
    """
    Base exception for all LinguaMentor service errors.
    Catch this when you want to handle any app-level error generically.
    """
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ServiceUnavailableError(LinguaMentorException):
    """
    Raised when a downstream dependency (DB, Redis, AI provider) is down.
    Maps to HTTP 503 — tells the client to retry later.
    """
    def __init__(self, service: str):
        super().__init__(
            message=f"Downstream service unavailable: {service}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ValidationError(LinguaMentorException):
    """
    Raised when incoming data fails business logic validation —
    distinct from Pydantic's schema validation which FastAPI handles
    automatically. Use this for rules like 'essay must be > 50 words'.
    """
    def __init__(self, message: str):
        super().__init__(message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class NotFoundError(LinguaMentorException):
    """Raised when a requested resource doesn't exist."""
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} not found: {resource_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedError(LinguaMentorException):
    """Raised when a request lacks valid authentication."""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Exception handlers — registered on the FastAPI app in main.py
# ---------------------------------------------------------------------------

def _error_response(status_code: int, message: str, detail: str = None) -> JSONResponse:
    """
    Builds the standard error response shape used across all services.

    Every error in LinguaMentor returns:
    {
        "error": true,
        "message": "human readable description",
        "detail": "optional extra context"
    }

    Clients can always expect this shape — no surprises.
    """
    content = {"error": True, "message": message}
    if detail:
        content["detail"] = detail
    return JSONResponse(status_code=status_code, content=content)


async def linguamentor_exception_handler(
    request: Request,
    exc: LinguaMentorException,
) -> JSONResponse:
    """Handles all custom LinguaMentor exceptions."""
    # Log 5xx errors as errors, 4xx as warnings — keeps alerts meaningful
    if exc.status_code >= 500:
        logger.error(f"{exc.status_code} on {request.url}: {exc.message}")
    else:
        logger.warning(f"{exc.status_code} on {request.url}: {exc.message}")

    return _error_response(exc.status_code, exc.message)


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Catches anything we didn't explicitly handle.
    Logs the full traceback (critical — we need to know about these)
    but never exposes internal details to the client.
    """
    logger.critical(
        f"Unhandled exception on {request.url}: {type(exc).__name__}: {exc}",
        exc_info=True,  # includes full traceback in the log
    )
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "An unexpected error occurred",
        # Don't send exc details to client — that's an info leak
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Registers all exception handlers on the FastAPI app instance.
    Called once during app initialisation in main.py.
    """
    app.add_exception_handler(LinguaMentorException, linguamentor_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
