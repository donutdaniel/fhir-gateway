"""
OAuth 2.0 service for FHIR Gateway.

Provides OAuth 2.0 authentication including:
- Authorization Code flow with PKCE
- Token exchange
- Token refresh
- Endpoint discovery from FHIR metadata
"""

import hashlib
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import aiohttp

from app.config.logging import get_logger
from app.config.platform import get_platform
from app.models.auth import OAuthToken

logger = get_logger(__name__)

# RFC 7636 PKCE constants
_PKCE_VERIFIER_MIN_LENGTH = 43
_PKCE_VERIFIER_MAX_LENGTH = 128
_PKCE_UNRESERVED_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


@dataclass
class PKCEChallenge:
    """PKCE code verifier and challenge pair."""

    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"


def _generate_verifier_bytes(length: int) -> bytes:
    """Generate cryptographically secure random bytes for PKCE verifier."""
    raw_bytes = os.urandom(length * 2)
    return raw_bytes


def _bytes_to_pkce_verifier(raw_bytes: bytes, target_length: int) -> str:
    """Convert random bytes to a PKCE-compliant code verifier string."""
    charset = _PKCE_UNRESERVED_CHARS
    charset_len = len(charset)

    verifier_chars = []
    for byte_val in raw_bytes:
        if len(verifier_chars) >= target_length:
            break
        verifier_chars.append(charset[byte_val % charset_len])

    return "".join(verifier_chars)


def _compute_s256_challenge(verifier: str) -> str:
    """Compute S256 code challenge from verifier per RFC 7636."""
    import base64

    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=")
    return encoded.decode("ascii")


def create_pkce_pair(verifier_length: int = 64) -> PKCEChallenge:
    """
    Create a PKCE code verifier and challenge pair.

    Args:
        verifier_length: Length of code verifier (43-128 per RFC 7636)

    Returns:
        PKCEChallenge containing verifier and S256 challenge

    Raises:
        ValueError: If verifier_length is outside valid range
    """
    if not (_PKCE_VERIFIER_MIN_LENGTH <= verifier_length <= _PKCE_VERIFIER_MAX_LENGTH):
        raise ValueError(
            f"Verifier length must be {_PKCE_VERIFIER_MIN_LENGTH}-{_PKCE_VERIFIER_MAX_LENGTH}, "
            f"got {verifier_length}"
        )

    raw_bytes = _generate_verifier_bytes(verifier_length)
    verifier = _bytes_to_pkce_verifier(raw_bytes, verifier_length)
    challenge = _compute_s256_challenge(verifier)

    return PKCEChallenge(
        code_verifier=verifier,
        code_challenge=challenge,
        code_challenge_method="S256",
    )


async def fetch_smart_configuration(
    fhir_base_url: str, timeout: float = 10.0
) -> dict[str, Any] | None:
    """
    Fetch SMART on FHIR configuration from well-known endpoint.

    Args:
        fhir_base_url: Base URL of the FHIR server
        timeout: Request timeout in seconds

    Returns:
        SMART configuration dict or None if not available
    """
    url = f"{fhir_base_url.rstrip('/')}/.well-known/smart-configuration"
    client_timeout = aiohttp.ClientTimeout(total=timeout)

    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(url, headers={"Accept": "application/json"}) as resp:
                if resp.status == 200:
                    try:
                        return await resp.json()
                    except (ValueError, aiohttp.ContentTypeError) as e:
                        logger.debug("Invalid JSON in SMART configuration", url=url, error=str(e))
                        return None
    except aiohttp.ClientError as e:
        logger.debug("SMART configuration not available", url=url, error=str(e))
    except Exception as e:
        logger.debug("Error fetching SMART configuration", error=str(e))

    return None


