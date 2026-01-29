"""
Tests for FHIR router endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fhirpy.base.exceptions import OperationOutcome, ResourceNotFound

from app.routers.fhir import router
from app.errors import PlatformNotConfiguredError, PlatformNotFoundError


@pytest.fixture
def app():
    """Create test FastAPI app with FHIR router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestGetMetadata:
    """Tests for GET /api/fhir/{platform_id}/metadata."""

    @pytest.fixture
    def mock_capability_statement(self):
        """Sample CapabilityStatement."""
        return {
            "resourceType": "CapabilityStatement",
            "status": "active",
            "fhirVersion": "4.0.1",
            "rest": [
                {
                    "mode": "server",
                    "resource": [
                        {"type": "Patient", "interaction": [{"code": "read"}]},
                    ],
                }
            ],
        }

    def test_get_metadata_success(self, client, mock_capability_statement):
        """Should return CapabilityStatement for valid platform."""
        with patch(
            "app.routers.fhir.fetch_capability_statement",
            new_callable=AsyncMock,
            return_value=mock_capability_statement,
        ):
            response = client.get("/api/fhir/aetna/metadata")

        assert response.status_code == 200
        assert response.json()["resourceType"] == "CapabilityStatement"

    def test_get_metadata_with_resource_type(self, client, mock_capability_statement):
        """Should filter by resource type."""
        with patch(
            "app.routers.fhir.fetch_capability_statement",
            new_callable=AsyncMock,
            return_value=mock_capability_statement,
        ):
            response = client.get("/api/fhir/aetna/metadata?resource_type=Patient")

        assert response.status_code == 200

    def test_get_metadata_with_auth_header(self, client, mock_capability_statement):
        """Should pass bearer token to service."""
        with patch(
            "app.routers.fhir.fetch_capability_statement",
            new_callable=AsyncMock,
            return_value=mock_capability_statement,
        ) as mock_fetch:
            response = client.get(
                "/api/fhir/aetna/metadata",
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        mock_fetch.assert_called_once()
        call_kwargs = mock_fetch.call_args.kwargs
        assert call_kwargs["access_token"] == "test-token"

    def test_get_metadata_platform_not_found(self, client):
        """Should return 404 when platform not found."""
        with patch(
            "app.routers.fhir.fetch_capability_statement",
            new_callable=AsyncMock,
            side_effect=PlatformNotFoundError("unknown"),
        ):
            response = client.get("/api/fhir/unknown/metadata")

        assert response.status_code == 404

    def test_get_metadata_platform_not_configured(self, client):
        """Should return 503 when platform not configured."""
        with patch(
            "app.routers.fhir.fetch_capability_statement",
            new_callable=AsyncMock,
            side_effect=PlatformNotConfiguredError("aetna"),
        ):
            response = client.get("/api/fhir/aetna/metadata")

        assert response.status_code == 503


class TestSearchResources:
    """Tests for GET /api/fhir/{platform_id}/{resource_type}."""

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        search = MagicMock()
        search.search = MagicMock(return_value=search)
        search.fetch = AsyncMock(
            return_value=[
                {"resourceType": "Patient", "id": "123"},
                {"resourceType": "Patient", "id": "456"},
            ]
        )
        client.resources = MagicMock(return_value=search)
        return client

    def test_search_resources_success(self, client, mock_fhir_client):
        """Should return search bundle for valid request."""
        with (
            patch("app.routers.fhir.get_fhir_client", return_value=mock_fhir_client),
            patch("app.routers.fhir.audit_log"),
        ):
            response = client.get("/api/fhir/aetna/Patient")

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Bundle"
        assert data["type"] == "searchset"
        assert data["total"] == 2

    def test_search_resources_with_params(self, client, mock_fhir_client):
        """Should pass search params to FHIR client."""
        with (
            patch("app.routers.fhir.get_fhir_client", return_value=mock_fhir_client),
            patch("app.routers.fhir.audit_log"),
        ):
            response = client.get("/api/fhir/aetna/Patient?name=Smith&birthdate=1970-01-01")

        assert response.status_code == 200
        mock_fhir_client.resources().search.assert_called_once_with(
            name="Smith", birthdate="1970-01-01"
        )

    def test_search_resources_invalid_resource_type(self, client):
        """Should return 400 for invalid resource type."""
        response = client.get("/api/fhir/aetna/patient")  # lowercase

        assert response.status_code == 400
        assert "Invalid resource type" in response.json()["detail"]

    def test_search_resources_platform_not_found(self, client):
        """Should return 404 when platform not found."""
        with patch(
            "app.routers.fhir.get_fhir_client",
            side_effect=PlatformNotFoundError("unknown"),
        ):
            response = client.get("/api/fhir/unknown/Patient")

        assert response.status_code == 404

    def test_search_resources_platform_not_configured(self, client):
        """Should return 503 when platform not configured."""
        with patch(
            "app.routers.fhir.get_fhir_client",
            side_effect=PlatformNotConfiguredError("aetna"),
        ):
            response = client.get("/api/fhir/aetna/Patient")

        assert response.status_code == 503


class TestReadResource:
    """Tests for GET /api/fhir/{platform_id}/{resource_type}/{resource_id}."""

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        client.get = AsyncMock(
            return_value={"resourceType": "Patient", "id": "123", "name": [{"family": "Smith"}]}
        )
        return client

    def test_read_resource_success(self, client, mock_fhir_client):
        """Should return resource for valid request."""
        with (
            patch("app.routers.fhir.get_fhir_client", return_value=mock_fhir_client),
            patch("app.routers.fhir.audit_log"),
        ):
            response = client.get("/api/fhir/aetna/Patient/123")

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Patient"
        assert data["id"] == "123"

    def test_read_resource_invalid_resource_type(self, client):
        """Should return 400 for invalid resource type."""
        response = client.get("/api/fhir/aetna/invalid_type/123")

        assert response.status_code == 400

    def test_read_resource_invalid_resource_id(self, client):
        """Should return 400 for invalid resource ID."""
        response = client.get("/api/fhir/aetna/Patient/bad@id!")

        assert response.status_code == 400

    def test_read_resource_not_found(self, client):
        """Should return 404 when resource not found."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=ResourceNotFound())

        with patch("app.routers.fhir.get_fhir_client", return_value=mock_client):
            response = client.get("/api/fhir/aetna/Patient/nonexistent")

        assert response.status_code == 404

    def test_read_resource_operation_outcome(self, client):
        """Should return 422 for OperationOutcome errors."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=OperationOutcome())

        with patch("app.routers.fhir.get_fhir_client", return_value=mock_client):
            response = client.get("/api/fhir/aetna/Patient/123")

        assert response.status_code == 422


class TestExecuteOperation:
    """Tests for GET /api/fhir/{platform_id}/{resource_type}/{resource_id}/{operation}."""

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        mock_resource = MagicMock()
        mock_resource.execute = AsyncMock(return_value={"resourceType": "Bundle", "type": "searchset"})
        client.resource = MagicMock(return_value=mock_resource)
        return client

    def test_execute_operation_success(self, client, mock_fhir_client):
        """Should execute operation successfully."""
        with (
            patch("app.routers.fhir.get_fhir_client", return_value=mock_fhir_client),
            patch("app.routers.fhir.audit_log"),
        ):
            response = client.get("/api/fhir/aetna/Patient/123/$everything")

        assert response.status_code == 200

    def test_execute_operation_invalid_operation(self, client):
        """Should return 400 for invalid operation (not starting with $)."""
        response = client.get("/api/fhir/aetna/Patient/123/everything")

        assert response.status_code == 400

    def test_execute_operation_not_allowed(self, client):
        """Should return 400 for disallowed operation."""
        response = client.get("/api/fhir/aetna/Patient/123/$unknown")

        assert response.status_code == 400


class TestCreateResource:
    """Tests for POST /api/fhir/{platform_id}/{resource_type}."""

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        # Return an actual dict from save()
        created = {"resourceType": "Patient", "id": "new-123", "name": [{"family": "Smith"}]}
        mock_resource = MagicMock()
        mock_resource.save = AsyncMock(return_value=created)
        client.resource = MagicMock(return_value=mock_resource)
        return client

    def test_create_resource_success(self, client, mock_fhir_client):
        """Should create resource successfully."""
        with (
            patch("app.routers.fhir.get_fhir_client", return_value=mock_fhir_client),
            patch("app.routers.fhir.audit_log"),
        ):
            response = client.post(
                "/api/fhir/aetna/Patient",
                json={"resourceType": "Patient", "name": [{"family": "Smith"}]},
            )

        assert response.status_code == 200

    def test_create_resource_type_mismatch(self, client):
        """Should return 400 when resource type doesn't match URL."""
        response = client.post(
            "/api/fhir/aetna/Patient",
            json={"resourceType": "Observation", "code": {}},
        )

        assert response.status_code == 400
        assert "mismatch" in response.json()["detail"].lower()

    def test_create_resource_invalid_resource_type(self, client):
        """Should return 400 for invalid resource type."""
        response = client.post(
            "/api/fhir/aetna/patient",  # lowercase
            json={"resourceType": "patient"},
        )

        assert response.status_code == 400


class TestUpdateResource:
    """Tests for PUT /api/fhir/{platform_id}/{resource_type}/{resource_id}."""

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        # Return an actual dict from save()
        updated = {"resourceType": "Patient", "id": "123", "name": [{"family": "Jones"}]}
        mock_resource = MagicMock()
        mock_resource.save = AsyncMock(return_value=updated)
        client.resource = MagicMock(return_value=mock_resource)
        return client

    def test_update_resource_success(self, client, mock_fhir_client):
        """Should update resource successfully."""
        with (
            patch("app.routers.fhir.get_fhir_client", return_value=mock_fhir_client),
            patch("app.routers.fhir.audit_log"),
        ):
            response = client.put(
                "/api/fhir/aetna/Patient/123",
                json={"resourceType": "Patient", "id": "123", "name": [{"family": "Jones"}]},
            )

        assert response.status_code == 200

    def test_update_resource_type_mismatch(self, client):
        """Should return 400 when resource type doesn't match URL."""
        response = client.put(
            "/api/fhir/aetna/Patient/123",
            json={"resourceType": "Observation", "id": "123"},
        )

        assert response.status_code == 400
        assert "mismatch" in response.json()["detail"].lower()

    def test_update_resource_id_mismatch(self, client):
        """Should return 400 when resource ID doesn't match URL."""
        response = client.put(
            "/api/fhir/aetna/Patient/123",
            json={"resourceType": "Patient", "id": "456"},
        )

        assert response.status_code == 400
        assert "mismatch" in response.json()["detail"].lower()


class TestDeleteResource:
    """Tests for DELETE /api/fhir/{platform_id}/{resource_type}/{resource_id}."""

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        mock_resource = MagicMock()
        mock_resource.delete = AsyncMock()
        client.resource = MagicMock(return_value=mock_resource)
        return client

    def test_delete_resource_success(self, client, mock_fhir_client):
        """Should delete resource successfully."""
        with (
            patch("app.routers.fhir.get_fhir_client", return_value=mock_fhir_client),
            patch("app.routers.fhir.audit_log"),
        ):
            response = client.delete("/api/fhir/aetna/Patient/123")

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "OperationOutcome"

    def test_delete_resource_not_found(self, client):
        """Should return 404 when resource not found."""
        mock_client = MagicMock()
        mock_resource = MagicMock()
        mock_resource.delete = AsyncMock(side_effect=ResourceNotFound())
        mock_client.resource = MagicMock(return_value=mock_resource)

        with patch("app.routers.fhir.get_fhir_client", return_value=mock_client):
            response = client.delete("/api/fhir/aetna/Patient/nonexistent")

        assert response.status_code == 404

    def test_delete_resource_invalid_resource_type(self, client):
        """Should return 400 for invalid resource type."""
        response = client.delete("/api/fhir/aetna/patient/123")  # lowercase

        assert response.status_code == 400
