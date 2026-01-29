"""
Tests for OAuth 2.0 service.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.oauth import (
    OAuthService,
    PKCEChallenge,
    create_pkce_pair,
    discover_oauth_endpoints,
    fetch_smart_configuration,
)


class TestPKCEChallenge:
    """Tests for PKCEChallenge dataclass."""

    def test_creation(self):
        """Should create PKCE challenge."""
        challenge = PKCEChallenge(
            code_verifier="test-verifier",
            code_challenge="test-challenge",
        )

        assert challenge.code_verifier == "test-verifier"
        assert challenge.code_challenge == "test-challenge"
        assert challenge.code_challenge_method == "S256"


class TestCreatePKCEPair:
    """Tests for create_pkce_pair function."""

    def test_generates_verifier_and_challenge(self):
        """Should generate verifier and challenge."""
        challenge = create_pkce_pair()

        assert challenge.code_verifier is not None
        assert challenge.code_challenge is not None
        assert challenge.code_challenge_method == "S256"

    def test_verifier_length(self):
        """Should generate verifier of specified length."""
        challenge = create_pkce_pair(verifier_length=48)

        assert len(challenge.code_verifier) == 48

    def test_challenge_is_different_from_verifier(self):
        """Challenge should be derived but different from verifier."""
        challenge = create_pkce_pair()

        assert challenge.code_challenge != challenge.code_verifier

    def test_unique_challenges(self):
        """Should generate unique challenges each time."""
        challenge1 = create_pkce_pair()
        challenge2 = create_pkce_pair()

        assert challenge1.code_verifier != challenge2.code_verifier
        assert challenge1.code_challenge != challenge2.code_challenge

    def test_verifier_length_too_short(self):
        """Should reject verifier length below minimum."""
        with pytest.raises(ValueError, match="Verifier length must be"):
            create_pkce_pair(verifier_length=42)

    def test_verifier_length_too_long(self):
        """Should reject verifier length above maximum."""
        with pytest.raises(ValueError, match="Verifier length must be"):
            create_pkce_pair(verifier_length=129)

    def test_minimum_length_accepted(self):
        """Should accept minimum verifier length."""
        challenge = create_pkce_pair(verifier_length=43)
        assert len(challenge.code_verifier) == 43

    def test_maximum_length_accepted(self):
        """Should accept maximum verifier length."""
        challenge = create_pkce_pair(verifier_length=128)
        assert len(challenge.code_verifier) == 128


class TestFetchSmartConfiguration:
    """Tests for fetch_smart_configuration function."""

    @pytest.mark.asyncio
    async def test_returns_config_on_success(self):
        """Should return SMART configuration on success."""
        mock_config = {
            "authorization_endpoint": "https://auth.example.com/authorize",
            "token_endpoint": "https://auth.example.com/token",
            "capabilities": ["launch-ehr"],
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_config)

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()

            mock_get = MagicMock()
            mock_get.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get.__aexit__ = AsyncMock()
            mock_session.get = MagicMock(return_value=mock_get)

            mock_session_cls.return_value = mock_session

            result = await fetch_smart_configuration("https://fhir.example.com")

            assert result is not None
            assert result["authorization_endpoint"] == "https://auth.example.com/authorize"

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self):
        """Should return None if endpoint not found."""
        mock_response = AsyncMock()
        mock_response.status = 404

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()

            mock_get = MagicMock()
            mock_get.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get.__aexit__ = AsyncMock()
            mock_session.get = MagicMock(return_value=mock_get)

            mock_session_cls.return_value = mock_session

            result = await fetch_smart_configuration("https://fhir.example.com")

            assert result is None


class TestDiscoverOAuthEndpoints:
    """Tests for discover_oauth_endpoints function."""

    @pytest.mark.asyncio
    async def test_returns_endpoints_from_smart_config(self):
        """Should extract endpoints from SMART configuration."""
        mock_config = {
            "authorization_endpoint": "https://auth.example.com/authorize",
            "token_endpoint": "https://auth.example.com/token",
            "revocation_endpoint": "https://auth.example.com/revoke",
            "capabilities": ["launch-ehr", "sso-openid-connect"],
            "scopes_supported": ["openid", "fhirUser"],
        }

        with patch(
            "app.services.oauth.fetch_smart_configuration",
            AsyncMock(return_value=mock_config),
        ):
            result = await discover_oauth_endpoints("https://fhir.example.com")

            assert result["authorize_url"] == "https://auth.example.com/authorize"
            assert result["token_url"] == "https://auth.example.com/token"
            assert result["revoke_url"] == "https://auth.example.com/revoke"
            assert "launch-ehr" in result["capabilities"]

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_config(self):
        """Should return empty dict if no SMART config available."""
        with patch(
            "app.services.oauth.fetch_smart_configuration",
            AsyncMock(return_value=None),
        ):
            result = await discover_oauth_endpoints("https://fhir.example.com")

            assert result == {}


class TestOAuthService:
    """Tests for OAuthService class."""

    @pytest.fixture
    def mock_platform(self):
        """Create mock platform config."""
        platform = MagicMock()
        platform.id = "test-platform"
        platform.fhir_base_url = "https://fhir.test.com"
        platform.oauth = MagicMock()
        platform.oauth.authorize_url = "https://auth.test.com/authorize"
        platform.oauth.token_url = "https://auth.test.com/token"
        platform.oauth.client_id = "test-client"
        platform.oauth.client_secret = "test-secret"
        platform.oauth.scopes = ["openid", "fhirUser"]
        return platform

    def test_init_success(self, mock_platform):
        """Should initialize with valid platform."""
        with patch(
            "app.services.oauth.get_platform",
            return_value=mock_platform,
        ):
            service = OAuthService(
                platform_id="test-platform",
                redirect_uri="http://localhost:8000/callback",
            )

            assert service.platform_id == "test-platform"
            assert service.client_id == "test-client"
            assert service.redirect_uri == "http://localhost:8000/callback"

    def test_init_platform_not_found(self):
        """Should raise error if platform not found."""
        with patch(
            "app.services.oauth.get_platform",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="not found"):
                OAuthService(
                    platform_id="unknown-platform",
                    redirect_uri="http://localhost:8000/callback",
                )

    def test_init_no_oauth_config(self, mock_platform):
        """Should raise error if platform has no OAuth config."""
        mock_platform.oauth = None

        with patch(
            "app.services.oauth.get_platform",
            return_value=mock_platform,
        ):
            with pytest.raises(ValueError, match="no OAuth configuration"):
                OAuthService(
                    platform_id="test-platform",
                    redirect_uri="http://localhost:8000/callback",
                )

    def test_build_authorization_url(self, mock_platform):
        """Should build authorization URL with PKCE."""
        with patch(
            "app.services.oauth.get_platform",
            return_value=mock_platform,
        ):
            service = OAuthService(
                platform_id="test-platform",
                redirect_uri="http://localhost:8000/callback",
            )

            url, state, pkce = service.build_authorization_url()

            assert url.startswith("https://auth.test.com/authorize")
            assert "client_id=test-client" in url
            assert "response_type=code" in url
            assert "code_challenge=" in url
            assert "code_challenge_method=S256" in url
            assert state is not None
            assert pkce is not None

    def test_build_authorization_url_custom_scopes(self, mock_platform):
        """Should use custom scopes."""
        with patch(
            "app.services.oauth.get_platform",
            return_value=mock_platform,
        ):
            service = OAuthService(
                platform_id="test-platform",
                redirect_uri="http://localhost:8000/callback",
            )

            url, _, _ = service.build_authorization_url(scopes=["custom.scope"])

            assert "custom.scope" in url

    def test_build_authorization_url_with_aud(self, mock_platform):
        """Should include aud parameter."""
        with patch(
            "app.services.oauth.get_platform",
            return_value=mock_platform,
        ):
            service = OAuthService(
                platform_id="test-platform",
                redirect_uri="http://localhost:8000/callback",
            )

            url, _, _ = service.build_authorization_url(aud="https://custom-fhir.example.com")

            assert "aud=" in url
            assert "custom-fhir.example.com" in url

    def test_build_authorization_url_no_authorize_url(self, mock_platform):
        """Should raise error if authorize_url not configured."""
        mock_platform.oauth.authorize_url = None

        with patch(
            "app.services.oauth.get_platform",
            return_value=mock_platform,
        ):
            service = OAuthService(
                platform_id="test-platform",
                redirect_uri="http://localhost:8000/callback",
            )

            with pytest.raises(ValueError, match="authorize_url not configured"):
                service.build_authorization_url()

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, mock_platform):
        """Should exchange code for tokens."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "access_token": "new-access-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "new-refresh-token",
                "scope": "openid fhirUser",
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        with patch(
            "app.services.oauth.get_platform",
            return_value=mock_platform,
        ):
            with patch("aiohttp.ClientSession", return_value=mock_session):
                service = OAuthService(
                    platform_id="test-platform",
                    redirect_uri="http://localhost:8000/callback",
                )

                # Build auth URL first to set up pending state
                service.build_authorization_url()

                token = await service.exchange_code(
                    code="auth-code",
                    code_verifier="test-verifier",
                )

                assert token.access_token == "new-access-token"
                assert token.refresh_token == "new-refresh-token"

    @pytest.mark.asyncio
    async def test_exchange_code_state_mismatch(self, mock_platform):
        """Should raise error on state mismatch."""
        with patch(
            "app.services.oauth.get_platform",
            return_value=mock_platform,
        ):
            service = OAuthService(
                platform_id="test-platform",
                redirect_uri="http://localhost:8000/callback",
            )

            # Build auth URL to set pending state
            service.build_authorization_url(state="original-state")

            with pytest.raises(ValueError, match="State"):
                await service.exchange_code(
                    code="auth-code",
                    code_verifier="test-verifier",
                    state="wrong-state",
                )

    @pytest.mark.asyncio
    async def test_exchange_code_no_token_url(self, mock_platform):
        """Should raise error if token_url not configured."""
        mock_platform.oauth.token_url = None

        with patch(
            "app.services.oauth.get_platform",
            return_value=mock_platform,
        ):
            service = OAuthService(
                platform_id="test-platform",
                redirect_uri="http://localhost:8000/callback",
            )

            with pytest.raises(ValueError, match="token_url not configured"):
                await service.exchange_code(
                    code="auth-code",
                    code_verifier="test-verifier",
                )

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, mock_platform):
        """Should refresh access token."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "access_token": "refreshed-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        with patch(
            "app.services.oauth.get_platform",
            return_value=mock_platform,
        ):
            with patch("aiohttp.ClientSession", return_value=mock_session):
                service = OAuthService(
                    platform_id="test-platform",
                    redirect_uri="http://localhost:8000/callback",
                )

                token = await service.refresh_token("old-refresh-token")

                assert token.access_token == "refreshed-token"