async def discover_oauth_endpoints(
    fhir_base_url: str,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """
    Discover OAuth endpoints from a FHIR server.

    Tries SMART configuration first, then falls back to CapabilityStatement.

    Args:
        fhir_base_url: Base URL of the FHIR server
        timeout: Request timeout in seconds

    Returns:
        Dictionary with discovered endpoints (authorize_url, token_url, etc.)
    """
    smart_config = await fetch_smart_configuration(fhir_base_url, timeout)

    if smart_config:
        endpoints = {
            "authorize_url": smart_config.get("authorization_endpoint", ""),
            "token_url": smart_config.get("token_endpoint", ""),
            "revoke_url": smart_config.get("revocation_endpoint", ""),
            "introspection_url": smart_config.get("introspection_endpoint", ""),
            "capabilities": smart_config.get("capabilities", []),
            "scopes_supported": smart_config.get("scopes_supported", []),
        }

        logger.info(
            "Discovered OAuth endpoints from SMART configuration",
            authorize_url=endpoints.get("authorize_url"),
            token_url=endpoints.get("token_url"),
        )
        return endpoints

    logger.warning("No OAuth endpoints discovered", fhir_base_url=fhir_base_url)
    return {}


class OAuthService:
    """
    OAuth 2.0 service for a specific platform.

    Handles authorization URL building, code exchange, and token refresh.
    """

    def __init__(
        self,
        platform_id: str,
        redirect_uri: str,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        """
        Initialize OAuth service for a platform.

        Args:
            platform_id: The platform identifier
            redirect_uri: OAuth callback URL
            client_id: Optional client ID override
            client_secret: Optional client secret override
        """
        self.platform_id = platform_id
        self.redirect_uri = redirect_uri

        platform = get_platform(platform_id)
        if not platform:
            raise ValueError(f"Platform '{platform_id}' not found")

        if not platform.oauth:
            raise ValueError(f"Platform '{platform_id}' has no OAuth configuration")

        self.platform = platform
        self.oauth_config = platform.oauth
        self.client_id = client_id or self.oauth_config.client_id
        self.client_secret = client_secret or self.oauth_config.client_secret

        if not self.client_id:
            raise ValueError(f"No client_id configured for platform '{platform_id}'")

        # Store pending PKCE and state
        self._pending_pkce: PKCEChallenge | None = None
        self._pending_state: str | None = None

    def _generate_state(self) -> str:
        """Generate a cryptographically secure state parameter."""
        return os.urandom(24).hex()

    def build_authorization_url(
        self,
        scopes: list[str] | None = None,
        state: str | None = None,
        aud: str | None = None,
    ) -> tuple[str, str, PKCEChallenge]:
        """
        Build the authorization URL for the auth code flow.

        Args:
            scopes: OAuth scopes (uses config default if not provided)
            state: State parameter for CSRF protection
            aud: FHIR server URL (for SMART launch)

        Returns:
            Tuple of (authorization_url, state, pkce_challenge)
        """
        if not self.oauth_config.authorize_url:
            raise ValueError("authorize_url not configured")

        # Generate state
        self._pending_state = state if state else self._generate_state()

        # Generate PKCE
        self._pending_pkce = create_pkce_pair(64)

        # Build default scopes
        default_scopes = self.oauth_config.scopes or ["openid", "fhirUser", "patient/*.*"]

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes or default_scopes),
            "state": self._pending_state,
            "code_challenge": self._pending_pkce.code_challenge,
            "code_challenge_method": self._pending_pkce.code_challenge_method,
        }

        # Add SMART aud parameter
        if aud:
            params["aud"] = aud
        elif self.platform.fhir_base_url:
            params["aud"] = self.platform.fhir_base_url

        url = f"{self.oauth_config.authorize_url}?{urlencode(params)}"
        return url, self._pending_state, self._pending_pkce

    async def exchange_code(
        self,
        code: str,
        code_verifier: str,
        state: str | None = None,
    ) -> OAuthToken:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from callback
            code_verifier: PKCE code verifier
            state: State parameter to verify (optional)

        Returns:
            OAuthToken with access token and optional refresh token

        Raises:
            ValueError: If state doesn't match or exchange fails
        """
        # Verify state if provided
        if state and self._pending_state and state != self._pending_state:
            raise ValueError("State parameter mismatch")

        if not self.oauth_config.token_url:
            raise ValueError("token_url not configured")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": code_verifier,
        }

        # Add client secret for confidential clients
        if self.client_secret:
            data["client_secret"] = self.client_secret

        client_timeout = aiohttp.ClientTimeout(total=30.0)

        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.post(
                self.oauth_config.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    logger.error(
                        "Token exchange failed",
                        status_code=resp.status,
                        error=error_body,
                    )
                    raise ValueError(f"Token exchange failed: {error_body}")

                try:
                    token_data = await resp.json()
                except (ValueError, aiohttp.ContentTypeError) as e:
                    error_body = await resp.text()
                    logger.error(
                        "Invalid JSON in token response", error=str(e), body=error_body[:200]
                    )
                    raise ValueError("Token endpoint returned invalid JSON response") from e

                logger.info("Authorization code exchange successful", platform_id=self.platform_id)

                # Clear pending state
                self._pending_pkce = None
                self._pending_state = None

                return OAuthToken(
                    access_token=token_data["access_token"],
                    token_type=token_data.get("token_type", "Bearer"),
                    expires_in=token_data.get("expires_in"),
                    refresh_token=token_data.get("refresh_token"),
                    scope=token_data.get("scope"),
                    id_token=token_data.get("id_token"),
                )

    async def refresh_token(self, refresh_token: str) -> OAuthToken:
        """
        Refresh an access token using a refresh token.

        Args:
            refresh_token: The refresh token

        Returns:
            New OAuthToken with fresh access token

        Raises:
            ValueError: If refresh fails
        """
        if not self.oauth_config.token_url:
            raise ValueError("token_url not configured")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }

        if self.client_secret:
            data["client_secret"] = self.client_secret

        client_timeout = aiohttp.ClientTimeout(total=30.0)

        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.post(
                self.oauth_config.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    logger.error("Token refresh failed", status_code=resp.status, error=error_body)
                    raise ValueError(f"Token refresh failed: {error_body}")

                try:
                    token_data = await resp.json()
                except (ValueError, aiohttp.ContentTypeError) as e:
                    error_body = await resp.text()
                    logger.error(
                        "Invalid JSON in refresh response", error=str(e), body=error_body[:200]
                    )
                    raise ValueError("Token endpoint returned invalid JSON response") from e

                logger.info("Token refresh successful", platform_id=self.platform_id)

                return OAuthToken(
                    access_token=token_data["access_token"],
                    token_type=token_data.get("token_type", "Bearer"),
                    expires_in=token_data.get("expires_in"),
                    refresh_token=token_data.get("refresh_token", refresh_token),
                    scope=token_data.get("scope"),
                    id_token=token_data.get("id_token"),
                )

    async def revoke_token(
        self,
        token: str,
        token_type_hint: str = "access_token",
    ) -> bool:
        """
        Revoke a token at the platform's OAuth server.

        Args:
            token: The token to revoke (access or refresh token)
            token_type_hint: Either "access_token" or "refresh_token"

        Returns:
            True if revocation succeeded or endpoint not available,
            False if revocation failed

        Note:
            Per RFC 7009, revocation endpoints should return 200 even if
            the token was already invalid, so we treat any 2xx as success.
        """
        if not self.oauth_config.revoke_url:
            logger.debug(
                "No revocation endpoint configured",
                platform_id=self.platform_id,
            )
            return True  # No endpoint = nothing to revoke

        data = {
            "token": token,
            "token_type_hint": token_type_hint,
            "client_id": self.client_id,
        }

        if self.client_secret:
            data["client_secret"] = self.client_secret

        client_timeout = aiohttp.ClientTimeout(total=10.0)

        try:
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.post(
                    self.oauth_config.revoke_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as resp:
                    if 200 <= resp.status < 300:
                        logger.info(
                            "Token revoked successfully",
                            platform_id=self.platform_id,
                            token_type=token_type_hint,
                        )
                        return True

                    error_body = await resp.text()
                    logger.warning(
                        "Token revocation failed",
                        platform_id=self.platform_id,
                        status_code=resp.status,
                        error=error_body[:200],
                    )
                    return False

        except aiohttp.ClientError as e:
            logger.warning(
                "Token revocation request failed",
                platform_id=self.platform_id,
                error=str(e),
            )
            return False
