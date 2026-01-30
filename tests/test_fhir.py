"""
Tests for FHIR endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_check(client):
    """Test health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "fhir-gateway"
    assert "platforms_registered" in data


def test_list_platforms(client):
    """Test listing all platforms."""
    response = client.get("/api/platforms")
    assert response.status_code == 200
    data = response.json()
    assert "platforms" in data
    assert "total" in data
    assert data["total"] > 0


def test_get_platform_details(client):
    """Test getting details for a specific platform."""
    response = client.get("/api/platforms/smarthealthit-sandbox-patient")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "smarthealthit-sandbox-patient"
    assert data["name"] == "SMART Health IT Sandbox (Patient)"
    assert data["has_oauth"] is True


def test_get_platform_not_found(client):
    """Test 404 for unknown platform."""
    response = client.get("/api/platforms/nonexistent-platform")
    assert response.status_code == 404


def test_fhir_search_requires_valid_resource_type(client):
    """Test that invalid resource types are rejected."""
    response = client.get("/api/fhir/smarthealthit-sandbox-patient/invalid_type")
    assert response.status_code == 400
    assert "Invalid resource type" in response.json()["detail"]


def test_fhir_metadata_endpoint(client):
    """Test fetching metadata (CapabilityStatement)."""
    response = client.get("/api/fhir/smarthealthit-sandbox-patient/metadata")
    # This may fail without network access, but should not return server error
    assert response.status_code in [200, 503]


def test_fhir_search_patient(client):
    """Test searching for patients."""
    response = client.get("/api/fhir/smarthealthit-sandbox-patient/Patient?family=Smith")
    # This may fail without network access, but should not return server error
    assert response.status_code in [200, 503]


def test_auth_login_requires_oauth_platform(client):
    """Test that login fails for platforms without OAuth."""
    # Use a platform that might not have OAuth configured
    response = client.get("/api/platforms/hapi-fhir")
    if response.status_code == 200:
        data = response.json()
        if not data.get("has_oauth"):
            response = client.get("/auth/hapi-fhir/login?redirect=false")
            assert response.status_code == 400


def test_auth_login_sandbox(client):
    """Test OAuth login initiation for sandbox."""
    response = client.get("/auth/smarthealthit-sandbox-patient/login?redirect=false")
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "state" in data
    assert data["platform_id"] == "smarthealthit-sandbox-patient"


def test_auth_status_empty_session(client):
    """Test auth status returns empty for new session."""
    response = client.get("/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert "platforms" in data


def test_validation_resource_type():
    """Test resource type validation."""
    from app.validation import ValidationError, validate_resource_type

    # Valid types
    assert validate_resource_type("Patient") == "Patient"
    assert validate_resource_type("Observation") == "Observation"
    assert validate_resource_type("MedicationRequest") == "MedicationRequest"

    # Invalid types
    with pytest.raises(ValidationError):
        validate_resource_type("patient")  # lowercase
    with pytest.raises(ValidationError):
        validate_resource_type("123Patient")  # starts with number
    with pytest.raises(ValidationError):
        validate_resource_type("Patient_v2")  # contains underscore


def test_validation_resource_id():
    """Test resource ID validation."""
    from app.validation import ValidationError, validate_resource_id

    # Valid IDs
    assert validate_resource_id("123") == "123"
    assert validate_resource_id("abc-def") == "abc-def"
    assert validate_resource_id("id.with.dots") == "id.with.dots"

    # Invalid IDs
    with pytest.raises(ValidationError):
        validate_resource_id("")  # empty
    with pytest.raises(ValidationError):
        validate_resource_id("a" * 65)  # too long


def test_audit_logging():
    """Test audit logging functionality."""
    from app.audit import AuditEvent, audit_log

    # Should not raise
    audit_log(
        AuditEvent.RESOURCE_READ,
        platform_id="test-platform",
        resource_type="Patient",
        resource_id="123",
    )

    audit_log(
        AuditEvent.AUTH_FAILURE,
        platform_id="test-platform",
        success=False,
        error="Test error",
    )


def test_pkce_generation():
    """Test PKCE challenge generation."""
    from app.services.oauth import create_pkce_pair

    pkce = create_pkce_pair()
    assert len(pkce.code_verifier) == 64
    assert pkce.code_challenge_method == "S256"
    assert len(pkce.code_challenge) > 0

    # Different calls should produce different values
    pkce2 = create_pkce_pair()
    assert pkce.code_verifier != pkce2.code_verifier


@pytest.mark.asyncio
async def test_in_memory_token_storage():
    """Test in-memory token storage backend."""
    from app.auth.secure_token_store import InMemoryTokenStorage

    storage = InMemoryTokenStorage()

    # Set and get
    await storage.set("key1", "value1")
    assert await storage.get("key1") == "value1"

    # Exists
    assert await storage.exists("key1") is True
    assert await storage.exists("nonexistent") is False

    # Keys pattern
    await storage.set("prefix:a", "va")
    await storage.set("prefix:b", "vb")
    keys = await storage.keys("prefix:*")
    assert len(keys) == 2

    # Delete
    await storage.delete("key1")
    assert await storage.exists("key1") is False


@pytest.mark.asyncio
async def test_secure_session():
    """Test SecureSession functionality."""
    from app.auth.secure_token_store import SecureSession

    session = SecureSession(session_id="test-123")

    # Verification
    assert session.verify() is True

    # Not expired immediately
    assert session.is_expired(ttl=3600) is False

    # Serialization
    data = session.to_dict()
    restored = SecureSession.from_dict(data)
    assert restored.session_id == session.session_id
    assert restored.verify() is True


def test_mcp_server_creation():
    """Test MCP server is configured correctly."""
    from app.mcp.server import mcp

    assert mcp.name == "fhir-gateway"
