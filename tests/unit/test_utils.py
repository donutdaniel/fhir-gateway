"""
Tests for the FHIR utility functions module.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils import (
    FHIR_JSON_CONTENT_TYPE,
    create_operation_outcome,
    extract_bundle_resources,
    extract_user_demographics,
    fetch_server_metadata,
    fhir_request_headers,
    operation_outcome_exception,
    operation_outcome_missing_required,
    sanitize_error_for_user,
    simplify_search_params,
    truncate_fhir_response,
)


class TestFhirRequestHeaders:
    """Tests for fhir_request_headers function."""

    def test_default_headers(self):
        """Should return default FHIR headers."""
        headers = fhir_request_headers()
        assert headers["Accept"] == FHIR_JSON_CONTENT_TYPE
        assert headers["Content-Type"] == FHIR_JSON_CONTENT_TYPE

    def test_custom_accept(self):
        """Should allow custom Accept header."""
        headers = fhir_request_headers(accept="application/json")
        assert headers["Accept"] == "application/json"

    def test_no_content_type(self):
        """Should omit Content-Type when None."""
        headers = fhir_request_headers(content_type=None)
        assert "Content-Type" not in headers


class TestExtractBundleResources:
    """Tests for extract_bundle_resources function."""

    @pytest.mark.asyncio
    async def test_extracts_resources(self):
        """Should extract resources from bundle entries."""
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"fullUrl": "url1", "resource": {"resourceType": "Patient", "id": "1"}},
                {"fullUrl": "url2", "resource": {"resourceType": "Patient", "id": "2"}},
            ],
        }

        result = await extract_bundle_resources(bundle)

        assert len(result["entry"]) == 2
        assert result["entry"][0]["resourceType"] == "Patient"
        assert result["entry"][1]["id"] == "2"

    @pytest.mark.asyncio
    async def test_returns_original_if_no_entries(self):
        """Should return original bundle if no entries."""
        bundle = {"resourceType": "Bundle", "total": 0}

        result = await extract_bundle_resources(bundle)

        assert result == bundle

    @pytest.mark.asyncio
    async def test_handles_empty_entries(self):
        """Should handle empty entry list."""
        bundle = {"resourceType": "Bundle", "entry": []}

        result = await extract_bundle_resources(bundle)

        assert result == bundle

    @pytest.mark.asyncio
    async def test_handles_none_bundle(self):
        """Should handle None bundle."""
        result = await extract_bundle_resources(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_skips_entries_without_resource(self):
        """Should skip entries without resource field."""
        bundle = {
            "entry": [
                {"fullUrl": "url1", "resource": {"id": "1"}},
                {"fullUrl": "url2"},  # No resource
                {"fullUrl": "url3", "resource": {"id": "3"}},
            ]
        }

        result = await extract_bundle_resources(bundle)

        assert len(result["entry"]) == 2


class TestTruncateFhirResponse:
    """Tests for truncate_fhir_response function."""

    def test_no_truncation_under_limits(self):
        """Should not truncate under limits."""
        response = {
            "resourceType": "Bundle",
            "entry": [{"resource": {"id": "1"}}],
        }

        result = truncate_fhir_response(response)

        assert "_truncated" not in result

    def test_truncates_by_entry_count(self):
        """Should truncate when exceeding max entries."""
        entries = [{"resource": {"id": str(i)}} for i in range(100)]
        response = {"resourceType": "Bundle", "entry": entries}

        result = truncate_fhir_response(response, max_entries=10)

        assert result["_truncated"] is True
        assert result["_total_available"] == 100
        assert result["_returned"] == 10
        assert len(result["entry"]) == 10

    def test_truncates_by_char_count(self):
        """Should truncate when exceeding max chars."""
        # Create entries with large data
        entries = [{"resource": {"data": "x" * 1000}} for i in range(20)]
        response = {"resourceType": "Bundle", "entry": entries}

        result = truncate_fhir_response(response, max_chars=5000)

        assert result["_truncated"] is True
        assert len(result["entry"]) < 20

    def test_handles_list_response(self):
        """Should handle list response (not bundle)."""
        response = [{"id": str(i)} for i in range(100)]

        result = truncate_fhir_response(response, max_entries=5)

        assert result["_truncated"] is True
        assert len(result["entry"]) == 5

    def test_handles_no_entries(self):
        """Should handle response without entries."""
        response = {"resourceType": "Patient", "id": "123"}

        result = truncate_fhir_response(response)

        assert result == response

    def test_handles_non_dict_response(self):
        """Should return non-dict response unchanged."""
        result = truncate_fhir_response("string response")
        assert result == "string response"


class TestSimplifySearchParams:
    """Tests for simplify_search_params function."""

    def test_extracts_name_and_docs(self):
        """Should extract name and documentation."""
        params = [
            {"name": "patient", "documentation": "Patient reference", "type": "reference"},
            {"name": "code", "documentation": "Code filter"},
        ]

        result = simplify_search_params(params)

        assert len(result) == 2
        assert result[0]["name"] == "patient"
        assert result[0]["documentation"] == "Patient reference"
        assert "type" not in result[0]

    def test_includes_params_with_only_name(self):
        """Should include params with only name."""
        params = [{"name": "status"}]

        result = simplify_search_params(params)

        assert len(result) == 1
        assert result[0]["name"] == "status"
        assert result[0]["documentation"] is None

    def test_filters_params_without_name_or_docs(self):
        """Should filter params without name or documentation."""
        params = [
            {"name": "valid", "documentation": "Has both"},
            {"type": "token"},  # No name or docs
        ]

        result = simplify_search_params(params)

        assert len(result) == 1


class TestCreateOperationOutcome:
    """Tests for create_operation_outcome function."""

    def test_creates_basic_outcome(self):
        """Should create basic OperationOutcome."""
        result = create_operation_outcome(code="not-found", diagnostics="Resource not found")

        assert result["resourceType"] == "OperationOutcome"
        assert len(result["issue"]) == 1
        assert result["issue"][0]["severity"] == "error"
        assert result["issue"][0]["code"] == "not-found"
        assert result["issue"][0]["diagnostics"] == "Resource not found"

    def test_custom_severity(self):
        """Should allow custom severity."""
        result = create_operation_outcome(
            code="informational", diagnostics="Info", severity="information"
        )

        assert result["issue"][0]["severity"] == "information"


class TestOperationOutcomeHelpers:
    """Tests for OperationOutcome helper functions."""

    def test_exception_outcome(self):
        """Should create exception outcome."""
        result = operation_outcome_exception()

        assert result["issue"][0]["code"] == "exception"
        assert "internal error" in result["issue"][0]["diagnostics"].lower()

    def test_missing_required_with_element(self):
        """Should include element name."""
        result = operation_outcome_missing_required("patient_id")

        assert "patient_id" in result["issue"][0]["diagnostics"]
        assert result["issue"][0]["code"] == "required"

    def test_missing_required_generic(self):
        """Should have generic message without element."""
        result = operation_outcome_missing_required()

        assert "required" in result["issue"][0]["diagnostics"].lower()


class TestSanitizeErrorForUser:
    """Tests for sanitize_error_for_user function."""

    def test_exposes_value_error(self):
        """Should expose ValueError messages."""
        error = ValueError("Invalid input: bad data")
        result = sanitize_error_for_user(error)
        assert result == "Invalid input: bad data"

    def test_exposes_key_error(self):
        """Should expose KeyError messages."""
        error = KeyError("missing_key")
        result = sanitize_error_for_user(error)
        assert "missing_key" in result

    def test_hides_generic_exceptions(self):
        """Should hide generic exception details."""
        error = Exception("Internal path /var/lib/secrets exposed")
        result = sanitize_error_for_user(error, operation="search")
        assert "/var/lib" not in result
        assert "unexpected error" in result.lower()
        assert "search" in result

    def test_exposes_platform_adapter_errors(self):
        """Should expose platform adapter errors."""
        from app.adapters.registry import PlatformAdapterNotFoundError

        error = PlatformAdapterNotFoundError(platform_id="test-platform")
        result = sanitize_error_for_user(error)
        assert "test-platform" in result


class TestFetchServerMetadata:
    """Tests for fetch_server_metadata function."""

    @pytest.mark.asyncio
    async def test_fetches_capability_statement(self):
        """Should fetch and return CapabilityStatement."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "resourceType": "CapabilityStatement",
            "fhirVersion": "4.0.1",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = await fetch_server_metadata("https://fhir.example.com")

            assert result["resourceType"] == "CapabilityStatement"
            assert result["fhirVersion"] == "4.0.1"

    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        """Should raise ValueError on timeout."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="Timeout"):
                await fetch_server_metadata("https://fhir.example.com")

    @pytest.mark.asyncio
    async def test_handles_http_error(self):
        """Should raise ValueError on HTTP error."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=mock_response
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError, match="404"):
                await fetch_server_metadata("https://fhir.example.com")


