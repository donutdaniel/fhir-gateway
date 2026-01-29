"""
Tests for MCP auth tools.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from app.mcp.tools.auth import register_auth_tools


@pytest.fixture
def mock_ctx():
    """Create mock MCP context with session ID."""
    ctx = MagicMock()
    ctx.client_id = "sess-123"
    ctx.request_id = "req-456"
    # Mock request context to not have mcp-session-id header
    request = MagicMock()
    request.headers = MagicMock()
    request.headers.get = MagicMock(return_value=None)
    ctx.request_context = MagicMock()
    ctx.request_context.request = request
    return ctx


class TestStartAuth:
    """Tests for start_auth tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        mcp.settings.host = "localhost"
        mcp.settings.port = 8000
        register_auth_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_platform(self):
        """Create mock platform config."""
        platform = MagicMock()
        platform.oauth = MagicMock()
        platform.oauth.authorize_url = "https://auth.test.com/authorize"
        return platform

    @pytest.mark.asyncio
    async def test_start_auth_success(self, mcp, mock_platform, mock_ctx):
        """Should return authorization URL and session info."""
        mock_token_manager = AsyncMock()
        mock_oauth_service = MagicMock()
        mock_pkce = MagicMock()
        mock_pkce.code_verifier = "test-verifier"
        mock_oauth_service.build_authorization_url = MagicMock(
            return_value=("https://auth.test.com/authorize?client_id=test", "test-state", mock_pkce)
        )

        with (
            patch("app.mcp.tools.auth.get_platform", return_value=mock_platform),
            patch("app.mcp.tools.auth.get_settings") as mock_settings,
            patch("app.mcp.tools.auth.OAuthService", return_value=mock_oauth_service),
            patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager),
            patch("app.mcp.tools.auth.audit_log"),
        ):
            mock_settings.return_value.oauth_redirect_uri = "http://localhost:8000/oauth/callback"

            tools = mcp._tool_manager._tools
            start_auth = tools["start_auth"].fn

            result = await start_auth(
                platform_id="test-payer",
                ctx=mock_ctx,
            )

        assert "authorization_url" in result
        assert result["platform_id"] == "test-payer"
        assert result["session_id"] == "sess-123"
        assert result["state"] == "test-state"

    @pytest.mark.asyncio
    async def test_start_auth_with_scopes(self, mcp, mock_platform, mock_ctx):
        """Should pass scopes to OAuth service."""
        mock_token_manager = AsyncMock()
        mock_oauth_service = MagicMock()
        mock_pkce = MagicMock()
        mock_pkce.code_verifier = "test-verifier"
        mock_oauth_service.build_authorization_url = MagicMock(
            return_value=("https://auth.test.com/authorize?client_id=test", "test-state", mock_pkce)
        )

        with (
            patch("app.mcp.tools.auth.get_platform", return_value=mock_platform),
            patch("app.mcp.tools.auth.get_settings") as mock_settings,
            patch("app.mcp.tools.auth.OAuthService", return_value=mock_oauth_service),
            patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager),
            patch("app.mcp.tools.auth.audit_log"),
        ):
            mock_settings.return_value.oauth_redirect_uri = "http://localhost:8000/oauth/callback"

            tools = mcp._tool_manager._tools
            start_auth = tools["start_auth"].fn

            await start_auth(
                platform_id="test-payer",
                ctx=mock_ctx,
                scopes=["openid", "patient/*.read"],
            )

        mock_oauth_service.build_authorization_url.assert_called_once_with(
            scopes=["openid", "patient/*.read"]
        )

    @pytest.mark.asyncio
    async def test_start_auth_invalid_platform_id(self, mcp, mock_ctx):
        """Should return validation error for invalid platform_id."""
        tools = mcp._tool_manager._tools
        start_auth = tools["start_auth"].fn

        result = await start_auth(
            platform_id="invalid@platform!",
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"
        assert "Invalid platform_id" in result["message"]

    @pytest.mark.asyncio
    async def test_start_auth_platform_not_found(self, mcp, mock_ctx):
        """Should return error when platform not found."""
        with patch("app.mcp.tools.auth.get_platform", return_value=None):
            tools = mcp._tool_manager._tools
            start_auth = tools["start_auth"].fn

            result = await start_auth(
                platform_id="unknown",
                ctx=mock_ctx,
            )

        assert result["error"] == "platform_not_found"

    @pytest.mark.asyncio
    async def test_start_auth_oauth_not_configured(self, mcp, mock_ctx):
        """Should return error when OAuth not configured."""
        mock_platform = MagicMock()
        mock_platform.oauth = None

        with patch("app.mcp.tools.auth.get_platform", return_value=mock_platform):
            tools = mcp._tool_manager._tools
            start_auth = tools["start_auth"].fn

            result = await start_auth(
                platform_id="test-payer",
                ctx=mock_ctx,
            )

        assert result["error"] == "oauth_not_configured"

    @pytest.mark.asyncio
    async def test_start_auth_oauth_no_authorize_url(self, mcp, mock_ctx):
        """Should return error when OAuth authorize URL not set."""
        mock_platform = MagicMock()
        mock_platform.oauth = MagicMock()
        mock_platform.oauth.authorize_url = None

        with patch("app.mcp.tools.auth.get_platform", return_value=mock_platform):
            tools = mcp._tool_manager._tools
            start_auth = tools["start_auth"].fn

            result = await start_auth(
                platform_id="test-payer",
                ctx=mock_ctx,
            )

        assert result["error"] == "oauth_not_configured"

    @pytest.mark.asyncio
    async def test_start_auth_no_session_id(self, mcp):
        """Should return error when no session ID available."""
        ctx = MagicMock()
        ctx.client_id = None
        ctx.request_id = None
        ctx.request_context = MagicMock()
        ctx.request_context.request = MagicMock()
        ctx.request_context.request.headers = MagicMock()
        ctx.request_context.request.headers.get = MagicMock(return_value=None)

        tools = mcp._tool_manager._tools
        start_auth = tools["start_auth"].fn

        result = await start_auth(
            platform_id="test-payer",
            ctx=ctx,
        )

        assert result["error"] == "session_error"


class TestWaitForAuth:
    """Tests for wait_for_auth tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_auth_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_token(self):
        """Create mock OAuth token."""
        token = MagicMock()
        token.seconds_until_expiry = MagicMock(return_value=3600)
        return token

    @pytest.mark.asyncio
    async def test_wait_for_auth_success(self, mcp, mock_token, mock_ctx):
        """Should return success when auth completes."""
        mock_token_manager = AsyncMock()
        mock_token_manager.wait_for_auth_complete = AsyncMock(return_value=mock_token)

        with (
            patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager),
            patch("app.mcp.tools.auth.audit_log"),
        ):
            tools = mcp._tool_manager._tools
            wait_for_auth = tools["wait_for_auth"].fn

            result = await wait_for_auth(
                platform_id="test-payer",
                ctx=mock_ctx,
                timeout=300,
            )

        assert result["success"] is True
        assert result["expires_in"] == 3600
        mock_token_manager.wait_for_auth_complete.assert_called_once_with("sess-123", "test-payer", 300)

    @pytest.mark.asyncio
    async def test_wait_for_auth_timeout(self, mcp, mock_ctx):
        """Should return error on timeout."""
        mock_token_manager = AsyncMock()
        mock_token_manager.wait_for_auth_complete = AsyncMock(return_value=None)

        with patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager):
            tools = mcp._tool_manager._tools
            wait_for_auth = tools["wait_for_auth"].fn

            result = await wait_for_auth(
                platform_id="test-payer",
                ctx=mock_ctx,
                timeout=60,
            )

        assert result["error"] == "timeout"
        assert "60s" in result["message"]

    @pytest.mark.asyncio
    async def test_wait_for_auth_exception(self, mcp, mock_ctx):
        """Should handle exceptions gracefully."""
        mock_token_manager = AsyncMock()
        mock_token_manager.wait_for_auth_complete = AsyncMock(side_effect=Exception("Wait failed"))

        with patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager):
            tools = mcp._tool_manager._tools
            wait_for_auth = tools["wait_for_auth"].fn

            result = await wait_for_auth(
                platform_id="test-payer",
                ctx=mock_ctx,
            )

        assert result["error"] == "internal_error"


class TestGetAuthStatus:
    """Tests for get_auth_status tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_auth_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_get_auth_status_all_platforms(self, mcp, mock_ctx):
        """Should return status for all platforms."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_auth_status = AsyncMock(
            return_value={
                "aetna": {"authenticated": True, "has_token": True},
                "cigna": {"authenticated": False, "has_token": False},
            }
        )

        with patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager):
            tools = mcp._tool_manager._tools
            get_auth_status = tools["get_auth_status"].fn

            result = await get_auth_status(ctx=mock_ctx)

        assert result["session_id"] == "sess-123"
        assert "platforms" in result
        assert "aetna" in result["platforms"]
        assert result["platforms"]["aetna"]["authenticated"] is True

    @pytest.mark.asyncio
    async def test_get_auth_status_single_platform(self, mcp, mock_ctx):
        """Should return status for specific platform."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_auth_status = AsyncMock(
            return_value={
                "aetna": {"authenticated": True, "has_token": True},
            }
        )

        with patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager):
            tools = mcp._tool_manager._tools
            get_auth_status = tools["get_auth_status"].fn

            result = await get_auth_status(
                ctx=mock_ctx,
                platform_id="aetna",
            )

        assert result["session_id"] == "sess-123"
        assert result["platform_id"] == "aetna"
        assert result["authenticated"] is True
        assert "platforms" not in result

    @pytest.mark.asyncio
    async def test_get_auth_status_unknown_platform(self, mcp, mock_ctx):
        """Should return default status for unknown platform."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_auth_status = AsyncMock(return_value={})

        with patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager):
            tools = mcp._tool_manager._tools
            get_auth_status = tools["get_auth_status"].fn

            result = await get_auth_status(
                ctx=mock_ctx,
                platform_id="unknown",
            )

        assert result["authenticated"] is False
        assert result["has_token"] is False

    @pytest.mark.asyncio
    async def test_get_auth_status_exception(self, mcp, mock_ctx):
        """Should handle exceptions gracefully."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_auth_status = AsyncMock(side_effect=Exception("Status error"))

        with patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager):
            tools = mcp._tool_manager._tools
            get_auth_status = tools["get_auth_status"].fn

            result = await get_auth_status(ctx=mock_ctx)

        assert result["error"] == "internal_error"


