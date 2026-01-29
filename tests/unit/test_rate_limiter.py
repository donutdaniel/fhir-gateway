"""
Tests for the rate limiter module.
"""

import time
from unittest.mock import MagicMock, patch

from app.rate_limiter import (
    RateLimiter,
    get_callback_rate_limiter,
    get_rate_limiter,
    reset_rate_limiter,
)


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_init_defaults(self):
        """Test default initialization."""
        limiter = RateLimiter()
        assert limiter.max_requests == 100
        assert limiter.window_seconds == 60

    def test_init_custom(self):
        """Test custom initialization."""
        limiter = RateLimiter(max_requests=50, window_seconds=30)
        assert limiter.max_requests == 50
        assert limiter.window_seconds == 30

    def test_check_allows_requests_under_limit(self):
        """Should allow requests under the limit."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        for _ in range(5):
            assert limiter.check("session-1") is True

    def test_check_blocks_requests_over_limit(self):
        """Should block requests over the limit."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        # First 3 requests allowed
        for _ in range(3):
            assert limiter.check("session-1") is True

        # 4th request blocked
        assert limiter.check("session-1") is False

    def test_check_per_session_tracking(self):
        """Should track requests per session independently."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Session 1: 2 requests
        assert limiter.check("session-1") is True
        assert limiter.check("session-1") is True
        assert limiter.check("session-1") is False

        # Session 2 should still be allowed
        assert limiter.check("session-2") is True
        assert limiter.check("session-2") is True

    def test_check_expires_old_requests(self):
        """Should expire old requests after window."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)

        # Use up the limit
        assert limiter.check("session-1") is True
        assert limiter.check("session-1") is True
        assert limiter.check("session-1") is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.check("session-1") is True

    def test_cleanup_session(self):
        """Should remove session tracking data."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        limiter.check("session-1")
        assert "session-1" in limiter._requests

        limiter.cleanup_session("session-1")
        assert "session-1" not in limiter._requests

    def test_cleanup_session_nonexistent(self):
        """Should handle cleanup of nonexistent session."""
        limiter = RateLimiter()
        # Should not raise
        limiter.cleanup_session("nonexistent")

    def test_cleanup_stale_removes_empty_sessions(self):
        """Should remove sessions with no recent requests."""
        limiter = RateLimiter(max_requests=5, window_seconds=1)

        limiter.check("session-1")
        limiter.check("session-2")

        # Wait for window to expire
        time.sleep(1.1)

        count = limiter.cleanup_stale()
        assert count == 2
        assert "session-1" not in limiter._requests
        assert "session-2" not in limiter._requests

    def test_cleanup_stale_keeps_active_sessions(self):
        """Should keep sessions with recent requests."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        limiter.check("session-1")
        limiter.check("session-2")

        count = limiter.cleanup_stale()
        assert count == 0
        assert "session-1" in limiter._requests


class TestGetRateLimiter:
    """Tests for get_rate_limiter function."""

    def setup_method(self):
        """Reset the singleton before each test."""
        reset_rate_limiter()

    def teardown_method(self):
        """Reset the singleton after each test."""
        reset_rate_limiter()

    def test_creates_singleton(self):
        """Should create and return singleton instance."""
        with patch("app.rate_limiter.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_max=100,
                rate_limit_window=60,
            )

            limiter1 = get_rate_limiter()
            limiter2 = get_rate_limiter()

            assert limiter1 is limiter2

    def test_uses_settings(self):
        """Should use settings for configuration."""
        with patch("app.rate_limiter.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_max=50,
                rate_limit_window=30,
            )

            limiter = get_rate_limiter()

            assert limiter.max_requests == 50
            assert limiter.window_seconds == 30


class TestGetCallbackRateLimiter:
    """Tests for get_callback_rate_limiter function."""

    def setup_method(self):
        """Reset the singleton before each test."""
        reset_rate_limiter()

    def teardown_method(self):
        """Reset the singleton after each test."""
        reset_rate_limiter()

    def test_creates_singleton(self):
        """Should create and return singleton instance."""
        limiter1 = get_callback_rate_limiter()
        limiter2 = get_callback_rate_limiter()

        assert limiter1 is limiter2

    def test_has_stricter_limits(self):
        """Should have stricter limits than general rate limiter."""
        limiter = get_callback_rate_limiter()

        assert limiter.max_requests == 20
        assert limiter.window_seconds == 60


class TestResetRateLimiter:
    """Tests for reset_rate_limiter function."""

    def setup_method(self):
        """Reset the singleton before each test."""
        reset_rate_limiter()

    def teardown_method(self):
        """Reset the singleton after each test."""
        reset_rate_limiter()

    def test_resets_both_limiters(self):
        """Should reset both rate limiters."""
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_max=100,
                rate_limit_window=60,
            )

            limiter1 = get_rate_limiter()
            callback_limiter1 = get_callback_rate_limiter()

            reset_rate_limiter()

            limiter2 = get_rate_limiter()
            callback_limiter2 = get_callback_rate_limiter()

            assert limiter1 is not limiter2
            assert callback_limiter1 is not callback_limiter2
