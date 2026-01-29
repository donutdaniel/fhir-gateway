"""
OAuth authentication endpoints.

Provides OAuth flow endpoints:
- GET /auth/{platform_id}/login - Redirect to OAuth authorize URL
- GET /auth/status - Get current auth status
- POST /auth/{platform_id}/logout - Clear session for platform

Note: OAuth callback is handled at /oauth/callback (see oauth.py).
"""

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.audit import AuditEvent, audit_log
from app.auth.token_manager import get_token_manager
from app.config.platform import get_platform
from app.config.settings import get_settings
from app.models.auth import (
    AuthStatus,
    AuthStatusResponse,
    LoginResponse,
)
from app.routers.session import get_session_id, set_session_cookie
from app.services.oauth import OAuthService

router = APIRouter(prefix="/auth", tags=["auth"])

# CSRF protection header - must be present on state-changing requests
# Browsers won't send custom headers in simple cross-origin requests without CORS preflight
CSRF_HEADER_NAME = "x-requested-with"
CSRF_HEADER_VALUE = "XMLHttpRequest"


@router.get("/{platform_id}/login", response_model=None)
async def login(
    platform_id: str,
    request: Request,
    redirect: bool = Query(True, description="Redirect to auth URL or return JSON"),
    scopes: str | None = Query(None, description="Space-separated OAuth scopes"),
):
    """
    Initiate OAuth login flow for a platform.

    Args:
        platform_id: The platform identifier
        redirect: If True, redirect to auth URL; if False, return JSON
        scopes: Optional OAuth scopes (space-separated)
    """
    platform = get_platform(platform_id)
    if not platform:
        raise HTTPException(status_code=404, detail=f"Platform '{platform_id}' not found")

    if not platform.oauth or not platform.oauth.authorize_url:
        raise HTTPException(
            status_code=400,
            detail=f"Platform '{platform_id}' does not support OAuth authentication",
        )

    settings = get_settings()
    callback_url = settings.oauth_redirect_uri
    session_id = get_session_id(request)

    try:
        oauth_service = OAuthService(
            platform_id=platform_id,
            redirect_uri=callback_url,
        )

        scope_list = scopes.split() if scopes else None
        auth_url, state, pkce = oauth_service.build_authorization_url(scopes=scope_list)

        # Store PKCE and state in token manager
        token_manager = get_token_manager()
        await token_manager.store_pending_auth(
            session_id=session_id,
            platform_id=platform_id,
            state=state,
            pkce_verifier=pkce.code_verifier,
        )

        audit_log(
            AuditEvent.AUTH_START,
            session_id=session_id,
            platform_id=platform_id,
        )

        if redirect:
            response = RedirectResponse(url=auth_url, status_code=302)
            set_session_cookie(response, session_id)
            return response

        return LoginResponse(
            authorization_url=auth_url,
            state=state,
            platform_id=platform_id,
        )

    except Exception as e:
        audit_log(
            AuditEvent.AUTH_FAILURE,
            session_id=session_id,
            platform_id=platform_id,
            success=False,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to build auth URL: {str(e)}")


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(request: Request) -> AuthStatusResponse:
    """
    Get authentication status for all platforms in the current session.
    """
    session_id = get_session_id(request)
    token_manager = get_token_manager()

    status_dict = await token_manager.get_auth_status(session_id)

    platforms = {}
    for platform_id, status in status_dict.items():
        platforms[platform_id] = AuthStatus(
            platform_id=platform_id,
            authenticated=status["authenticated"],
            has_token=status["has_token"],
            token_expires_at=status.get("expires_at"),
            scopes=status.get("scopes"),
        )

    return AuthStatusResponse(platforms=platforms)


@router.post("/{platform_id}/logout")
async def logout(
    platform_id: str,
    request: Request,
    x_requested_with: str | None = Header(None, alias="x-requested-with"),
) -> dict[str, Any]:
    """
    Clear authentication for a platform.

    Attempts to revoke tokens at the platform's OAuth server before
    removing them from local storage.

    CSRF Protection: Requires the X-Requested-With header to be set.
    This prevents cross-site request forgery attacks since browsers
    won't send custom headers in simple cross-origin requests.

    Args:
        platform_id: The platform identifier
        x_requested_with: CSRF protection header (required)
    """
    # CSRF protection: require custom header that can't be sent cross-origin
    # without CORS preflight (which would be blocked by our CORS policy)
    if not x_requested_with:
        audit_log(
            AuditEvent.SECURITY_CSRF_VIOLATION,
            success=False,
            error="Missing X-Requested-With header",
            details={"endpoint": f"/auth/{platform_id}/logout"},
        )
        raise HTTPException(
            status_code=403,
            detail="Missing required header: X-Requested-With",
        )

    session_id = get_session_id(request)
    token_manager = get_token_manager()
    settings = get_settings()

    # Get current token to revoke
    token = await token_manager.get_token(session_id, platform_id, auto_refresh=False)

    revoked = False
    if token:
        try:
            oauth_service = OAuthService(
                platform_id=platform_id,
                redirect_uri=settings.oauth_redirect_uri,
            )

            # Revoke refresh token first (if present), then access token
            if token.refresh_token:
                await oauth_service.revoke_token(
                    token.refresh_token,
                    token_type_hint="refresh_token",
                )

            revoked = await oauth_service.revoke_token(
                token.access_token,
                token_type_hint="access_token",
            )

        except Exception as e:
            # Log but don't fail - still remove from local storage
            audit_log(
                AuditEvent.AUTH_REVOKE,
                session_id=session_id,
                platform_id=platform_id,
                success=False,
                error=f"Revocation failed: {str(e)}",
            )

    # Always remove from local storage
    await token_manager.delete_token(session_id, platform_id)

    return {
        "success": True,
        "message": f"Logged out from {platform_id}",
        "token_revoked": revoked,
    }


@router.get("/{platform_id}/wait")
async def wait_for_auth(
    platform_id: str,
    request: Request,
    timeout: float = Query(300, description="Timeout in seconds"),
) -> dict[str, Any]:
    """
    Wait for OAuth callback to complete.

    Blocks until the OAuth callback is received or timeout is reached.
    Only one concurrent waiter is allowed per session/platform.

    Args:
        platform_id: The platform identifier
        timeout: Maximum wait time in seconds
    """
    session_id = get_session_id(request)
    token_manager = get_token_manager()

    token = await token_manager.wait_for_auth_complete(session_id, platform_id, timeout)

    if token is None:
        return {
            "success": False,
            "message": "Authentication timed out or already waiting",
        }

    return {
        "success": True,
        "message": "Authentication completed",
        "expires_in": int(token.seconds_until_expiry() or 0),
    }
