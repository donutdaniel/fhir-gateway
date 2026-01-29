"""
Tests for session token manager.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.auth import OAuthToken


@pytest.fixture
def sample_oauth_token():
    """Create a sample OAuth token."""
    return OAuthToken(
        access_token="test-access-token",
        token_type="Bearer",
        expires_in=3600,
        refresh_token="test-refresh-token",
        scope="patient/*.read",
    )


@pytest.fixture
def expired_oauth_token():
    """Create an expired OAuth token."""
    # Create token with explicitly expired timestamps
    expired_time = time.time() - 4000
    token = OAuthToken(
        access_token="expired-token",
        token_type="Bearer",
        expires_in=3600,
        refresh_token="refresh-token",
        scope="openid",
        created_at=expired_time,
        expires_at=expired_time + 3600,  # Still in the past
    )
    return token


class TestOAuthToken:
    """Tests for OAuthToken model."""

    def test_creation(self, sample_oauth_token):
        """Should create token with all fields."""
        assert sample_oauth_token.access_token == "test-access-token"
        assert sample_oauth_token.token_type == "Bearer"
        assert sample_oauth_token.expires_in == 3600
        assert sample_oauth_token.refresh_token == "test-refresh-token"

    def test_is_expired_false(self, sample_oauth_token):
        """Should report not expired for fresh token."""
        assert sample_oauth_token.is_expired is False

    def test_is_expired_true(self, expired_oauth_token):
        """Should report expired for old token."""
        assert expired_oauth_token.is_expired is True

    def test_expires_at_calculated(self, sample_oauth_token):
        """Should calculate expiration timestamp."""
        assert sample_oauth_token.expires_at is not None
        assert sample_oauth_token.expires_at > time.time()

    def test_seconds_until_expiry(self, sample_oauth_token):
        """Should calculate seconds until expiry."""
        seconds = sample_oauth_token.seconds_until_expiry()
        assert seconds is not None
        assert 3590 <= seconds <= 3600


class TestSessionTokenManager:
    """Tests for SessionTokenManager class."""

    @pytest.fixture
    def mock_store(self):
        """Create mock secure token store."""
        store = AsyncMock()
        store.get_token = AsyncMock(return_value=None)
        store.store_token = AsyncMock()
        store.delete_token = AsyncMock()
        store.get_session = AsyncMock(return_value=None)
        store.store_pending_auth = AsyncMock()
        store.get_pending_auth = AsyncMock(return_value=None)
        store.clear_pending_auth = AsyncMock()
        store.cleanup_expired_sessions = AsyncMock(return_value=0)
        return store

    @pytest.fixture
    def mock_backend(self):
        """Create mock storage backend."""
        backend = MagicMock()
        return backend

    @pytest.fixture
    def token_manager(self, mock_store, mock_backend):
        """Create token manager with mocks."""
        from app.auth.token_manager import SessionTokenManager

        return SessionTokenManager(store=mock_store, backend=mock_backend)

    @pytest.mark.asyncio
    async def test_get_token_not_found(self, token_manager, mock_store):
        """Should return None if token doesn't exist."""
        token = await token_manager.get_token(
            session_id="session-123",
            platform_id="aetna",
        )
        assert token is None
        mock_store.get_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_token_exists(self, token_manager, mock_store, sample_oauth_token):
        """Should return existing token."""
        mock_store.get_token.return_value = sample_oauth_token

        token = await token_manager.get_token(
            session_id="session-123",
            platform_id="aetna",
            auto_refresh=False,
        )

        assert token == sample_oauth_token

    @pytest.mark.asyncio
    async def test_store_token(self, token_manager, mock_store, sample_oauth_token):
        """Should store token."""
        await token_manager.store_token(
            session_id="session-123",
            platform_id="aetna",
            token=sample_oauth_token,
        )

        mock_store.store_token.assert_called_once_with("session-123", "aetna", sample_oauth_token)

    @pytest.mark.asyncio
    async def test_delete_token(self, token_manager, mock_store):
        """Should delete token."""
        await token_manager.delete_token(
            session_id="session-123",
            platform_id="aetna",
        )

        mock_store.delete_token.assert_called_once_with("session-123", "aetna")

    @pytest.mark.asyncio
    async def test_store_pending_auth(self, token_manager, mock_store):
        """Should store pending auth state."""
        await token_manager.store_pending_auth(
            session_id="session-123",
            platform_id="aetna",
            state="oauth-state",
            pkce_verifier="verifier123",
        )

        mock_store.store_pending_auth.assert_called_once_with(
            "session-123", "aetna", "oauth-state", "verifier123"
        )

    @pytest.mark.asyncio
    async def test_get_pending_auth(self, token_manager, mock_store):
        """Should get pending auth state."""
        mock_store.get_pending_auth.return_value = {
            "state": "oauth-state",
            "pkce_verifier": "verifier123",
        }

        result = await token_manager.get_pending_auth(
            session_id="session-123",
            platform_id="aetna",
        )

        assert result["state"] == "oauth-state"
        mock_store.get_pending_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_pending_auth(self, token_manager, mock_store):
        """Should clear pending auth state."""
        await token_manager.clear_pending_auth(
            session_id="session-123",
            platform_id="aetna",
        )

        mock_store.clear_pending_auth.assert_called_once()


class TestWaitForAuthComplete:
    """Tests for wait_for_auth_complete functionality."""

    @pytest.fixture
    def mock_store(self):
        """Create mock secure token store."""
        store = AsyncMock()
        store.get_token = AsyncMock(return_value=None)
        return store

    @pytest.fixture
    def mock_backend(self):
        """Create mock storage backend."""
        return MagicMock()

    @pytest.fixture
    def token_manager(self, mock_store, mock_backend):
        """Create token manager with mocks."""
        from app.auth.token_manager import SessionTokenManager

        return SessionTokenManager(store=mock_store, backend=mock_backend)

    @pytest.mark.asyncio
    async def test_wait_timeout(self, token_manager):
        """Should return None on timeout."""
        result = await token_manager.wait_for_auth_complete("session-1", "aetna", timeout=0.1)
        assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_wait_blocked(self, token_manager):
        """Second concurrent wait should return None immediately."""

        async def first_wait():
            return await token_manager.wait_for_auth_complete("session-1", "aetna", timeout=2)

        # Start first wait
        task = asyncio.create_task(first_wait())
        await asyncio.sleep(0.05)

        # Second wait should return None
        result = await token_manager.wait_for_auth_complete("session-1", "aetna", timeout=1)
        assert result is None

        # Cancel the first task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestTokenManagerFactory:
    """Tests for get_token_manager factory function."""

    def test_get_token_manager_singleton(self):
        """Should return singleton instance."""
        from app.auth import token_manager as tm_module

        # Reset singleton
        tm_module._token_manager = None

        with patch("app.auth.token_manager.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url=None,
                require_redis_tls=False,
                master_key=None,
                session_max_age=3600,
            )

            manager1 = tm_module.get_token_manager()
            manager2 = tm_module.get_token_manager()

            assert manager1 is manager2

        # Cleanup
        tm_module._token_manager = None