class TestExtractUserDemographics:
    """Tests for extract_user_demographics function."""

    def test_extracts_standard_fields(self):
        """Should extract standard demographic fields."""
        resource = {
            "resourceType": "Patient",
            "id": "123",
            "name": [{"given": ["John"], "family": "Doe"}],
            "gender": "male",
            "birthDate": "1990-01-01",
            "telecom": [{"system": "phone", "value": "555-1234"}],
            "address": [{"city": "Boston"}],
            "extension": [{"url": "custom"}],  # Should be filtered
        }

        result = extract_user_demographics(resource)

        assert result["id"] == "123"
        assert result["name"][0]["family"] == "Doe"
        assert result["gender"] == "male"
        assert "extension" not in result

    def test_includes_additional_fields(self):
        """Should include additional fields when specified."""
        resource = {
            "resourceType": "Practitioner",
            "id": "456",
            "name": [{"family": "Smith"}],
            "qualification": [{"code": "MD"}],
        }

        result = extract_user_demographics(resource, additional_fields=["qualification"])

        assert "qualification" in result
        assert result["qualification"][0]["code"] == "MD"

    def test_filters_none_values(self):
        """Should filter None values."""
        resource = {
            "resourceType": "Patient",
            "id": "123",
            "name": None,
            "gender": "female",
        }

        result = extract_user_demographics(resource)

        assert "name" not in result
        assert result["gender"] == "female"
