"""
OAuth callback endpoint.

Handles the OAuth callback at /oauth/callback.
Platform and session are looked up from the state parameter.
"""

import html

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app.audit import AuditEvent, audit_log
from app.auth.token_manager import get_token_manager
from app.config.platform import get_platform
from app.config.settings import get_settings
from app.services.oauth import OAuthService

router = APIRouter(prefix="/oauth", tags=["oauth"])


def _get_session_id(request: Request) -> str | None:
    """Get session ID from cookie."""
    settings = get_settings()
    return request.cookies.get(settings.session_cookie_name)


def _set_session_cookie(response: HTMLResponse, session_id: str) -> None:
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


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    error: str | None = Query(None, description="Error code"),
    error_description: str | None = Query(None, description="Error description"),
) -> HTMLResponse:
    """
    Handle OAuth callback.

    This endpoint receives the authorization code from the OAuth provider
    and exchanges it for tokens. The platform_id and session_id are looked
    up from the state parameter.
    """
    settings = get_settings()
    token_manager = get_token_manager()

    # Handle OAuth errors first
    if error:
        error_msg = html.escape(error_description or error)
        audit_log(
            AuditEvent.AUTH_FAILURE,
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

    # Look up pending auth by state
    pending_auth = await token_manager.get_pending_auth_by_state(state)
    if not pending_auth:
        audit_log(
            AuditEvent.SECURITY_INVALID_STATE,
            success=False,
            error="State not found",
        )
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Invalid State</title></head>
            <body>
                <h1>Invalid State</h1>
                <p>The authorization state was not found or has expired.</p>
                <p>Please start the login process again.</p>
            </body>
            </html>
            """,
            status_code=400,
            headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
        )

    session_id = pending_auth["session_id"]
    platform_id = pending_auth["platform_id"]
    pkce_verifier = pending_auth["pkce_verifier"]

    # Exchange code for tokens
    try:
        oauth_service = OAuthService(
            platform_id=platform_id,
            redirect_uri=settings.oauth_redirect_uri,
        )

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
        _set_session_cookie(response, session_id)
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
