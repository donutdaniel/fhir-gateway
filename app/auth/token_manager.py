"""
Session token manager for FHIR Gateway.

Provides high-level session token management with:
- Automatic token refresh
- Distributed locking for refresh operations
- Session lifecycle management
- Auth completion signaling
"""

import asyncio
from typing import Any

from app.audit import AuditEvent, audit_log, truncate_session_id
from app.auth.identity import UserIdentity
from app.auth.secure_token_store import (
    InMemoryTokenStorage,
    RedisTokenStorage,
    SecureTokenStore,
    TokenStorageBackend,
)
from app.config.logging import get_logger
from app.config.settings import get_settings
from app.constants import (
    AUTH_WAIT_TIMEOUT_SECONDS,
    REFRESH_LOCK_TTL_SECONDS,
    TOKEN_REFRESH_BUFFER_SECONDS,
)
from app.models.auth import OAuthToken
from app.services.oauth import OAuthService

logger = get_logger(__name__)

# Singleton instance
_token_manager: "SessionTokenManager | None" = None


class SessionTokenManager:
    """
    High-level session token manager.

    Provides session-scoped token management with automatic refresh,
    distributed locking, and auth completion signaling.
    """

    def __init__(
        self,
        store: SecureTokenStore,
        backend: TokenStorageBackend,
    ):
        """
        Initialize token manager.

        Args:
            store: Secure token store for session data
            backend: Storage backend (for distributed locks and pub/sub signals)
        """
        self._store = store
        self._backend = backend
        self._auth_waiters: dict[str, asyncio.Event] = {}
        self._waiter_counts: dict[str, int] = {}

    async def get_token(
        self,
        session_id: str,
        platform_id: str,
        auto_refresh: bool = True,
    ) -> OAuthToken | None:
        """
        Get OAuth token for a platform, optionally auto-refreshing if expired.

        Args:
            session_id: Session ID
            platform_id: Platform ID
            auto_refresh: If True, automatically refresh expired tokens

        Returns:
            OAuth token or None if not found
        """
        token = await self._store.get_token(session_id, platform_id)

        if token is None:
            return None

        # Check if token needs refresh
        if auto_refresh and token.refresh_token and self._should_refresh(token):
            token = await self._refresh_token_with_lock(session_id, platform_id, token)

        return token

    def _should_refresh(self, token: OAuthToken) -> bool:
        """Check if token should be refreshed."""
        seconds_remaining = token.seconds_until_expiry()
        if seconds_remaining is None:
            return False
        return seconds_remaining < TOKEN_REFRESH_BUFFER_SECONDS

    async def _refresh_token_with_lock(
        self,
        session_id: str,
        platform_id: str,
        token: OAuthToken,
    ) -> OAuthToken:
        """
        Refresh token with distributed locking.

        Ensures only one refresh operation happens at a time per session/platform.
        Uses backend distributed lock for multi-instance coordination.
        """
        ttl = REFRESH_LOCK_TTL_SECONDS

        # Try to acquire distributed lock
        acquired = await self._backend.acquire_refresh_lock(session_id, platform_id, ttl)
        if not acquired:
            # Another refresh in progress (possibly on another instance)
            logger.debug(
                "Token refresh already in progress",
                session_id=truncate_session_id(session_id),
                platform_id=platform_id,
            )
            return token

        try:
            # Re-check token after acquiring lock (another call may have refreshed)
            current_token = await self._store.get_token(session_id, platform_id)
            if current_token and not self._should_refresh(current_token):
                return current_token

            # Perform refresh
            settings = get_settings()

            oauth_service = OAuthService(
                platform_id=platform_id,
                redirect_uri=settings.oauth_redirect_uri,
            )

            new_token = await oauth_service.refresh_token(token.refresh_token)

            # Store new token
            await self._store.store_token(session_id, platform_id, new_token)

            audit_log(
                AuditEvent.TOKEN_REFRESH,
                session_id=session_id,
                platform_id=platform_id,
                success=True,
            )

            logger.info(
                "Token refreshed successfully",
                session_id=truncate_session_id(session_id),
                platform_id=platform_id,
            )

            return new_token

        except Exception as e:
            audit_log(
                AuditEvent.TOKEN_REFRESH_FAILURE,
                session_id=session_id,
                platform_id=platform_id,
                success=False,
                error=str(e),
            )

            logger.error(
                "Token refresh failed",
                session_id=truncate_session_id(session_id),
                platform_id=platform_id,
                error=str(e),
            )

            # Return original token, let caller handle expiry
            return token

        finally:
            await self._backend.release_refresh_lock(session_id, platform_id)

    async def store_token(
        self,
        session_id: str,
        platform_id: str,
        token: OAuthToken,
    ) -> None:
        """
        Store OAuth token for a platform.

        Args:
            session_id: Session ID
            platform_id: Platform ID
            token: OAuth token to store
        """
        await self._store.store_token(session_id, platform_id, token)

        # Signal any waiters
        await self._signal_auth_complete(session_id, platform_id)

    async def delete_token(
        self,
        session_id: str,
        platform_id: str,
    ) -> None:
        """
        Delete OAuth token for a platform.

        Args:
            session_id: Session ID
            platform_id: Platform ID
        """
        await self._store.delete_token(session_id, platform_id)

        audit_log(
            AuditEvent.AUTH_REVOKE,
            session_id=session_id,
            platform_id=platform_id,
        )

    async def store_user_identity(
        self,
        session_id: str,
        platform_id: str,
        identity: UserIdentity,
    ) -> None:
        """
        Store user identity for a platform.

        Args:
            session_id: Session ID
            platform_id: Platform ID
            identity: User identity to store
        """
        await self._store.store_user_identity(session_id, platform_id, identity)

    async def get_user_identity(
        self,
        session_id: str,
        platform_id: str,
    ) -> UserIdentity | None:
        """
        Get user identity for a platform.

        Args:
            session_id: Session ID
            platform_id: Platform ID

        Returns:
            User identity or None if not found
        """
        return await self._store.get_user_identity(session_id, platform_id)

    async def get_auth_status(
        self,
        session_id: str,
    ) -> dict[str, dict[str, Any]]:
        """
        Get authentication status for all platforms in session.

        Args:
            session_id: Session ID

        Returns:
            Dictionary mapping platform_id to auth status
        """
        session = await self._store.get_session(session_id)
        if session is None:
            return {}

        status = {}
        for platform_id, token in session.platform_tokens.items():
            status[platform_id] = {
                "authenticated": not token.is_expired,
                "has_token": True,
                "expires_at": token.expires_at,
                "can_refresh": token.refresh_token is not None,
                "scopes": token.scope.split() if token.scope else None,
            }

        return status

    async def store_pending_auth(
        self,
        session_id: str,
        platform_id: str,
        state: str,
        pkce_verifier: str,
        mcp_initiated: bool = False,
    ) -> None:
        """Store pending OAuth authorization data."""
        await self._store.store_pending_auth(
            session_id, platform_id, state, pkce_verifier, mcp_initiated
        )

    async def get_pending_auth(
        self,
        session_id: str,
        platform_id: str,
    ) -> dict[str, Any] | None:
        """Get pending OAuth authorization data."""
        return await self._store.get_pending_auth(session_id, platform_id)

    async def clear_pending_auth(
        self,
        session_id: str,
        platform_id: str,
    ) -> None:
        """Clear pending OAuth authorization data."""
        await self._store.clear_pending_auth(session_id, platform_id)

    async def get_pending_auth_by_state(self, state: str) -> dict[str, Any] | None:
        """Find pending OAuth authorization by state parameter."""
        return await self._store.get_pending_auth_by_state(state)

    async def wait_for_auth_complete(
        self,
        session_id: str,
        platform_id: str,
        timeout: float | None = None,
    ) -> OAuthToken | None:
        """
        Wait for OAuth callback to complete.

        Uses per-session:platform semaphore to allow only one concurrent waiter.
        Subscribes to backend pub/sub for distributed signaling (multi-instance).

        Args:
            session_id: Session ID
            platform_id: Platform ID
            timeout: Maximum wait time in seconds (uses settings default if not provided)

        Returns:
            OAuth token if auth completed, None if timeout or already waiting
        """
        if timeout is None:
            timeout = AUTH_WAIT_TIMEOUT_SECONDS

        wait_key = f"{session_id}:{platform_id}"

        # Check if already waiting
        if self._waiter_counts.get(wait_key, 0) > 0:
            logger.warning(
                "Already waiting for auth completion",
                session_id=truncate_session_id(session_id),
                platform_id=platform_id,
            )
            return None

        # Create local event for this wait
        if wait_key not in self._auth_waiters:
            self._auth_waiters[wait_key] = asyncio.Event()
        else:
            self._auth_waiters[wait_key].clear()

        self._waiter_counts[wait_key] = self._waiter_counts.get(wait_key, 0) + 1

        try:
            # Check if token already exists
            token = await self._store.get_token(session_id, platform_id)
            if token and not token.is_expired:
                return token

            # Subscribe to backend pub/sub for distributed signaling
            async with self._backend.subscribe_auth_complete(
                session_id, platform_id
            ) as backend_event:
                local_event = self._auth_waiters[wait_key]

                async def wait_for_either():
                    """Wait for either local or backend event."""
                    while True:
                        # Check both events
                        if local_event.is_set() or backend_event.is_set():
                            return
                        # Wait a short time then check again
                        await asyncio.sleep(0.1)

                try:
                    await asyncio.wait_for(wait_for_either(), timeout=timeout)

                    # Get token after signal
                    return await self._store.get_token(session_id, platform_id)

                except asyncio.TimeoutError:
                    logger.debug(
                        "Auth wait timed out",
                        session_id=truncate_session_id(session_id),
                        platform_id=platform_id,
                    )
                    return None

        finally:
            self._waiter_counts[wait_key] = self._waiter_counts.get(wait_key, 1) - 1

    async def _signal_auth_complete(
        self,
        session_id: str,
        platform_id: str,
    ) -> None:
        """Signal that authentication completed for a session/platform."""
        wait_key = f"{session_id}:{platform_id}"

        # Signal local waiters
        if wait_key in self._auth_waiters:
            self._auth_waiters[wait_key].set()

        # Publish to backend for distributed signaling (multi-instance)
        await self._backend.publish_auth_complete(session_id, platform_id)

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        count = await self._store.cleanup_expired_sessions()

        if count > 0:
            audit_log(
                AuditEvent.SESSION_CLEANUP,
                details={"sessions_cleaned": count},
            )

        return count


