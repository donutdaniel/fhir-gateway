"""
OAuth authentication endpoints.

Provides OAuth flow endpoints:
- GET /auth/{platform_id}/login - Redirect to OAuth authorize URL
- GET /auth/callback - OAuth callback handler
- GET /auth/status - Get current auth status
- POST /auth/{platform_id}/logout - Clear session for platform
"""

import html
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.audit import AuditEvent, audit_log
from app.auth.token_manager import get_token_manager
from app.config.platform import get_platform
from app.config.settings import get_settings
from app.models.auth import (
    AuthStatus,
    AuthStatusResponse,
    LoginResponse,
)
from app.services.oauth import OAuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_session_id(request: Request) -> str:
    """Get or create session ID from cookie."""
    settings = get_settings()
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id


def set_session_cookie(response: Response, session_id: str) -> None:
    """Set session cookie on response."""
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


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
    callback_url = f"{settings.oauth_redirect_uri}/{platform_id}"
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


@router.get("/callback/{platform_id}")
async def oauth_callback(
    platform_id: str,
    request: Request,
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    error: str | None = Query(None, description="Error code"),
    error_description: str | None = Query(None, description="Error description"),
) -> HTMLResponse:
    """
    Handle OAuth callback.

    This endpoint receives the authorization code from the OAuth provider
    and exchanges it for tokens.

    Args:
        platform_id: The platform identifier
        code: Authorization code
        state: State parameter for CSRF validation
        error: Error code if auth failed
        error_description: Error description
    """
    settings = get_settings()
    session_id = get_session_id(request)
    token_manager = get_token_manager()

    # Handle OAuth errors
    if error:
        error_msg = html.escape(error_description or error)
        audit_log(
            AuditEvent.AUTH_FAILURE,
            session_id=session_id,
            platform_id=platform_id,
            success=False,
            error=error_msg,
        )
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head><title>Authentication Failed</title></head>
            <body>
                <h1>Authentication Failed</h1>
                <p>Error: {error_msg}</p>
                <p>Please close this window and try again.</p>
            </body>
            </html>
            """,
            status_code=400,
            headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
        )

    # Get pending auth data
    pending_auth = await token_manager.get_pending_auth(session_id, platform_id)
    if not pending_auth:
        audit_log(
            AuditEvent.SECURITY_INVALID_STATE,
            session_id=session_id,
            platform_id=platform_id,
            success=False,
            error="Session not found",
        )
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Session Expired</title></head>
            <body>
                <h1>Session Expired</h1>
                <p>Your session has expired. Please start the login process again.</p>
            </body>
            </html>
            """,
            status_code=400,
            headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
        )

    # Verify state
    expected_state = pending_auth.get("state")
    if state != expected_state:
        audit_log(
            AuditEvent.SECURITY_INVALID_STATE,
            session_id=session_id,
            platform_id=platform_id,
            success=False,
            error="State mismatch",
        )
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Invalid State</title></head>
            <body>
                <h1>Invalid State</h1>
                <p>The state parameter does not match. This may be a CSRF attack.</p>
            </body>
            </html>
            """,
            status_code=400,
            headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
        )

    # Exchange code for tokens
    try:
        callback_url = f"{settings.oauth_redirect_uri}/{platform_id}"
        oauth_service = OAuthService(
            platform_id=platform_id,
            redirect_uri=callback_url,
        )

        pkce_verifier = pending_auth["pkce_verifier"]
        token = await oauth_service.exchange_code(
            code=code,
            code_verifier=pkce_verifier,
            state=state,
        )

        # Store token in session via token manager
        await token_manager.store_token(session_id, platform_id, token)

        # Clear pending auth
        await token_manager.clear_pending_auth(session_id, platform_id)

        audit_log(
            AuditEvent.AUTH_SUCCESS,
            session_id=session_id,
            platform_id=platform_id,
        )

        platform = get_platform(platform_id)
        platform_name = html.escape(platform.display_name if platform else platform_id)

        response = HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head><title>Authentication Successful</title></head>
            <body>
                <h1>Authentication Successful</h1>
                <p>You have been authenticated with {platform_name}.</p>
                <p>You can close this window and return to your application.</p>
            </body>
            </html>
            """,
            status_code=200,
            headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
        )
        set_session_cookie(response, session_id)
        return response

    except Exception as e:
        error_msg = html.escape(str(e))
        audit_log(
            AuditEvent.AUTH_FAILURE,
            session_id=session_id,
            platform_id=platform_id,
            success=False,
            error=str(e),
        )
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head><title>Token Exchange Failed</title></head>
            <body>
                <h1>Token Exchange Failed</h1>
                <p>Error: {error_msg}</p>
            </body>
            </html>
            """,
            status_code=500,
            headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
        )


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
async def logout(platform_id: str, request: Request) -> dict[str, Any]:
    """
    Clear authentication for a platform.

    Attempts to revoke tokens at the platform's OAuth server before
    removing them from local storage.

    Args:
        platform_id: The platform identifier
    """
    session_id = get_session_id(request)
    token_manager = get_token_manager()
    settings = get_settings()

    # Get current token to revoke
    token = await token_manager.get_token(session_id, platform_id, auto_refresh=False)

    revoked = False
    if token:
        try:
            callback_url = f"{settings.oauth_redirect_uri}/{platform_id}"
            oauth_service = OAuthService(
                platform_id=platform_id,
                redirect_uri=callback_url,
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


@router.get("/token/{platform_id}")
async def get_token(platform_id: str, request: Request) -> dict[str, Any]:
    """
    Get the current access token for a platform (internal use).

    This endpoint is for internal use to retrieve tokens for FHIR requests.
    In production, tokens should be handled server-side only.

    Args:
        platform_id: The platform identifier
    """
    session_id = get_session_id(request)
    token_manager = get_token_manager()

    # Get token with auto-refresh
    token = await token_manager.get_token(session_id, platform_id, auto_refresh=True)

    if not token:
        raise HTTPException(status_code=401, detail=f"No token for platform '{platform_id}'")

    if token.is_expired:
        raise HTTPException(status_code=401, detail="Token expired, re-authentication required")

    return {
        "access_token": token.access_token,
        "token_type": token.token_type,
        "expires_in": int(token.seconds_until_expiry() or 0),
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
