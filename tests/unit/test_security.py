"""
Tests for security middleware and hardening features.
"""

import pytest

from app.middleware.security import SecurityHeadersMiddleware


class TestSecurityHeadersMiddleware:
    """Tests for the SecurityHeadersMiddleware."""

    @pytest.mark.asyncio
    async def test_adds_security_headers(self):
        """Should add security headers to HTTP responses."""
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        async def homepage(request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(SecurityHeadersMiddleware)

        client = TestClient(app)
        response = client.get("/")

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_adds_csp_for_html(self):
        """Should add CSP header for HTML responses."""
        from starlette.applications import Starlette
        from starlette.responses import HTMLResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        async def homepage(request):
            return HTMLResponse("<html><body>Test</body></html>")

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(SecurityHeadersMiddleware)

        client = TestClient(app)
        response = client.get("/")

        assert "Content-Security-Policy" in response.headers
        assert response.headers["Content-Security-Policy"] == (
            "default-src 'none'; style-src 'unsafe-inline'"
        )

    @pytest.mark.asyncio
    async def test_no_csp_for_json(self):
        """Should not add CSP header for JSON responses."""
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        async def api(request):
            return JSONResponse({"data": "test"})

        app = Starlette(routes=[Route("/api", api)])
        app.add_middleware(SecurityHeadersMiddleware)

        client = TestClient(app)
        response = client.get("/api")

        # CSP should not be added for JSON responses
        assert "Content-Security-Policy" not in response.headers

    @pytest.mark.asyncio
    async def test_preserves_existing_headers(self):
        """Should preserve existing response headers."""
        from starlette.applications import Starlette
        from starlette.responses import Response
        from starlette.routing import Route
        from starlette.testclient import TestClient

        async def custom_headers(request):
            return Response(
                content="test",
                headers={"X-Custom-Header": "custom-value"},
            )

        app = Starlette(routes=[Route("/", custom_headers)])
        app.add_middleware(SecurityHeadersMiddleware)

        client = TestClient(app)
        response = client.get("/")

        assert response.headers["X-Custom-Header"] == "custom-value"
        assert response.headers["X-Content-Type-Options"] == "nosniff"


class TestSecureTokenStore:
    """Tests for secure token storage."""

    @pytest.mark.asyncio
    async def test_in_memory_store_token(self):
        """Should store and retrieve token from in-memory backend."""
        from app.auth.secure_token_store import InMemoryTokenStorage

        backend = InMemoryTokenStorage()

        await backend.set("session:123:token:aetna", '{"access_token": "test"}', ttl=3600)
        result = await backend.get("session:123:token:aetna")

        assert result == '{"access_token": "test"}'

    @pytest.mark.asyncio
    async def test_in_memory_delete(self):
        """Should delete from in-memory backend."""
        from app.auth.secure_token_store import InMemoryTokenStorage

        backend = InMemoryTokenStorage()

        await backend.set("test-key", "test-value", ttl=3600)
        await backend.delete("test-key")
        result = await backend.get("test-key")

        assert result is None

    @pytest.mark.asyncio
    async def test_in_memory_expiration(self):
        """Should respect TTL expiration."""
        import time

        from app.auth.secure_token_store import InMemoryTokenStorage

        backend = InMemoryTokenStorage()

        # Store with very short TTL
        await backend.set("expiring-key", "value", ttl=1)

        # Manually expire by setting tuple to expired timestamp
        backend._store["expiring-key"] = ("value", time.time() - 1)

        result = await backend.get("expiring-key")

        assert result is None


class TestMasterKeyEncryption:
    """Tests for master key encryption (if implemented)."""

    def test_import_secure_token_store(self):
        """Should be able to import secure token store module."""
        from app.auth.secure_token_store import (
            InMemoryTokenStorage,
            SecureTokenStore,
            TokenStorageBackend,
        )

        assert SecureTokenStore is not None
        assert InMemoryTokenStorage is not None
        assert TokenStorageBackend is not None


class TestRedisTLSEnforcement:
    """Tests for Redis TLS enforcement."""

    def test_redis_storage_init_with_tls(self):
        """Should accept TLS Redis URL."""
        from app.auth.secure_token_store import RedisTokenStorage

        # This should not raise
        storage = RedisTokenStorage(
            redis_url="rediss://localhost:6380",
            require_tls=True,
        )
        assert storage is not None

    def test_redis_storage_init_without_tls_required(self):
        """Should warn but not raise for non-TLS URL when not required."""
        from app.auth.secure_token_store import RedisTokenStorage

        # This should not raise
        storage = RedisTokenStorage(
            redis_url="redis://localhost:6379",
            require_tls=False,
        )
        assert storage is not None


class TestAuthModels:
    """Tests for authentication models."""

    def test_oauth_token_model(self):
        """Should create OAuth token with all fields."""
        from app.models.auth import OAuthToken

        token = OAuthToken(
            access_token="test-access",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="test-refresh",
            scope="openid patient/*.*",
        )

        assert token.access_token == "test-access"
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600
        assert token.refresh_token == "test-refresh"
        assert token.scope == "openid patient/*.*"

    def test_oauth_token_is_expired(self):
        """Should correctly report expired status."""
        import time

        from app.models.auth import OAuthToken

        token = OAuthToken(
            access_token="test",
            token_type="Bearer",
            expires_in=3600,
        )

        # Fresh token should not be expired (considering buffer)
        assert token.has_expired(buffer_seconds=0) is False

        # Create an expired token
        expired_time = time.time() - 4000
        expired_token = OAuthToken(
            access_token="test",
            token_type="Bearer",
            expires_in=3600,
            created_at=expired_time,
            expires_at=expired_time + 3600,  # Still in the past
        )

        assert expired_token.has_expired(buffer_seconds=0) is True

    def test_oauth_token_no_expiry(self):
        """Should handle token without expiry."""
        from app.models.auth import OAuthToken

        token = OAuthToken(
            access_token="test",
            token_type="Bearer",
            expires_in=None,
        )

        # Token without expiry should not be expired
        assert token.is_expired is False
        assert token.seconds_until_expiry() is None


class TestInputValidation:
    """Tests for input validation functions."""

    def test_validate_platform_id_valid(self):
        """Should accept valid platform IDs that exist in config."""
        from app.validation import validate_platform_id

        # Use actual configured platforms
        validate_platform_id("medicare")
        validate_platform_id("aetna")

    def test_validate_platform_id_invalid(self):
        """Should reject invalid platform IDs."""
        from app.validation import validate_platform_id

        with pytest.raises(ValueError):
            validate_platform_id("invalid..platform")

        with pytest.raises(ValueError):
            validate_platform_id("platform/injection")

        with pytest.raises(ValueError):
            validate_platform_id("")

    def test_validate_resource_type_valid(self):
        """Should accept valid resource types."""
        from app.validation import validate_resource_type

        validate_resource_type("Patient")
        validate_resource_type("Coverage")
        validate_resource_type("Questionnaire")

    def test_validate_resource_type_invalid(self):
        """Should reject invalid resource types."""
        from app.validation import validate_resource_type

        with pytest.raises(ValueError):
            validate_resource_type("invalid-type")

        with pytest.raises(ValueError):
            validate_resource_type("../Patient")

        with pytest.raises(ValueError):
            validate_resource_type("")

    def test_validate_procedure_code_valid(self):
        """Should accept valid procedure codes."""
        from app.validation import validate_procedure_code

        validate_procedure_code("27447")  # CPT
        validate_procedure_code("99213")
        validate_procedure_code("J0129")  # HCPCS

    def test_validate_procedure_code_invalid(self):
        """Should reject invalid procedure codes."""
        from app.validation import validate_procedure_code

        with pytest.raises(ValueError):
            validate_procedure_code("invalid;injection")

        with pytest.raises(ValueError):
            validate_procedure_code("")
