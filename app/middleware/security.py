"""
Security middleware for FHIR Gateway.

Adds security headers to all responses, enforces request size limits,
and provides rate limiting.
"""

from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.audit import AuditEvent, audit_log
from app.rate_limiter import get_callback_rate_limiter, get_rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces per-session rate limits.

    Uses a sliding window algorithm to limit requests per session.
    OAuth callback endpoints have stricter limits.
    """

    def __init__(self, app, session_cookie_name: str = "app_session") -> None:
        """
        Initialize the middleware.

        Args:
            app: The ASGI application
            session_cookie_name: Name of the session cookie
        """
        super().__init__(app)
        self.session_cookie_name = session_cookie_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get session ID from cookie, or use client IP as fallback
        session_id = request.cookies.get(self.session_cookie_name)
        if not session_id:
            # Use IP + User-Agent as a fallback identifier
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "")[:50]
            session_id = f"anon:{client_ip}:{hash(user_agent)}"

        # Use stricter rate limiter for OAuth callback
        path = request.url.path
        if "/auth/callback" in path:
            limiter = get_callback_rate_limiter()
        else:
            limiter = get_rate_limiter()

        if not limiter.check(session_id):
            audit_log(
                AuditEvent.SECURITY_RATE_LIMIT,
                session_id=session_id,
                details={"path": path, "method": request.method},
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(limiter.window_seconds)},
            )

        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces request body size limits.

    Prevents DoS attacks by rejecting requests that exceed the configured size.
    """

    def __init__(self, app, max_body_size: int = 10 * 1024 * 1024) -> None:
        """
        Initialize the middleware.

        Args:
            app: The ASGI application
            max_body_size: Maximum allowed request body size in bytes (default 10MB)
        """
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_body_size:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large. Maximum size is {self.max_body_size} bytes."
                        },
                    )
            except ValueError:
                pass  # Invalid content-length, let the request proceed

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy for API responses
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; style-src 'unsafe-inline'"
            )

        return response
