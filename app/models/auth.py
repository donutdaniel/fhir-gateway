"""
Pydantic models for authentication.
"""

import time
from typing import Any

from pydantic import BaseModel, Field


class OAuthToken(BaseModel):
    """OAuth token with expiration tracking."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
    id_token: str | None = None
    expires_at: float | None = None
    created_at: float = Field(default_factory=time.time)

    def model_post_init(self, __context: Any) -> None:
        """Compute expiration timestamp from expires_in if provided."""
        if self.expires_in is not None and self.expires_at is None:
            self.expires_at = self.created_at + self.expires_in

    def seconds_until_expiry(self) -> float | None:
        """Get seconds remaining until token expires."""
        if self.expires_at is None:
            return None
        return self.expires_at - time.time()

    def has_expired(self, buffer_seconds: int = 120) -> bool:
        """Check if token has expired or will expire soon."""
        remaining = self.seconds_until_expiry()
        if remaining is None:
            return False
        return remaining < buffer_seconds

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired (with default buffer)."""
        return self.has_expired()


class AuthStatus(BaseModel):
    """Authentication status for a single platform."""

    platform_id: str
    authenticated: bool = False
    has_token: bool = False
    token_expires_at: float | None = None
    scopes: list[str] | None = None


class AuthStatusResponse(BaseModel):
    """Response for auth status endpoint."""

    platforms: dict[str, AuthStatus] = Field(
        default_factory=dict, description="Auth status by platform_id"
    )


class LoginResponse(BaseModel):
    """Response for login initiation."""

    authorization_url: str = Field(description="URL to redirect user for OAuth")
    state: str = Field(description="State parameter for CSRF protection")
    platform_id: str = Field(description="Platform being authenticated")


class CallbackResponse(BaseModel):
    """Response for OAuth callback."""

    success: bool
    platform_id: str
    message: str | None = None
    error: str | None = None
