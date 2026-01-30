"""
Contract tests for API response structure validation.

These tests verify that the gateway's API responses follow the expected contracts.

Run with: pytest tests/contract -v
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Mark all tests in this module as contract tests
pytestmark = pytest.mark.contract


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthResponseContract:
    """Contract tests for /health endpoint."""

    def test_health_response_structure(self, client):
        """Health response should have expected structure."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()

        # Required fields
        assert "status" in data
        assert "service" in data
        assert "version" in data

        # Type checks
        assert isinstance(data["status"], str)
        assert isinstance(data["service"], str)
        assert isinstance(data["version"], str)

        # Value checks
        assert data["status"] in ["healthy", "unhealthy", "degraded"]
        assert data["service"] == "fhir-gateway"


class TestPlatformListResponseContract:
    """Contract tests for /api/platforms endpoint."""

    def test_platform_list_structure(self, client):
        """Platform list should have expected structure."""
        response = client.get("/api/platforms")
        assert response.status_code == 200

        data = response.json()

        # Required fields
        assert "platforms" in data
        assert "total" in data

        # Type checks
        assert isinstance(data["platforms"], list)
        assert isinstance(data["total"], int)
        assert data["total"] >= 0
        assert data["total"] == len(data["platforms"])

    def test_platform_item_structure(self, client):
        """Each platform should have expected fields."""
        response = client.get("/api/platforms")
        data = response.json()

        for platform in data["platforms"]:
            # Required fields
            assert "id" in platform
            assert isinstance(platform["id"], str)

            # Optional but expected fields
            if "name" in platform:
                assert isinstance(platform["name"], str)
            if "has_fhir" in platform:
                assert isinstance(platform["has_fhir"], bool)
            if "has_oauth" in platform:
                assert isinstance(platform["has_oauth"], bool)


class TestPlatformDetailResponseContract:
    """Contract tests for /api/platforms/{id} endpoint."""

    def test_platform_detail_structure(self, client):
        """Platform detail should have expected structure."""
        # First get a valid platform ID
        list_response = client.get("/api/platforms")
        platforms = list_response.json()["platforms"]
        if not platforms:
            pytest.skip("No platforms available")

        platform_id = platforms[0]["id"]

        response = client.get(f"/api/platforms/{platform_id}")
        assert response.status_code == 200

        data = response.json()

        # Required fields
        assert "id" in data
        assert "name" in data
        assert isinstance(data["id"], str)
        assert isinstance(data["name"], str)

    def test_platform_not_found_structure(self, client):
        """404 response should have expected structure."""
        response = client.get("/api/platforms/nonexistent-platform-id")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)


class TestAuthLoginResponseContract:
    """Contract tests for /auth/{platform_id}/login endpoint."""

    def test_login_response_structure(self, client):
        """Login response should have expected structure."""
        # Use the sandbox platform which is known to have working OAuth
        oauth_platform = "smarthealthit-sandbox-patient"

        response = client.get(f"/auth/{oauth_platform}/login?redirect=false")

        if response.status_code == 500:
            # OAuth not configured for this platform
            pytest.skip("Sandbox OAuth not configured")

        assert response.status_code == 200

        data = response.json()

        # Required fields
        assert "authorization_url" in data
        assert "state" in data
        assert "platform_id" in data

        # Type checks
        assert isinstance(data["authorization_url"], str)
        assert isinstance(data["state"], str)
        assert isinstance(data["platform_id"], str)

        # Value checks
        assert data["authorization_url"].startswith("http")
        assert len(data["state"]) > 0
        assert data["platform_id"] == oauth_platform


class TestAuthStatusResponseContract:
    """Contract tests for /auth/status endpoint."""

    def test_auth_status_structure(self, client):
        """Auth status should have expected structure."""
        response = client.get("/auth/status")
        assert response.status_code == 200

        data = response.json()

        # Required fields
        assert "platforms" in data
        assert isinstance(data["platforms"], dict)

        # Each platform status should have expected fields
        for platform_id, status in data["platforms"].items():
            assert isinstance(platform_id, str)
            assert isinstance(status, dict)

            if "authenticated" in status:
                assert isinstance(status["authenticated"], bool)
            if "has_token" in status:
                assert isinstance(status["has_token"], bool)


class TestFHIRSearchResponseContract:
    """Contract tests for FHIR search response structure."""

    def test_search_response_is_bundle(self, client):
        """Search response should be a Bundle."""
        # Use sandbox platform
        response = client.get("/api/fhir/smarthealthit-sandbox-patient/Patient?_count=1")

        if response.status_code == 503:
            pytest.skip("FHIR server unavailable")

        assert response.status_code == 200
        data = response.json()

        # Must be a Bundle
        assert data["resourceType"] == "Bundle"
        assert data["type"] == "searchset"

    def test_search_error_response(self, client):
        """Search error should have expected structure."""
        response = client.get("/api/fhir/smarthealthit-sandbox-patient/invalid_type")

        assert response.status_code == 400
        data = response.json()

        assert "detail" in data
        assert isinstance(data["detail"], str)


class TestErrorResponseContract:
    """Contract tests for error response structure."""

    def test_400_error_structure(self, client):
        """400 errors should have detail field."""
        response = client.get("/api/fhir/test-platform/invalid_type")
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    def test_404_error_structure(self, client):
        """404 errors should have detail field."""
        response = client.get("/api/platforms/nonexistent")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    def test_validation_error_structure(self, client):
        """Validation errors should have detail field."""
        # POST with invalid body
        response = client.post(
            "/api/coverage/test-platform/requirements",
            json={"invalid": "body"},
        )

        assert response.status_code == 422
        data = response.json()

        # FastAPI validation errors have 'detail' as array
        assert "detail" in data
