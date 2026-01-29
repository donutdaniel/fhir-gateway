"""
Tests for payer adapters.
"""

from unittest.mock import AsyncMock

import pytest

from app.adapters.base import BasePayerAdapter
from app.models.coverage import CoverageRequirementStatus


class ConcreteAdapter(BasePayerAdapter):
    """Concrete implementation for testing."""

    @property
    def adapter_name(self) -> str:
        return "TestAdapter"


class TestBasePayerAdapter:
    """Tests for BasePayerAdapter."""

    @pytest.fixture
    def mock_client(self):
        """Create mock FHIR client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def adapter(self, mock_client):
        """Create adapter instance."""
        return ConcreteAdapter(client=mock_client)

    def test_client_property_default(self, adapter, mock_client):
        """Test default client is returned."""
        assert adapter.client == mock_client

    def test_fhir_base_url_none_by_default(self, adapter):
        """Test fhir_base_url is None by default."""
        assert adapter.fhir_base_url is None

    def test_adapter_name(self, adapter):
        """Test adapter name is returned."""
        assert adapter.adapter_name == "TestAdapter"

    @pytest.mark.asyncio
    async def test_get_coverage(self, adapter, mock_client):
        """Test fetching coverage resource."""
        mock_coverage = {"resourceType": "Coverage", "id": "cov-123"}
        mock_client.get = AsyncMock(return_value=mock_coverage)

        result = await adapter.get_coverage("cov-123")

        mock_client.get.assert_called_once_with(
            resource_type_or_resource_or_ref="Coverage",
            id_or_ref="cov-123",
        )
        assert result["id"] == "cov-123"

    @pytest.mark.asyncio
    async def test_get_patient(self, adapter, mock_client):
        """Test fetching patient resource."""
        mock_patient = {"resourceType": "Patient", "id": "pat-456"}
        mock_client.get = AsyncMock(return_value=mock_patient)

        result = await adapter.get_patient("pat-456")

        mock_client.get.assert_called_once_with(
            resource_type_or_resource_or_ref="Patient",
            id_or_ref="pat-456",
        )
        assert result["id"] == "pat-456"

    def test_extract_payer_from_coverage(self, adapter):
        """Test extracting payer info from coverage."""
        coverage = {
            "resourceType": "Coverage",
            "payor": [
                {
                    "reference": "Organization/aetna",
                    "display": "Aetna Health Insurance",
                }
            ],
        }

        payer_info = adapter.extract_payer_from_coverage(coverage)

        assert payer_info is not None
        assert payer_info.id == "aetna"
        assert payer_info.name == "Aetna Health Insurance"

    def test_extract_payer_no_payor(self, adapter):
        """Test extracting from coverage without payor."""
        coverage = {"resourceType": "Coverage"}

        payer_info = adapter.extract_payer_from_coverage(coverage)

        assert payer_info is None

    @pytest.mark.asyncio
    async def test_check_coverage_requirements_default(self, adapter):
        """Test default coverage requirements returns unknown."""
        result = await adapter.check_coverage_requirements(
            patient_id="pat-123",
            coverage_id="cov-456",
            procedure_code="27447",
        )

        assert result.status == CoverageRequirementStatus.UNKNOWN
        assert "not configured" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_fetch_questionnaire_package_default(self, adapter, mock_client):
        """Test default questionnaire fetch returns empty bundle."""
        mock_client.execute = AsyncMock(side_effect=Exception("Not supported"))

        result = await adapter.fetch_questionnaire_package(
            coverage_id="cov-123",
        )

        assert result["resourceType"] == "Bundle"
        assert len(result["entry"]) == 0

    @pytest.mark.asyncio
    async def test_get_platform_rules_default(self, adapter):
        """Test default platform rules returns empty."""
        result = await adapter.get_platform_rules(
            platform_id="test-platform",
            procedure_code="27447",
        )

        assert len(result.rules) == 0
        assert "No policy rules" in result.markdown_summary

    @pytest.mark.asyncio
    async def test_initialize_platform_client_no_url(self, adapter):
        """Test initialize with no URL does nothing."""
        await adapter.initialize_platform_client(access_token="test-token")

        # Should not have created a platform client
        assert adapter._platform_client is None
