"""
End-to-end tests against the SMART Health IT sandbox.

These tests make real HTTP requests to the sandbox FHIR server.
They verify the gateway correctly proxies requests and transforms responses.

Run with: pytest tests/e2e -v
Skip in CI: pytest --ignore=tests/e2e
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Mark all tests in this module as e2e
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.network,  # Requires network access
]


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sandbox_platform():
    """The sandbox platform ID to test against."""
    return "smarthealthit-sandbox"


class TestFHIRMetadata:
    """E2E tests for FHIR metadata/CapabilityStatement."""

    def test_fetch_capability_statement(self, client, sandbox_platform):
        """Should fetch CapabilityStatement from sandbox server."""
        response = client.get(f"/api/fhir/{sandbox_platform}/metadata")

        if response.status_code == 503:
            pytest.skip("Sandbox server unavailable")

        assert response.status_code == 200
        data = response.json()

        # Verify it's a CapabilityStatement
        assert data["resourceType"] == "CapabilityStatement"
        assert data["status"] in ["active", "draft"]
        assert "fhirVersion" in data

    def test_capability_statement_has_rest(self, client, sandbox_platform):
        """Should include REST capabilities."""
        response = client.get(f"/api/fhir/{sandbox_platform}/metadata")

        if response.status_code == 503:
            pytest.skip("Sandbox server unavailable")

        data = response.json()
        assert "rest" in data
        assert len(data["rest"]) > 0

        rest = data["rest"][0]
        assert rest["mode"] == "server"
        assert "resource" in rest

    def test_capability_statement_resource_filter(self, client, sandbox_platform):
        """Should filter capabilities by resource type."""
        response = client.get(
            f"/api/fhir/{sandbox_platform}/metadata?resource_type=Patient"
        )

        if response.status_code == 503:
            pytest.skip("Sandbox server unavailable")

        data = response.json()
        assert data["resourceType"] == "CapabilityStatement"

        # Should have filtered resource info
        if "resource" in data:
            assert data["resource"]["type"] == "Patient"


class TestFHIRSearch:
    """E2E tests for FHIR search operations."""

    def test_search_patients(self, client, sandbox_platform):
        """Should search for patients."""
        response = client.get(f"/api/fhir/{sandbox_platform}/Patient?_count=5")

        if response.status_code == 503:
            pytest.skip("Sandbox server unavailable")

        assert response.status_code == 200
        data = response.json()

        assert data["resourceType"] == "Bundle"
        assert data["type"] == "searchset"
        assert "total" in data or "entry" in data

    def test_search_patients_by_name(self, client, sandbox_platform):
        """Should search patients by name."""
        response = client.get(
            f"/api/fhir/{sandbox_platform}/Patient?family=Smith&_count=5"
        )

        if response.status_code == 503:
            pytest.skip("Sandbox server unavailable")

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Bundle"

    def test_search_observations(self, client, sandbox_platform):
        """Should search for observations."""
        response = client.get(f"/api/fhir/{sandbox_platform}/Observation?_count=5")

        if response.status_code == 503:
            pytest.skip("Sandbox server unavailable")

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Bundle"

    def test_search_conditions(self, client, sandbox_platform):
        """Should search for conditions."""
        response = client.get(f"/api/fhir/{sandbox_platform}/Condition?_count=5")

        if response.status_code == 503:
            pytest.skip("Sandbox server unavailable")

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Bundle"

    def test_search_with_multiple_params(self, client, sandbox_platform):
        """Should handle multiple search parameters."""
        response = client.get(
            f"/api/fhir/{sandbox_platform}/Patient?_count=3&_sort=-_lastUpdated"
        )

        if response.status_code == 503:
            pytest.skip("Sandbox server unavailable")

        assert response.status_code == 200


class TestFHIRRead:
    """E2E tests for FHIR read operations."""

    @pytest.fixture
    def sample_patient_id(self, client, sandbox_platform):
        """Get a valid patient ID from search."""
        response = client.get(f"/api/fhir/{sandbox_platform}/Patient?_count=1")

        if response.status_code == 503:
            pytest.skip("Sandbox server unavailable")

        data = response.json()
        if not data.get("entry"):
            pytest.skip("No patients available in sandbox")

        return data["entry"][0]["resource"]["id"]

    def test_read_patient(self, client, sandbox_platform, sample_patient_id):
        """Should read a specific patient resource."""
        response = client.get(
            f"/api/fhir/{sandbox_platform}/Patient/{sample_patient_id}"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["resourceType"] == "Patient"
        assert data["id"] == sample_patient_id

    def test_read_nonexistent_resource(self, client, sandbox_platform):
        """Should return 404 for nonexistent resource."""
        response = client.get(
            f"/api/fhir/{sandbox_platform}/Patient/nonexistent-id-12345"
        )

        # Should be 404, but some servers may return different codes
        assert response.status_code in [404, 410, 500]


class TestOAuthFlow:
    """E2E tests for OAuth authentication flow."""

    def test_initiate_oauth_flow(self, client, sandbox_platform):
        """Should initiate OAuth flow and return authorization URL."""
        response = client.get(f"/auth/{sandbox_platform}/login?redirect=false")

        assert response.status_code == 200
        data = response.json()

        assert "authorization_url" in data
        assert "state" in data
        assert data["platform_id"] == sandbox_platform

        # Verify URL points to sandbox auth server
        assert "smart" in data["authorization_url"].lower() or "auth" in data["authorization_url"].lower()

    def test_oauth_state_is_unique(self, client, sandbox_platform):
        """Should generate unique state for each OAuth request."""
        response1 = client.get(f"/auth/{sandbox_platform}/login?redirect=false")
        response2 = client.get(f"/auth/{sandbox_platform}/login?redirect=false")

        assert response1.status_code == 200
        assert response2.status_code == 200

        state1 = response1.json()["state"]
        state2 = response2.json()["state"]

        assert state1 != state2

    def test_oauth_with_custom_scopes(self, client, sandbox_platform):
        """Should include custom scopes in authorization URL."""
        scopes = "openid patient/*.read"
        response = client.get(
            f"/auth/{sandbox_platform}/login?redirect=false&scopes={scopes}"
        )

        assert response.status_code == 200
        data = response.json()

        # Scopes should be included in the URL
        auth_url = data["authorization_url"]
        assert "scope" in auth_url


class TestErrorHandling:
    """E2E tests for error handling."""

    def test_invalid_platform_returns_404(self, client):
        """Should return 404 for unknown platform."""
        response = client.get("/api/fhir/nonexistent-platform/Patient")

        assert response.status_code == 404

    def test_invalid_resource_type_returns_400(self, client, sandbox_platform):
        """Should return 400 for invalid resource type."""
        response = client.get(f"/api/fhir/{sandbox_platform}/invalid_resource")

        assert response.status_code == 400
        assert "Invalid resource type" in response.json()["detail"]

    def test_invalid_resource_id_returns_400(self, client, sandbox_platform):
        """Should return 400 for invalid resource ID."""
        response = client.get(f"/api/fhir/{sandbox_platform}/Patient/bad@id!")

        assert response.status_code == 400


class TestResponseHeaders:
    """E2E tests for response headers and metadata."""

    def test_cors_headers_present(self, client, sandbox_platform):
        """Should include CORS headers in responses."""
        response = client.get(
            f"/api/fhir/{sandbox_platform}/metadata",
            headers={"Origin": "http://localhost:3000"},
        )

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers or response.status_code == 503

    def test_security_headers_present(self, client):
        """Should include security headers in responses."""
        response = client.get("/health")

        assert response.status_code == 200
        # Security headers added by middleware
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_response_content_type(self, client, sandbox_platform):
        """Should return JSON content type."""
        response = client.get(f"/api/fhir/{sandbox_platform}/metadata")

        if response.status_code == 200:
            assert "application/json" in response.headers["content-type"]
