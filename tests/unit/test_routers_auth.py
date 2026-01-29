"""
Tests for auth router endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.auth import router as auth_router
from app.routers.oauth import router as oauth_router


@pytest.fixture
def app():
    """Create test FastAPI app with auth and oauth routers."""
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(oauth_router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestLogin:
    """Tests for GET /auth/{platform_id}/login."""

    @pytest.fixture
    def mock_platform(self):
        """Create mock platform config."""
        platform = MagicMock()
        platform.oauth = MagicMock()
        platform.oauth.authorize_url = "https://auth.test.com/authorize"
        return platform

    @pytest.fixture
    def mock_oauth_service(self):
        """Create mock OAuth service."""
        service = MagicMock()
        pkce = MagicMock()
        pkce.code_verifier = "test-verifier"
        service.build_authorization_url = MagicMock(
            return_value=("https://auth.test.com/authorize?client_id=test", "test-state", pkce)
        )
        return service

    def test_login_redirect(self, client, mock_platform, mock_oauth_service):
        """Should redirect to authorization URL by default."""
        mock_token_manager = AsyncMock()

        with (
            patch("app.routers.auth.get_platform", return_value=mock_platform),
            patch("app.routers.auth.get_settings") as mock_settings,
            patch("app.routers.auth.OAuthService", return_value=mock_oauth_service),
            patch("app.routers.auth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.auth.audit_log"),
        ):
            mock_settings.return_value.oauth_redirect_uri = "http://localhost:8000/auth/callback"
            mock_settings.return_value.session_cookie_name = "fhir_session"
            mock_settings.return_value.session_max_age = 3600
            mock_settings.return_value.session_cookie_secure = False

            response = client.get("/auth/test-payer/login", follow_redirects=False)

        assert response.status_code == 302
        assert "auth.test.com" in response.headers["location"]

    def test_login_json_response(self, client, mock_platform, mock_oauth_service):
        """Should return JSON when redirect=false."""
        mock_token_manager = AsyncMock()

        with (
            patch("app.routers.auth.get_platform", return_value=mock_platform),
            patch("app.routers.auth.get_settings") as mock_settings,
            patch("app.routers.auth.OAuthService", return_value=mock_oauth_service),
            patch("app.routers.auth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.auth.audit_log"),
        ):
            mock_settings.return_value.oauth_redirect_uri = "http://localhost:8000/auth/callback"
            mock_settings.return_value.session_cookie_name = "fhir_session"
            mock_settings.return_value.session_max_age = 3600
            mock_settings.return_value.session_cookie_secure = False

            response = client.get("/auth/test-payer/login?redirect=false")

        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert data["state"] == "test-state"
        assert data["platform_id"] == "test-payer"

    def test_login_with_scopes(self, client, mock_platform, mock_oauth_service):
        """Should pass scopes to OAuth service."""
        mock_token_manager = AsyncMock()

        with (
            patch("app.routers.auth.get_platform", return_value=mock_platform),
            patch("app.routers.auth.get_settings") as mock_settings,
            patch("app.routers.auth.OAuthService", return_value=mock_oauth_service),
            patch("app.routers.auth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.auth.audit_log"),
        ):
            mock_settings.return_value.oauth_redirect_uri = "http://localhost:8000/auth/callback"
            mock_settings.return_value.session_cookie_name = "fhir_session"
            mock_settings.return_value.session_max_age = 3600
            mock_settings.return_value.session_cookie_secure = False

            client.get("/auth/test-payer/login?redirect=false&scopes=openid%20patient/*.read")

        mock_oauth_service.build_authorization_url.assert_called_once_with(
            scopes=["openid", "patient/*.read"]
        )

    def test_login_platform_not_found(self, client):
        """Should return 404 when platform not found."""
        with patch("app.routers.auth.get_platform", return_value=None):
            response = client.get("/auth/unknown/login")

        assert response.status_code == 404

    def test_login_oauth_not_configured(self, client):
        """Should return 400 when OAuth not configured."""
        mock_platform = MagicMock()
        mock_platform.oauth = None

        with patch("app.routers.auth.get_platform", return_value=mock_platform):
            response = client.get("/auth/test-payer/login")

        assert response.status_code == 400

    def test_login_oauth_no_authorize_url(self, client):
        """Should return 400 when OAuth has no authorize URL."""
        mock_platform = MagicMock()
        mock_platform.oauth = MagicMock()
        mock_platform.oauth.authorize_url = None

        with patch("app.routers.auth.get_platform", return_value=mock_platform):
            response = client.get("/auth/test-payer/login")

        assert response.status_code == 400


class TestOAuthCallback:
    """Tests for GET /oauth/callback."""

    def test_callback_error_response(self, client):
        """Should return HTML error for OAuth error."""
        with patch("app.routers.oauth.audit_log"):
            response = client.get(
                "/oauth/callback?code=test&state=test&error=access_denied&error_description=User%20denied"
            )

        assert response.status_code == 400
        assert "Authentication Failed" in response.text

    def test_callback_session_not_found(self, client):
        """Should return error when state not found."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_pending_auth_by_state = AsyncMock(return_value=None)

        with (
            patch("app.routers.oauth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.oauth.audit_log"),
        ):
            response = client.get("/oauth/callback?code=test-code&state=test-state")

        assert response.status_code == 400
        assert "Invalid State" in response.text

    def test_callback_state_mismatch(self, client):
        """Should return error when state not found (no separate mismatch check)."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_pending_auth_by_state = AsyncMock(return_value=None)

        with (
            patch("app.routers.oauth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.oauth.audit_log"),
        ):
            response = client.get("/oauth/callback?code=test-code&state=wrong-state")

        assert response.status_code == 400
        assert "Invalid State" in response.text

    def test_callback_platform_not_found(self, client):
        """Should return error when platform is not found."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_pending_auth_by_state = AsyncMock(
            return_value={
                "session_id": "test-session",
                "platform_id": "missing-platform",
                "state": "test-state",
                "pkce_verifier": "test-verifier",
            }
        )

        with (
            patch("app.routers.oauth.get_settings") as mock_settings,
            patch("app.routers.oauth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.oauth.get_platform", return_value=None),
            patch("app.routers.oauth.audit_log"),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"

            response = client.get("/oauth/callback?code=test-code&state=test-state")

        assert response.status_code == 400
        assert "Platform Error" in response.text

    def test_callback_platform_no_oauth(self, client):
        """Should return error when platform has no OAuth configured."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_pending_auth_by_state = AsyncMock(
            return_value={
                "session_id": "test-session",
                "platform_id": "test-payer",
                "state": "test-state",
                "pkce_verifier": "test-verifier",
            }
        )

        mock_platform = MagicMock()
        mock_platform.oauth = None

        with (
            patch("app.routers.oauth.get_settings") as mock_settings,
            patch("app.routers.oauth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.oauth.get_platform", return_value=mock_platform),
            patch("app.routers.oauth.audit_log"),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"

            response = client.get("/oauth/callback?code=test-code&state=test-state")

        assert response.status_code == 400
        assert "Platform Error" in response.text

    def test_callback_success(self, client):
        """Should exchange code and store token successfully."""
        mock_token = MagicMock()
        mock_token.access_token = "test-access-token"

        mock_token_manager = AsyncMock()
        mock_token_manager.get_pending_auth_by_state = AsyncMock(
            return_value={
                "session_id": "test-session",
                "platform_id": "test-payer",
                "state": "test-state",
                "pkce_verifier": "test-verifier",
            }
        )
        mock_token_manager.store_token = AsyncMock()
        mock_token_manager.clear_pending_auth = AsyncMock()

        mock_oauth_service = MagicMock()
        mock_oauth_service.exchange_code = AsyncMock(return_value=mock_token)

        mock_platform = MagicMock()
        mock_platform.display_name = "Test Platform"
        mock_platform.oauth = MagicMock()  # Explicitly set OAuth config

        with (
            patch("app.routers.oauth.get_settings") as mock_settings,
            patch("app.routers.oauth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.oauth.OAuthService", return_value=mock_oauth_service),
            patch("app.routers.oauth.get_platform", return_value=mock_platform),
            patch("app.routers.oauth.audit_log"),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"
            mock_settings.return_value.oauth_redirect_uri = "http://localhost:8000/oauth/callback"
            mock_settings.return_value.session_max_age = 3600
            mock_settings.return_value.session_cookie_secure = False

            response = client.get("/oauth/callback?code=test-code&state=test-state")

        assert response.status_code == 200
        assert "Authentication Successful" in response.text
        mock_token_manager.store_token.assert_called_once()
        mock_token_manager.clear_pending_auth.assert_called_once()

    def test_callback_token_exchange_failure(self, client):
        """Should return error when token exchange fails."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_pending_auth_by_state = AsyncMock(
            return_value={
                "session_id": "test-session",
                "platform_id": "test-payer",
                "state": "test-state",
                "pkce_verifier": "test-verifier",
            }
        )

        mock_oauth_service = MagicMock()
        mock_oauth_service.exchange_code = AsyncMock(side_effect=Exception("Exchange failed"))

        mock_platform = MagicMock()
        mock_platform.oauth = MagicMock()

        with (
            patch("app.routers.oauth.get_settings") as mock_settings,
            patch("app.routers.oauth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.oauth.get_platform", return_value=mock_platform),
            patch("app.routers.oauth.OAuthService", return_value=mock_oauth_service),
            patch("app.routers.oauth.audit_log"),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"
            mock_settings.return_value.oauth_redirect_uri = "http://localhost:8000/oauth/callback"

            response = client.get("/oauth/callback?code=test-code&state=test-state")

        assert response.status_code == 500
        assert "Token Exchange Failed" in response.text


class TestGetAuthStatus:
    """Tests for GET /auth/status."""

    def test_get_auth_status(self, client):
        """Should return auth status for all platforms."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_auth_status = AsyncMock(
            return_value={
                "aetna": {"authenticated": True, "has_token": True, "expires_at": 1234567890},
                "cigna": {"authenticated": False, "has_token": False},
            }
        )

        with (
            patch("app.routers.auth.get_settings") as mock_settings,
            patch("app.routers.auth.get_token_manager", return_value=mock_token_manager),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"

            response = client.get("/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert "platforms" in data
        assert "aetna" in data["platforms"]
        assert data["platforms"]["aetna"]["authenticated"] is True


class TestLogout:
    """Tests for POST /auth/{platform_id}/logout."""

    def test_logout_success(self, client):
        """Should logout and revoke token successfully."""
        mock_token = MagicMock()
        mock_token.access_token = "test-access-token"
        mock_token.refresh_token = "test-refresh-token"

        mock_token_manager = AsyncMock()
        mock_token_manager.get_token = AsyncMock(return_value=mock_token)
        mock_token_manager.delete_token = AsyncMock()

        mock_oauth_service = MagicMock()
        mock_oauth_service.revoke_token = AsyncMock(return_value=True)

        with (
            patch("app.routers.auth.get_settings") as mock_settings,
            patch("app.routers.auth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.auth.OAuthService", return_value=mock_oauth_service),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"
            mock_settings.return_value.oauth_redirect_uri = "http://localhost:8000/auth/callback"

            response = client.post("/auth/test-payer/logout")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_token_manager.delete_token.assert_called_once()

    def test_logout_no_token(self, client):
        """Should succeed even when no token exists."""
        mock_token_manager = AsyncMock()
        mock_token_manager.get_token = AsyncMock(return_value=None)
        mock_token_manager.delete_token = AsyncMock()

        with (
            patch("app.routers.auth.get_settings") as mock_settings,
            patch("app.routers.auth.get_token_manager", return_value=mock_token_manager),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"

            response = client.post("/auth/test-payer/logout")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_logout_revocation_failure(self, client):
        """Should still succeed when revocation fails."""
        mock_token = MagicMock()
        mock_token.access_token = "test-access-token"
        mock_token.refresh_token = None

        mock_token_manager = AsyncMock()
        mock_token_manager.get_token = AsyncMock(return_value=mock_token)
        mock_token_manager.delete_token = AsyncMock()

        mock_oauth_service = MagicMock()
        mock_oauth_service.revoke_token = AsyncMock(side_effect=Exception("Revoke failed"))

        with (
            patch("app.routers.auth.get_settings") as mock_settings,
            patch("app.routers.auth.get_token_manager", return_value=mock_token_manager),
            patch("app.routers.auth.OAuthService", return_value=mock_oauth_service),
            patch("app.routers.auth.audit_log"),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"
            mock_settings.return_value.oauth_redirect_uri = "http://localhost:8000/auth/callback"

            response = client.post("/auth/test-payer/logout")

        # Should still succeed
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestWaitForAuth:
    """Tests for GET /auth/{platform_id}/wait."""

    def test_wait_for_auth_success(self, client):
        """Should return success when auth completes."""
        mock_token = MagicMock()
        mock_token.seconds_until_expiry = MagicMock(return_value=3600)

        mock_token_manager = AsyncMock()
        mock_token_manager.wait_for_auth_complete = AsyncMock(return_value=mock_token)

        with (
            patch("app.routers.auth.get_settings") as mock_settings,
            patch("app.routers.auth.get_token_manager", return_value=mock_token_manager),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"

            response = client.get("/auth/test-payer/wait")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["expires_in"] == 3600

    def test_wait_for_auth_timeout(self, client):
        """Should return failure on timeout."""
        mock_token_manager = AsyncMock()
        mock_token_manager.wait_for_auth_complete = AsyncMock(return_value=None)

        with (
            patch("app.routers.auth.get_settings") as mock_settings,
            patch("app.routers.auth.get_token_manager", return_value=mock_token_manager),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"

            response = client.get("/auth/test-payer/wait?timeout=60")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_wait_for_auth_custom_timeout(self, client):
        """Should use custom timeout value."""
        mock_token_manager = AsyncMock()
        mock_token_manager.wait_for_auth_complete = AsyncMock(return_value=None)

        with (
            patch("app.routers.auth.get_settings") as mock_settings,
            patch("app.routers.auth.get_token_manager", return_value=mock_token_manager),
        ):
            mock_settings.return_value.session_cookie_name = "fhir_session"

            client.get("/auth/test-payer/wait?timeout=120")

        mock_token_manager.wait_for_auth_complete.assert_called_once()
        call_args = mock_token_manager.wait_for_auth_complete.call_args[0]
        assert call_args[2] == 120.0  # timeout argument
