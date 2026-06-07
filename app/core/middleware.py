import time
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a unique request_id (UUID hex) to every request.

    Adds 'X-Request-ID' to the response headers.
    """

    async def dispatch(self, request: Request, call_next):
        import uuid

        request_id = uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Log request duration in ms at INFO level, with route path and request_id."""

    async def dispatch(self, request: Request, call_next):
        t0 = time.monotonic()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed = time.monotonic() - t0
            rid = getattr(request.state, "request_id", "-")
            logger.info(
                "request_complete",
                method=request.method,
                path=request.url.path,
                status=getattr(response, "status_code", 0),
                duration_ms=round(elapsed * 1000, 2),
                request_id=rid,
            )