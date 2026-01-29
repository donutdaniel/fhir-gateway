"""
Tests for coverage router endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import PlatformNotConfiguredError, PlatformNotFoundError
from app.models.coverage import (
    CoverageRequirement,
    CoverageRequirementStatus,
    PlatformRulesResult,
    QuestionnairePackageResult,
)
from app.routers.coverage import router


@pytest.fixture
def app():
    """Create test FastAPI app with coverage router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestCheckRequirements:
    """Tests for POST /api/coverage/{platform_id}/requirements."""

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        return MagicMock()

    @pytest.fixture
    def mock_coverage_result(self):
        """Create mock coverage requirement result."""
        return CoverageRequirement(
            status=CoverageRequirementStatus.REQUIRED,
            procedure_code="27447",
            code_system="http://www.ama-assn.org/go/cpt",
            coverage_id="cov-123",
            patient_id="pat-456",
            documentation_required=True,
            questionnaire_url="http://example.org/Questionnaire/knee",
            reason="Prior authorization required for total knee replacement",
        )

    def test_check_requirements_success(self, client, mock_fhir_client, mock_coverage_result):
        """Should return coverage requirements for valid request."""
        with (
            patch("app.routers.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.routers.coverage.check_coverage_requirements",
                new_callable=AsyncMock,
                return_value=mock_coverage_result,
            ),
            patch("app.routers.coverage.audit_log"),
        ):
            response = client.post(
                "/api/coverage/aetna/requirements",
                json={
                    "patient_id": "pat-456",
                    "coverage_id": "cov-123",
                    "procedure_code": "27447",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "required"
        assert data["procedure_code"] == "27447"
        assert data["documentation_required"] is True

    def test_check_requirements_with_custom_code_system(self, client, mock_fhir_client, mock_coverage_result):
        """Should use custom code system."""
        with (
            patch("app.routers.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.routers.coverage.check_coverage_requirements",
                new_callable=AsyncMock,
                return_value=mock_coverage_result,
            ) as mock_check,
            patch("app.routers.coverage.audit_log"),
        ):
            response = client.post(
                "/api/coverage/aetna/requirements",
                json={
                    "patient_id": "pat-456",
                    "coverage_id": "cov-123",
                    "procedure_code": "G0219",
                    "code_system": "https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets",
                },
            )

        assert response.status_code == 200
        mock_check.assert_called_once()
        call_kwargs = mock_check.call_args.kwargs
        assert call_kwargs["code_system"] == "https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"

    def test_check_requirements_invalid_patient_id(self, client):
        """Should return 400 for invalid patient_id."""
        response = client.post(
            "/api/coverage/aetna/requirements",
            json={
                "patient_id": "bad@id!",
                "coverage_id": "cov-123",
                "procedure_code": "27447",
            },
        )

        assert response.status_code == 400
        assert "patient_id" in response.json()["detail"].lower()

    def test_check_requirements_invalid_coverage_id(self, client):
        """Should return 400 for invalid coverage_id."""
        response = client.post(
            "/api/coverage/aetna/requirements",
            json={
                "patient_id": "pat-456",
                "coverage_id": "bad@id!",
                "procedure_code": "27447",
            },
        )

        assert response.status_code == 400
        assert "coverage_id" in response.json()["detail"].lower()

    def test_check_requirements_platform_not_found(self, client, mock_fhir_client):
        """Should return 404 when platform not found."""
        # First patch validation to pass, then have get_fhir_client raise the error
        with (
            patch("app.routers.validation._validate_platform_id", return_value=None),
            patch(
                "app.routers.coverage.get_fhir_client",
                side_effect=PlatformNotFoundError("unknown"),
            ),
        ):
            response = client.post(
                "/api/coverage/unknown/requirements",
                json={
                    "patient_id": "pat-456",
                    "coverage_id": "cov-123",
                    "procedure_code": "27447",
                },
            )

        assert response.status_code == 404

    def test_check_requirements_platform_not_configured(self, client):
        """Should return 503 when platform not configured."""
        with patch(
            "app.routers.coverage.get_fhir_client",
            side_effect=PlatformNotConfiguredError("aetna"),
        ):
            response = client.post(
                "/api/coverage/aetna/requirements",
                json={
                    "patient_id": "pat-456",
                    "coverage_id": "cov-123",
                    "procedure_code": "27447",
                },
            )

        assert response.status_code == 503


class TestGetQuestionnairePackage:
    """Tests for POST /api/coverage/{platform_id}/questionnaire-package."""

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        return MagicMock()

    @pytest.fixture
    def mock_package_result(self):
        """Create mock questionnaire package result."""
        return QuestionnairePackageResult(
            questionnaires=[],
            value_sets=None,
            libraries=None,
        )

    @pytest.fixture
    def mock_raw_bundle(self):
        """Create mock raw FHIR bundle."""
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Questionnaire",
                        "id": "test-q",
                    }
                }
            ],
        }

    def test_get_questionnaire_package_success(self, client, mock_fhir_client, mock_package_result):
        """Should return questionnaire package for valid request."""
        with (
            patch("app.routers.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.routers.coverage.fetch_questionnaire_package",
                new_callable=AsyncMock,
                return_value=mock_package_result,
            ),
            patch("app.routers.coverage.audit_log"),
        ):
            response = client.post(
                "/api/coverage/aetna/questionnaire-package",
                json={"coverage_id": "cov-123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "questionnaires" in data

    def test_get_questionnaire_package_raw_format(self, client, mock_fhir_client, mock_raw_bundle):
        """Should return raw bundle when raw_format=True."""
        with (
            patch("app.routers.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.routers.coverage.fetch_questionnaire_package",
                new_callable=AsyncMock,
                return_value=mock_raw_bundle,
            ),
            patch("app.routers.coverage.audit_log"),
        ):
            response = client.post(
                "/api/coverage/aetna/questionnaire-package",
                json={"coverage_id": "cov-123", "raw_format": True},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Bundle"

    def test_get_questionnaire_package_with_url(self, client, mock_fhir_client, mock_package_result):
        """Should pass questionnaire URL to service."""
        with (
            patch("app.routers.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.routers.coverage.fetch_questionnaire_package",
                new_callable=AsyncMock,
                return_value=mock_package_result,
            ) as mock_fetch,
            patch("app.routers.coverage.audit_log"),
        ):
            response = client.post(
                "/api/coverage/aetna/questionnaire-package",
                json={
                    "coverage_id": "cov-123",
                    "questionnaire_url": "http://example.org/Questionnaire/knee",
                },
            )

        assert response.status_code == 200
        mock_fetch.assert_called_once()
        call_kwargs = mock_fetch.call_args.kwargs
        assert call_kwargs["questionnaire_url"] == "http://example.org/Questionnaire/knee"

    def test_get_questionnaire_package_invalid_coverage_id(self, client):
        """Should return 400 for invalid coverage_id."""
        response = client.post(
            "/api/coverage/aetna/questionnaire-package",
            json={"coverage_id": "bad@id!"},
        )

        assert response.status_code == 400

    def test_get_questionnaire_package_platform_not_found(self, client, mock_fhir_client):
        """Should return 404 when platform not found."""
        # First patch validation to pass, then have get_fhir_client raise the error
        with (
            patch("app.routers.validation._validate_platform_id", return_value=None),
            patch(
                "app.routers.coverage.get_fhir_client",
                side_effect=PlatformNotFoundError("unknown"),
            ),
        ):
            response = client.post(
                "/api/coverage/unknown/questionnaire-package",
                json={"coverage_id": "cov-123"},
            )

        assert response.status_code == 404


class TestGetRules:
    """Tests for GET /api/coverage/{platform_id}/rules/{procedure_code}."""

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        return MagicMock()

    @pytest.fixture
    def mock_rules_result(self):
        """Create mock platform rules result."""
        return PlatformRulesResult(
            platform_id="aetna",
            procedure_code="27447",
            code_system="http://www.ama-assn.org/go/cpt",
            rules=[],
            markdown_summary="No policy rules found for procedure code 27447",
        )

    def test_get_rules_success(self, client, mock_fhir_client, mock_rules_result):
        """Should return policy rules for valid request."""
        with (
            patch("app.routers.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.routers.coverage.get_platform_rules",
                new_callable=AsyncMock,
                return_value=mock_rules_result,
            ),
            patch("app.routers.coverage.audit_log"),
        ):
            response = client.get("/api/coverage/aetna/rules/27447")

        assert response.status_code == 200
        data = response.json()
        assert data["platform_id"] == "aetna"
        assert data["procedure_code"] == "27447"
        assert "markdown_summary" in data

    def test_get_rules_with_custom_code_system(self, client, mock_fhir_client, mock_rules_result):
        """Should use custom code system."""
        with (
            patch("app.routers.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.routers.coverage.get_platform_rules",
                new_callable=AsyncMock,
                return_value=mock_rules_result,
            ) as mock_get_rules,
            patch("app.routers.coverage.audit_log"),
        ):
            response = client.get(
                "/api/coverage/aetna/rules/G0219?code_system=https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"
            )

        assert response.status_code == 200
        mock_get_rules.assert_called_once()
        call_kwargs = mock_get_rules.call_args.kwargs
        assert call_kwargs["code_system"] == "https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"

    def test_get_rules_platform_not_found(self, client, mock_fhir_client):
        """Should return 404 when platform not found."""
        # First patch validation to pass, then have get_fhir_client raise the error
        with (
            patch("app.routers.validation._validate_platform_id", return_value=None),
            patch(
                "app.routers.coverage.get_fhir_client",
                side_effect=PlatformNotFoundError("unknown"),
            ),
        ):
            response = client.get("/api/coverage/unknown/rules/27447")

        assert response.status_code == 404

    def test_get_rules_platform_not_configured(self, client):
        """Should return 503 when platform not configured."""
        with patch(
            "app.routers.coverage.get_fhir_client",
            side_effect=PlatformNotConfiguredError("aetna"),
        ):
            response = client.get("/api/coverage/aetna/rules/27447")

        assert response.status_code == 503

    def test_get_rules_general_error(self, client, mock_fhir_client):
        """Should return 500 for general errors."""
        with (
            patch("app.routers.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.routers.coverage.get_platform_rules",
                new_callable=AsyncMock,
                side_effect=Exception("Service error"),
            ),
        ):
            response = client.get("/api/coverage/aetna/rules/27447")

        assert response.status_code == 500
