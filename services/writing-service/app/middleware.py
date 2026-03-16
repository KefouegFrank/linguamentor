"""
app/middleware.py

Request middleware for the writing service.

CorrelationIdMiddleware:
  Every request gets a unique ID that flows through all log lines
  for that request. Without this, debugging a production issue means
  searching unrelated log lines with no way to tie them together.

  The ID is read from X-Request-ID if the API Gateway sets it,
  or generated fresh if absent. It's returned in every response
  so clients can include it in support tickets.

  Usage in logs:
    logger.info("Processing essay", extra={"request_id": request.state.request_id})
"""

import logging
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Attaches a unique request ID to every request and response.

    Flow:
    1. Read X-Request-ID from incoming headers (set by API Gateway)
    2. If absent, generate a new UUID4
    3. Attach to request.state.request_id for use in route handlers and logs
    4. Add X-Request-ID to every response header
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Prefer the ID set by the upstream API Gateway — this ensures
        # a single request ID flows across all services in the system
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Make it accessible anywhere that has a Request object
        request.state.request_id = request_id

        # Process the request
        response = await call_next(request)

        # Echo the ID back so clients can log it with support requests
        response.headers["X-Request-ID"] = request_id

        return response
