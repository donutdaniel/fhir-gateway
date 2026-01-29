"""
In-memory sliding window rate limiter for FHIR Gateway.

Provides per-session rate limiting to protect against abuse.
Uses a sliding window algorithm for accurate request counting.
"""

import time
from collections import deque

from app.config.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter with per-session tracking.

    Each session gets its own deque of request timestamps.
    Old entries are cleaned up on each check.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum requests allowed per window per session
            window_seconds: Sliding window duration in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}

    def check(self, session_id: str) -> bool:
        """
        Check if a request is allowed for the given session.

        Args:
            session_id: Session identifier

        Returns:
            True if the request is allowed, False if rate-limited
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        if session_id not in self._requests:
            self._requests[session_id] = deque()

        window = self._requests[session_id]

        # Remove expired entries
        while window and window[0] <= cutoff:
            window.popleft()

        if len(window) >= self.max_requests:
            return False

        window.append(now)
        return True

    def cleanup_session(self, session_id: str) -> None:
        """Remove tracking data for a session."""
        self._requests.pop(session_id, None)

    def cleanup_stale(self) -> int:
        """
        Remove sessions with no recent requests.

        Returns:
            Number of sessions cleaned up
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        stale = []

        for session_id, window in self._requests.items():
            # Remove expired entries
            while window and window[0] <= cutoff:
                window.popleft()
            if not window:
                stale.append(session_id)

        for session_id in stale:
            del self._requests[session_id]

        return len(stale)


# Module-level singleton
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance, creating it if needed."""
    global _rate_limiter
    if _rate_limiter is None:
        from app.config.settings import get_settings

        settings = get_settings()
        _rate_limiter = RateLimiter(
            max_requests=settings.rate_limit_max,
            window_seconds=settings.rate_limit_window,
        )
    return _rate_limiter


# Callback rate limiter - stricter limits for OAuth callback endpoint
_callback_rate_limiter: RateLimiter | None = None


def get_callback_rate_limiter() -> RateLimiter:
    """
    Get the callback rate limiter instance.

    Stricter than the general rate limiter. Used to protect the OAuth
    callback endpoint from abuse.
    """
    global _callback_rate_limiter
    if _callback_rate_limiter is None:
        from app.config.settings import get_settings

        settings = get_settings()
        _callback_rate_limiter = RateLimiter(
            max_requests=settings.callback_rate_limit_max,
            window_seconds=settings.callback_rate_limit_window,
        )
    return _callback_rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiters (for testing)."""
    global _rate_limiter, _callback_rate_limiter
    _rate_limiter = None
    _callback_rate_limiter = None