class TestRevokeAuth:
    """Tests for revoke_auth tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_auth_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_revoke_auth_success(self, mcp, mock_ctx):
        """Should revoke auth successfully."""
        mock_token_manager = AsyncMock()
        mock_token_manager.delete_token = AsyncMock()

        with (
            patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager),
            patch("app.mcp.tools.auth.audit_log"),
        ):
            tools = mcp._tool_manager._tools
            revoke_auth = tools["revoke_auth"].fn

            result = await revoke_auth(
                platform_id="test-payer",
                ctx=mock_ctx,
            )

        assert result["success"] is True
        assert "test-payer" in result["message"]
        mock_token_manager.delete_token.assert_called_once_with("sess-123", "test-payer")

    @pytest.mark.asyncio
    async def test_revoke_auth_exception(self, mcp, mock_ctx):
        """Should handle exceptions gracefully."""
        mock_token_manager = AsyncMock()
        mock_token_manager.delete_token = AsyncMock(side_effect=Exception("Delete failed"))

        with patch("app.mcp.tools.auth.get_token_manager", return_value=mock_token_manager):
            tools = mcp._tool_manager._tools
            revoke_auth = tools["revoke_auth"].fn

            result = await revoke_auth(
                platform_id="test-payer",
                ctx=mock_ctx,
            )

        assert result["error"] == "internal_error"
