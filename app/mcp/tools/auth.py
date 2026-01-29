"""
OAuth authentication tools.

Thin wrappers around app.services.oauth and auth.token_manager.
"""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from app.audit import AuditEvent, audit_log
from app.auth.token_manager import get_token_manager
from app.config.platform import get_platform
from app.config.settings import get_settings
from app.mcp.errors import error_response, handle_exception
from app.mcp.validation import validate_platform_id
from app.services.oauth import OAuthService


def register_auth_tools(mcp: FastMCP) -> None:
    """Register OAuth authentication tools."""

    @mcp.tool(
        description="Start OAuth authentication flow for a platform. Returns URL for user to visit."
    )
    async def start_auth(
        platform_id: Annotated[str, Field(description="Platform identifier to authenticate with")],
        session_id: Annotated[
            str, Field(description="Unique session identifier for this auth flow")
        ],
        scopes: Annotated[list[str] | None, Field(description="OAuth scopes to request")] = None,
    ) -> dict[str, Any]:
        """Initiate OAuth flow for a platform."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)

        platform = get_platform(platform_id)
        if not platform:
            return error_response("platform_not_found", f"Platform '{platform_id}' not found")
        if not platform.oauth or not platform.oauth.authorize_url:
            return error_response(
                "oauth_not_configured", f"Platform '{platform_id}' does not have OAuth configured"
            )

        try:
            settings = get_settings()
            redirect_uri = settings.oauth_redirect_uri or "http://localhost:8000/auth/callback"

            oauth_service = OAuthService(
                platform_id=platform_id,
                redirect_uri=f"{redirect_uri}/{platform_id}",
            )

            auth_url, state, pkce = oauth_service.build_authorization_url(scopes=scopes)

            # Store pending auth state
            token_manager = get_token_manager()
            await token_manager.store_pending_auth(
                session_id=session_id,
                platform_id=platform_id,
                state=state,
                pkce_verifier=pkce.code_verifier,
            )

            audit_log(AuditEvent.AUTH_START, platform_id=platform_id, session_id=session_id)

            return {
                "authorization_url": auth_url,
                "state": state,
                "session_id": session_id,
                "platform_id": platform_id,
                "message": "Direct user to authorization_url. After login, call wait_for_auth or complete_auth.",
            }
        except Exception as e:
            return handle_exception(e, "start_auth")

    @mcp.tool(
        description="Wait for OAuth callback to complete. Blocks until user finishes login or timeout."
    )
    async def wait_for_auth(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        session_id: Annotated[str, Field(description="Session ID from start_auth")],
        timeout: Annotated[int, Field(description="Timeout in seconds", ge=1, le=600)] = 300,
    ) -> dict[str, Any]:
        """Wait for OAuth callback to complete."""
        try:
            token_manager = get_token_manager()
            token = await token_manager.wait_for_auth_complete(session_id, platform_id, timeout)

            if token is None:
                return error_response(
                    "timeout", f"Authentication timed out after {timeout}s or already waiting"
                )

            audit_log(AuditEvent.AUTH_SUCCESS, platform_id=platform_id, session_id=session_id)
            return {
                "success": True,
                "platform_id": platform_id,
                "expires_in": int(token.seconds_until_expiry() or 0),
                "message": "Authentication completed. You can now make FHIR requests.",
            }
        except Exception as e:
            return handle_exception(e, "wait_for_auth")

    @mcp.tool(description="Get authentication status for platforms in a session.")
    async def get_auth_status(
        session_id: Annotated[str, Field(description="Session identifier")],
        platform_id: Annotated[
            str | None, Field(description="Specific platform to check (optional)")
        ] = None,
    ) -> dict[str, Any]:
        """Get current auth status for a session."""
        try:
            token_manager = get_token_manager()
            status = await token_manager.get_auth_status(session_id)

            if platform_id:
                platform_status = status.get(platform_id, {"authenticated": False, "has_token": False})
                return {"session_id": session_id, "platform_id": platform_id, **platform_status}

            return {"session_id": session_id, "platforms": status}
        except Exception as e:
            return handle_exception(e, "get_auth_status")

    @mcp.tool(description="Revoke authentication for a platform, clearing stored tokens.")
    async def revoke_auth(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        session_id: Annotated[str, Field(description="Session identifier")],
    ) -> dict[str, Any]:
        """Clear authentication for a platform."""
        try:
            token_manager = get_token_manager()
            await token_manager.delete_token(session_id, platform_id)
            audit_log(AuditEvent.AUTH_REVOKE, platform_id=platform_id, session_id=session_id)
            return {"success": True, "message": f"Revoked authentication for {platform_id}"}
        except Exception as e:
            return handle_exception(e, "revoke_auth")
