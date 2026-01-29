"""
Tests for payer adapters and adapter registry.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.base import BasePayerAdapter
from app.adapters.registry import (
    PlatformAdapterNotFoundError,
    PlatformAdapterRegistry,
    PlatformNotConfiguredError,
)
from app.models.coverage import CoverageRequirementStatus
from app.models.platform import PlatformInfo


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


class TestPlatformAdapterRegistry:
    """Tests for PlatformAdapterRegistry."""

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear registry before and after each test."""
        PlatformAdapterRegistry.clear()
        yield
        PlatformAdapterRegistry.clear()

    @pytest.fixture
    def mock_client(self):
        """Create mock FHIR client."""
        return AsyncMock()

    def test_register_platform(self):
        """Test registering a platform ID."""
        PlatformAdapterRegistry.register("test-platform")

        assert "test-platform" in PlatformAdapterRegistry.list_registered()
        assert PlatformAdapterRegistry.get_platform_count() == 1

    def test_register_platform_case_insensitive(self):
        """Test platform IDs are normalized to lowercase."""
        PlatformAdapterRegistry.register("TEST-Platform")

        registered = PlatformAdapterRegistry.list_registered()
        assert "test-platform" in registered
        assert "TEST-Platform" not in registered

    def test_register_with_aliases(self):
        """Test registering a platform with aliases."""
        PlatformAdapterRegistry.register("aetna", aliases=["aetna-health", "aetna-cvs"])

        assert "aetna" in PlatformAdapterRegistry.list_registered()

        # Test alias resolution
        assert PlatformAdapterRegistry._resolve_platform_id("aetna-health") == "aetna"
        assert PlatformAdapterRegistry._resolve_platform_id("aetna-cvs") == "aetna"

    def test_register_pattern(self):
        """Test registering a pattern."""
        PlatformAdapterRegistry.register("aetna")
        PlatformAdapterRegistry.register_pattern("aetna", "aetna")

        # Pattern should resolve to canonical ID
        resolved = PlatformAdapterRegistry._resolve_platform_id("aetna-some-variant")
        assert resolved == "aetna"

    def test_resolve_platform_id_direct(self):
        """Test resolving a directly registered platform ID."""
        PlatformAdapterRegistry.register("cigna")

        resolved = PlatformAdapterRegistry._resolve_platform_id("cigna")
        assert resolved == "cigna"

    def test_resolve_platform_id_alias(self):
        """Test resolving an alias."""
        PlatformAdapterRegistry.register("united", aliases=["uhc", "united-healthcare"])

        assert PlatformAdapterRegistry._resolve_platform_id("uhc") == "united"
        assert PlatformAdapterRegistry._resolve_platform_id("united-healthcare") == "united"

    def test_resolve_platform_id_pattern(self):
        """Test resolving via pattern matching."""
        PlatformAdapterRegistry.register("bcbs")
        PlatformAdapterRegistry.register_pattern("blue", "bcbs")

        resolved = PlatformAdapterRegistry._resolve_platform_id("blue-cross-michigan")
        assert resolved == "bcbs"

    def test_resolve_platform_id_not_found(self):
        """Test resolving unknown platform returns None."""
        resolved = PlatformAdapterRegistry._resolve_platform_id("unknown-platform")
        assert resolved is None

    def test_auto_register_from_directory(self):
        """Test auto-registering platforms from JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            platforms_dir = Path(tmpdir)

            # Create test platform JSON files
            platform1 = {
                "id": "test-payer-1",
                "name": "Test Payer 1",
                "aliases": ["tp1", "test1"],
                "patterns": ["testpayer"],
            }
            with open(platforms_dir / "test-payer-1.json", "w") as f:
                json.dump(platform1, f)

            platform2 = {"id": "test-payer-2", "name": "Test Payer 2"}
            with open(platforms_dir / "test-payer-2.json", "w") as f:
                json.dump(platform2, f)

            count = PlatformAdapterRegistry.auto_register(platforms_dir)

            assert count == 2
            assert "test-payer-1" in PlatformAdapterRegistry.list_registered()
            assert "test-payer-2" in PlatformAdapterRegistry.list_registered()

            # Check aliases were registered
            assert PlatformAdapterRegistry._resolve_platform_id("tp1") == "test-payer-1"

            # Check patterns were registered
            assert PlatformAdapterRegistry._resolve_platform_id("testpayer-variant") == "test-payer-1"

    def test_auto_register_invalid_json(self):
        """Test auto-register handles invalid JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            platforms_dir = Path(tmpdir)

            # Create invalid JSON file
            with open(platforms_dir / "invalid.json", "w") as f:
                f.write("not valid json {")

            # Create valid JSON file
            with open(platforms_dir / "valid.json", "w") as f:
                json.dump({"id": "valid-platform"}, f)

            count = PlatformAdapterRegistry.auto_register(platforms_dir)

            assert count == 1  # Only valid file counted
            assert "valid-platform" in PlatformAdapterRegistry.list_registered()

    def test_auto_register_missing_directory(self):
        """Test auto-register handles missing directory."""
        count = PlatformAdapterRegistry.auto_register(Path("/nonexistent/path"))

        assert count == 0

    def test_auto_register_uses_filename_as_fallback_id(self):
        """Test auto-register uses filename as ID if not in JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            platforms_dir = Path(tmpdir)

            # Create JSON without id field
            with open(platforms_dir / "fallback-platform.json", "w") as f:
                json.dump({"name": "Fallback Platform"}, f)

            PlatformAdapterRegistry.auto_register(platforms_dir)

            assert "fallback-platform" in PlatformAdapterRegistry.list_registered()

    def test_get_adapter_success(self, mock_client):
        """Test getting adapter for registered platform."""
        PlatformAdapterRegistry.register("aetna")
        platform_info = PlatformInfo(id="aetna", name="Aetna Health")

        with patch("app.adapters.generic.GenericPayerAdapter") as MockAdapter:
            MockAdapter.return_value = MagicMock()
            adapter = PlatformAdapterRegistry.get_adapter(platform_info, mock_client)

        MockAdapter.assert_called_once()
        assert adapter is not None

    def test_get_adapter_no_platform_info(self, mock_client):
        """Test get_adapter raises error when platform_info is None."""
        with pytest.raises(PlatformAdapterNotFoundError):
            PlatformAdapterRegistry.get_adapter(None, mock_client)

    def test_get_adapter_unknown_platform(self, mock_client):
        """Test get_adapter raises error for unknown platform."""
        platform_info = PlatformInfo(id="unknown", name="Unknown Platform")

        with pytest.raises(PlatformAdapterNotFoundError) as exc_info:
            PlatformAdapterRegistry.get_adapter(platform_info, mock_client)

        assert "unknown" in str(exc_info.value)

    def test_get_adapter_resolves_by_name_pattern(self, mock_client):
        """Test get_adapter can resolve via name pattern matching."""
        PlatformAdapterRegistry.register("aetna")
        PlatformAdapterRegistry.register_pattern("aetna", "aetna")

        platform_info = PlatformInfo(id="unknown-id", name="Aetna Health Insurance")

        with patch("app.adapters.generic.GenericPayerAdapter") as MockAdapter:
            MockAdapter.return_value = MagicMock()
            adapter = PlatformAdapterRegistry.get_adapter(platform_info, mock_client)

        assert adapter is not None

    def test_get_adapter_by_id_success(self, mock_client):
        """Test getting adapter by ID."""
        PlatformAdapterRegistry.register("cigna")

        with patch("app.adapters.generic.GenericPayerAdapter") as MockAdapter:
            MockAdapter.return_value = MagicMock()
            adapter = PlatformAdapterRegistry.get_adapter_by_id("cigna", mock_client)

        MockAdapter.assert_called_once()
        assert adapter is not None

    def test_get_adapter_by_id_unknown(self, mock_client):
        """Test get_adapter_by_id raises error for unknown platform."""
        with pytest.raises(PlatformAdapterNotFoundError) as exc_info:
            PlatformAdapterRegistry.get_adapter_by_id("unknown", mock_client)

        assert "unknown" in str(exc_info.value)

    def test_has_adapter_true(self):
        """Test has_adapter returns True for registered platform."""
        PlatformAdapterRegistry.register("aetna")
        platform_info = PlatformInfo(id="aetna")

        assert PlatformAdapterRegistry.has_adapter(platform_info) is True

    def test_has_adapter_false(self):
        """Test has_adapter returns False for unknown platform."""
        platform_info = PlatformInfo(id="unknown")

        assert PlatformAdapterRegistry.has_adapter(platform_info) is False

    def test_has_adapter_none_platform(self):
        """Test has_adapter returns False for None platform."""
        assert PlatformAdapterRegistry.has_adapter(None) is False

    def test_clear_registry(self):
        """Test clearing the registry."""
        PlatformAdapterRegistry.register("aetna", aliases=["a1"])
        PlatformAdapterRegistry.register_pattern("test", "aetna")

        PlatformAdapterRegistry.clear()

        assert PlatformAdapterRegistry.get_platform_count() == 0
        assert len(PlatformAdapterRegistry.list_registered()) == 0

    def test_get_platform_fhir_url_success(self):
        """Test getting FHIR URL for platform."""
        PlatformAdapterRegistry.register("aetna")

        mock_platform = MagicMock()
        mock_platform.fhir_base_url = "https://fhir.aetna.com/r4"

        with patch("app.config.platform.get_platform", return_value=mock_platform):
            url = PlatformAdapterRegistry.get_platform_fhir_url("aetna")

        assert url == "https://fhir.aetna.com/r4"

    def test_get_platform_fhir_url_not_found(self):
        """Test get_platform_fhir_url raises error for unknown platform."""
        with pytest.raises(PlatformAdapterNotFoundError):
            PlatformAdapterRegistry.get_platform_fhir_url("unknown")

    def test_get_platform_fhir_url_no_config(self):
        """Test get_platform_fhir_url returns None when platform has no config."""
        PlatformAdapterRegistry.register("aetna")

        with patch("app.config.platform.get_platform", return_value=None):
            url = PlatformAdapterRegistry.get_platform_fhir_url("aetna")

        assert url is None


class TestPlatformAdapterNotFoundError:
    """Tests for PlatformAdapterNotFoundError."""

    def test_error_with_platform_info(self):
        """Test error message with platform_info."""
        platform_info = PlatformInfo(id="test-id", name="Test Platform")
        error = PlatformAdapterNotFoundError(platform_info=platform_info)

        assert "test-id" in str(error)
        assert "Test Platform" in str(error)

    def test_error_with_platform_id(self):
        """Test error message with platform_id only."""
        error = PlatformAdapterNotFoundError(platform_id="test-id")

        assert "test-id" in str(error)

    def test_error_with_no_info(self):
        """Test error message with no platform info."""
        error = PlatformAdapterNotFoundError()

        assert "No platform information" in str(error)


class TestPlatformNotConfiguredError:
    """Tests for PlatformNotConfiguredError."""

    def test_error_default_message(self):
        """Test default error message."""
        error = PlatformNotConfiguredError("aetna")

        assert "aetna" in str(error)
        assert "fhir_base_url" in str(error).lower()

    def test_error_custom_message(self):
        """Test custom error message."""
        error = PlatformNotConfiguredError("aetna", "Custom error message")

        assert str(error) == "Custom error message"