def get_token_manager() -> SessionTokenManager:
    """
    Get or create the singleton token manager.

    Uses Redis if configured, otherwise falls back to in-memory storage.

    Returns:
        SessionTokenManager instance
    """
    global _token_manager

    if _token_manager is not None:
        return _token_manager

    settings = get_settings()

    # Create backend
    backend: TokenStorageBackend
    if settings.redis_url:
        backend = RedisTokenStorage(
            redis_url=settings.redis_url,
            require_tls=settings.require_redis_tls,
        )
        logger.info("Using Redis token storage")
    else:
        backend = InMemoryTokenStorage()
        logger.warning("Using in-memory token storage - tokens will not persist across restarts")

    # Create secure store
    store = SecureTokenStore(
        backend=backend,
        master_key=settings.master_key,
        master_keys=settings.master_keys,
        session_ttl=settings.session_max_age,
    )

    # Create manager
    _token_manager = SessionTokenManager(
        store=store,
        backend=backend,
    )

    return _token_manager


async def cleanup_token_manager() -> None:
    """Clean up token manager resources."""
    global _token_manager

    if _token_manager is not None:
        # Clean up backend if Redis
        if isinstance(_token_manager._backend, RedisTokenStorage):
            await _token_manager._backend.close()

        _token_manager = None
