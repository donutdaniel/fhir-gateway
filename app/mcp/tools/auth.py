"""
OAuth authentication tools.

Provides MCP tools for OAuth authentication flows.
Uses OAuthService directly to build provider authorization URLs.
Session ID is obtained automatically from MCP context.
"""

from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from app.audit import AuditEvent, audit_log
from app.auth.token_manager import get_token_manager
from app.config.platform import get_platform
from app.config.settings import get_settings
from app.mcp.auth_handle import create_auth_handle, verify_auth_handle
from app.mcp.errors import error_response, handle_exception
from app.mcp.session import get_session_id
from app.mcp.validation import validate_platform_id
from app.services.oauth import OAuthService


def _resolve_session_id(
    ctx: Context, auth_handle: str | None, platform_id: str | None = None
) -> str | None:
    """
    Resolve session ID from auth_handle or MCP context.

    Priority:
    1. Verify and extract from auth_handle if provided
    2. Fall back to MCP transport session ID
    """
    if auth_handle:
        session_id = verify_auth_handle(auth_handle, platform_id)
        if session_id:
            return session_id
        # Invalid handle - don't fall back, return None to signal error
        return None

    return get_session_id(ctx)


def register_auth_tools(mcp: FastMCP) -> None:
    """Register OAuth authentication tools."""

    @mcp.tool(
        description="Start OAuth authentication flow for a platform. Returns the provider's authorization URL for user to visit."
    )
    async def start_auth(
        platform_id: Annotated[str, Field(description="Platform identifier to authenticate with")],
        ctx: Context,
        scopes: Annotated[list[str] | None, Field(description="OAuth scopes to request")] = None,
    ) -> dict[str, Any]:
        """Initiate OAuth flow for a platform."""
        session_id = get_session_id(ctx)
        if not session_id:
            return error_response("session_error", "No MCP session ID available")

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

            oauth_service = OAuthService(
                platform_id=platform_id,
                redirect_uri=settings.oauth_redirect_uri,
            )

            # Build authorization URL with PKCE
            auth_url, state, pkce = oauth_service.build_authorization_url(scopes=scopes)

            # Store pending auth state for callback
            token_manager = get_token_manager()
            await token_manager.store_pending_auth(
                session_id=session_id,
                platform_id=platform_id,
                state=state,
                pkce_verifier=pkce.code_verifier,
                mcp_initiated=True,  # Skip browser session validation in callback
            )

            # Create signed auth handle for session correlation
            auth_handle = create_auth_handle(session_id, platform_id)

            audit_log(AuditEvent.AUTH_START, platform_id=platform_id, session_id=session_id)

            return {
                "authorization_url": auth_url,
                "state": state,
                "auth_handle": auth_handle,
                "platform_id": platform_id,
                "message": "Direct user to authorization_url to authenticate. Then call wait_for_auth with the auth_handle.",
            }
        except Exception as e:
            return handle_exception(e, "start_auth")

    @mcp.tool(
        description="Wait for OAuth callback to complete. Blocks until user finishes login or timeout."
    )
    async def wait_for_auth(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        ctx: Context,
        timeout: Annotated[int, Field(description="Timeout in seconds", ge=1, le=600)] = 300,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (required for stable session correlation)")
        ] = None,
    ) -> dict[str, Any]:
        """Wait for OAuth callback to complete."""
        session_id = _resolve_session_id(ctx, auth_handle, platform_id)
        if not session_id:
            if auth_handle:
                return error_response("invalid_auth_handle", "Auth handle is invalid or expired")
            return error_response("session_error", "No MCP session ID available")

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
                "auth_handle": auth_handle or create_auth_handle(session_id, platform_id),
                "expires_in": int(token.seconds_until_expiry() or 0),
                "message": "Authentication completed. You can now make FHIR requests using the auth_handle.",
            }
        except Exception as e:
            return handle_exception(e, "wait_for_auth")

    @mcp.tool(description="Get authentication status for platforms in this session.")
    async def get_auth_status(
        ctx: Context,
        platform_id: Annotated[
            str | None, Field(description="Specific platform to check (optional)")
        ] = None,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for stable session correlation)")
        ] = None,
    ) -> dict[str, Any]:
        """Get current auth status for a session."""
        session_id = _resolve_session_id(ctx, auth_handle, platform_id)
        if not session_id:
            if auth_handle:
                return error_response("invalid_auth_handle", "Auth handle is invalid or expired")
            return error_response("session_error", "No MCP session ID available")

        try:
            token_manager = get_token_manager()
            status = await token_manager.get_auth_status(session_id)

            if platform_id:
                platform_status = status.get(
                    platform_id, {"authenticated": False, "has_token": False}
                )
                return {"platform_id": platform_id, **platform_status}

            return {"platforms": status}
        except Exception as e:
            return handle_exception(e, "get_auth_status")

    @mcp.tool(description="Revoke authentication for a platform, clearing stored tokens.")
    async def revoke_auth(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        ctx: Context,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for stable session correlation)")
        ] = None,
    ) -> dict[str, Any]:
        """Clear authentication for a platform."""
        session_id = _resolve_session_id(ctx, auth_handle, platform_id)
        if not session_id:
            if auth_handle:
                return error_response("invalid_auth_handle", "Auth handle is invalid or expired")
            return error_response("session_error", "No MCP session ID available")

        try:
            token_manager = get_token_manager()
            await token_manager.delete_token(session_id, platform_id)
            audit_log(AuditEvent.AUTH_REVOKE, platform_id=platform_id, session_id=session_id)
            return {"success": True, "message": f"Revoked authentication for {platform_id}"}
        except Exception as e:
            return handle_exception(e, "revoke_auth")
