"""
Tests for coverage tools and services.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.coverage import (
    CoverageRequirement,
    CoverageRequirementStatus,
    PlatformInfo,
    PlatformRulesResult,
    QuestionnairePackageResult,
)
from app.services.coverage import (
    check_coverage_requirements,
    fetch_questionnaire_package,
    get_platform_rules,
)


class TestCheckCoverageRequirements:
    """Tests for check_coverage_requirements function."""

    @pytest.fixture
    def mock_client(self):
        """Create mock FHIR client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def mock_coverage(self):
        """Sample coverage resource."""
        return {
            "resourceType": "Coverage",
            "id": "coverage-123",
            "status": "active",
            "payor": [
                {
                    "reference": "Organization/test-payer",
                    "display": "Test Insurance",
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_check_requirements_with_platform_id(self, mock_client, mock_coverage):
        """Test checking requirements with explicit platform_id."""
        mock_client.get = AsyncMock(return_value=mock_coverage)

        with (
            patch("app.services.coverage.get_platform") as mock_get_platform,
            patch("app.services.coverage.PlatformAdapterRegistry") as mock_registry,
        ):
            mock_get_platform.return_value = MagicMock(display_name="Test Platform")

            mock_adapter = AsyncMock()
            mock_adapter.check_coverage_requirements = AsyncMock(
                return_value=CoverageRequirement(
                    status=CoverageRequirementStatus.REQUIRED,
                    platform=PlatformInfo(id="test-platform", name="Test Platform"),
                    procedure_code="27447",
                    code_system="http://www.ama-assn.org/go/cpt",
                    questionnaire_url="http://example.org/Questionnaire/test",
                    documentation_required=True,
                    coverage_id="coverage-123",
                    patient_id="patient-456",
                )
            )
            mock_adapter.fhir_base_url = None
            mock_registry.get_adapter.return_value = mock_adapter

            result = await check_coverage_requirements(
                client=mock_client,
                patient_id="patient-456",
                coverage_id="coverage-123",
                procedure_code="27447",
                platform_id="test-platform",
            )

            assert result.status == CoverageRequirementStatus.REQUIRED
            assert result.documentation_required is True
            assert result.questionnaire_url is not None

    @pytest.mark.asyncio
    async def test_check_requirements_unknown_status(self, mock_client):
        """Test that default returns unknown status."""
        mock_client.get = AsyncMock(return_value={})

        with (
            patch("app.services.coverage.get_platform") as mock_get_platform,
            patch("app.services.coverage.PlatformAdapterRegistry") as mock_registry,
        ):
            mock_get_platform.return_value = None

            mock_adapter = AsyncMock()
            mock_adapter.check_coverage_requirements = AsyncMock(
                return_value=CoverageRequirement(
                    status=CoverageRequirementStatus.UNKNOWN,
                    procedure_code="27447",
                    code_system="http://www.ama-assn.org/go/cpt",
                    coverage_id="coverage-123",
                    patient_id="patient-456",
                    reason="CRD endpoint not configured",
                )
            )
            mock_adapter.fhir_base_url = None
            mock_registry.get_adapter.return_value = mock_adapter

            result = await check_coverage_requirements(
                client=mock_client,
                patient_id="patient-456",
                coverage_id="coverage-123",
                procedure_code="27447",
                platform_id="unknown-platform",
            )

            assert result.status == CoverageRequirementStatus.UNKNOWN
            assert "not configured" in result.reason.lower()


class TestFetchQuestionnairePackage:
    """Tests for fetch_questionnaire_package function."""

    @pytest.fixture
    def mock_client(self):
        """Create mock FHIR client."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_fetch_with_questionnaires(self, mock_client):
        """Test fetching questionnaire package."""
        mock_bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Questionnaire",
                        "id": "q1",
                        "status": "active",
                        "title": "Prior Auth Form",
                        "item": [{"linkId": "1", "text": "Name", "type": "string"}],
                    }
                }
            ],
        }

        with (
            patch("app.services.coverage.get_platform") as mock_get_platform,
            patch("app.services.coverage.PlatformAdapterRegistry") as mock_registry,
        ):
            mock_get_platform.return_value = MagicMock(display_name="Test")

            mock_adapter = AsyncMock()
            mock_adapter.fetch_questionnaire_package = AsyncMock(return_value=mock_bundle)
            mock_adapter.fhir_base_url = None
            mock_registry.get_adapter.return_value = mock_adapter

            result = await fetch_questionnaire_package(
                client=mock_client,
                coverage_id="coverage-123",
                platform_id="test-platform",
            )

            assert isinstance(result, QuestionnairePackageResult)
            assert len(result.questionnaires) == 1
            assert result.questionnaires[0].title == "Prior Auth Form"

    @pytest.mark.asyncio
    async def test_fetch_raw_format(self, mock_client):
        """Test raw format returns bundle."""
        mock_bundle = {"resourceType": "Bundle", "type": "collection", "entry": []}

        with (
            patch("app.services.coverage.get_platform") as mock_get_platform,
            patch("app.services.coverage.PlatformAdapterRegistry") as mock_registry,
        ):
            mock_get_platform.return_value = MagicMock(display_name="Test")

            mock_adapter = AsyncMock()
            mock_adapter.fetch_questionnaire_package = AsyncMock(return_value=mock_bundle)
            mock_adapter.fhir_base_url = None
            mock_registry.get_adapter.return_value = mock_adapter

            result = await fetch_questionnaire_package(
                client=mock_client,
                coverage_id="coverage-123",
                platform_id="test-platform",
                raw_format=True,
            )

            assert isinstance(result, dict)
            assert "raw_bundle" in result


class TestGetPlatformRules:
    """Tests for get_platform_rules function."""

    @pytest.fixture
    def mock_client(self):
        """Create mock FHIR client."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_rules_empty(self, mock_client):
        """Test getting rules returns empty by default."""
        with (
            patch("app.services.coverage.get_platform") as mock_get_platform,
            patch("app.services.coverage.PlatformAdapterRegistry") as mock_registry,
        ):
            mock_get_platform.return_value = MagicMock(display_name="Test")

            mock_adapter = AsyncMock()
            mock_adapter.get_platform_rules = AsyncMock(
                return_value=PlatformRulesResult(
                    platform_id="test-platform",
                    procedure_code="27447",
                    code_system="http://www.ama-assn.org/go/cpt",
                    rules=[],
                    markdown_summary="# Policy Rules\n\nNo rules found.",
                )
            )
            mock_adapter.fhir_base_url = None
            mock_registry.get_adapter.return_value = mock_adapter

            result = await get_platform_rules(
                client=mock_client,
                platform_id="test-platform",
                procedure_code="27447",
            )

            assert isinstance(result, PlatformRulesResult)
            assert len(result.rules) == 0
            assert "No rules" in result.markdown_summary


class TestCoverageRequirementModel:
    """Tests for CoverageRequirement model."""

    def test_create_requirement(self):
        """Test creating a coverage requirement."""
        req = CoverageRequirement(
            status=CoverageRequirementStatus.REQUIRED,
            procedure_code="27447",
            code_system="http://www.ama-assn.org/go/cpt",
            coverage_id="cov-123",
            patient_id="pat-456",
        )

        assert req.status == CoverageRequirementStatus.REQUIRED
        assert req.procedure_code == "27447"
        assert req.documentation_required is False  # Default
        assert req.platform is None  # Optional

    def test_requirement_with_platform(self):
        """Test requirement with platform info."""
        req = CoverageRequirement(
            status=CoverageRequirementStatus.CONDITIONAL,
            platform=PlatformInfo(id="aetna", name="Aetna"),
            procedure_code="27447",
            code_system="http://www.ama-assn.org/go/cpt",
            coverage_id="cov-123",
            patient_id="pat-456",
            reason="May require auth depending on diagnosis",
        )

        assert req.platform.id == "aetna"
        assert req.platform.name == "Aetna"
        assert "diagnosis" in req.reason


class TestPlatformRulesResultModel:
    """Tests for PlatformRulesResult model."""

    def test_create_rules_result(self):
        """Test creating platform rules result."""
        result = PlatformRulesResult(
            platform_id="cigna",
            procedure_code="99213",
            code_system="http://www.ama-assn.org/go/cpt",
            rules=[],
            markdown_summary="# Rules\n\nNo rules.",
        )

        assert result.platform_id == "cigna"
        assert result.procedure_code == "99213"
        assert len(result.rules) == 0
