"""
OAuth callback endpoint.

Handles the OAuth callback at /oauth/callback.
Platform and session are looked up from the state parameter.
"""

import html

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app.audit import AuditEvent, audit_log
from app.auth.identity import extract_user_identity
from app.auth.token_manager import get_token_manager
from app.config.platform import get_platform
from app.config.settings import get_settings
from app.rate_limiter import get_callback_rate_limiter
from app.routers.session import get_client_ip, get_session_id, set_session_cookie
from app.services.oauth import OAuthService

router = APIRouter(prefix="/oauth", tags=["oauth"])

CSP_HEADER = "default-src 'none'; style-src 'unsafe-inline'"


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str | None = Query(None, description="Authorization code"),
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
    # Rate limit by client IP to prevent abuse
    client_ip = get_client_ip(request)
    limiter = get_callback_rate_limiter()
    if not limiter.check(client_ip):
        audit_log(
            AuditEvent.SECURITY_RATE_LIMIT,
            success=False,
            details={"ip": client_ip, "endpoint": "/oauth/callback"},
        )
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Too Many Requests</title></head>
            <body>
                <h1>Too Many Requests</h1>
                <p>Please wait a moment and try again.</p>
            </body>
            </html>
            """,
            status_code=429,
            headers={"Content-Security-Policy": CSP_HEADER},
        )

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
            headers={"Content-Security-Policy": CSP_HEADER},
        )

    # Handle missing code (no error but also no code)
    if not code:
        audit_log(
            AuditEvent.AUTH_FAILURE,
            success=False,
            error="Missing authorization code",
        )
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Invalid Request</title></head>
            <body>
                <h1>Invalid Request</h1>
                <p>No authorization code was provided.</p>
                <p>Please close this window and try again.</p>
            </body>
            </html>
            """,
            status_code=400,
            headers={"Content-Security-Policy": CSP_HEADER},
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
            headers={"Content-Security-Policy": CSP_HEADER},
        )

    session_id = pending_auth["session_id"]
    platform_id = pending_auth["platform_id"]
    pkce_verifier = pending_auth["pkce_verifier"]
    mcp_initiated = pending_auth.get("mcp_initiated", False)

    # SESSION FIXATION PROTECTION:
    # Verify the browser's session cookie matches the session that initiated OAuth.
    # This prevents attacks where an attacker initiates OAuth on their session,
    # then tricks a victim into completing the callback.
    #
    # For MCP-initiated auth, we skip this check because:
    # - MCP sessions are server-side transport sessions, not browser cookies
    # - The browser will never have the MCP session cookie
    # - State + PKCE already protect against CSRF/replay attacks
    if not mcp_initiated:
        current_session = get_session_id(request, create_if_missing=False)
        if current_session and current_session != session_id:
            audit_log(
                AuditEvent.SECURITY_SESSION_MISMATCH,
                session_id=session_id,
                success=False,
                error="Session mismatch - possible session fixation attempt",
                details={"expected": session_id[:8] + "...", "got": current_session[:8] + "..."},
            )
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>Session Mismatch</title></head>
                <body>
                    <h1>Session Mismatch</h1>
                    <p>The authentication was started in a different browser session.</p>
                    <p>Please start the login process again from your application.</p>
                </body>
                </html>
                """,
                status_code=400,
                headers={"Content-Security-Policy": CSP_HEADER},
            )

    # Validate platform still exists and has OAuth configured
    platform = get_platform(platform_id)
    if not platform or not platform.oauth:
        audit_log(
            AuditEvent.AUTH_FAILURE,
            session_id=session_id,
            platform_id=platform_id,
            success=False,
            error="Platform not found or OAuth not configured",
        )
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Platform Error</title></head>
            <body>
                <h1>Platform Error</h1>
                <p>The platform is no longer available or OAuth is not configured.</p>
            </body>
            </html>
            """,
            status_code=400,
            headers={"Content-Security-Policy": CSP_HEADER},
        )

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

        # Extract and store user identity from id_token if available
        user_id = None
        if token.id_token:
            # Build token_response dict from OAuthToken fields for identity extraction
            token_response = {
                "id_token": token.id_token,
                "scope": token.scope,
            }
            identity = extract_user_identity(token_response)
            if identity:
                await token_manager.store_user_identity(session_id, platform_id, identity)
                user_id = identity.user_id

        # Clear pending auth
        await token_manager.clear_pending_auth(session_id, platform_id)

        audit_log(
            AuditEvent.AUTH_SUCCESS,
            session_id=session_id,
            platform_id=platform_id,
            user_id=user_id,
        )

        # platform was already validated above, use it directly
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
            headers={"Content-Security-Policy": CSP_HEADER},
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
            headers={"Content-Security-Policy": CSP_HEADER},
        )
