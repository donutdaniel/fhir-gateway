"""
Tests for FHIR utility functions.
"""

from app.utils import (
    FHIR_JSON_CONTENT_TYPE,
    extract_bearer_token,
    fhir_request_headers,
)


class TestExtractBearerToken:
    """Tests for extract_bearer_token function."""

    def test_extracts_valid_token(self):
        """Should extract token from valid Bearer header."""
        result = extract_bearer_token("Bearer eyJhbGciOiJIUzI1NiJ9")
        assert result == "eyJhbGciOiJIUzI1NiJ9"

    def test_returns_none_for_none_input(self):
        """Should return None when input is None."""
        result = extract_bearer_token(None)
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Should return None for empty string."""
        result = extract_bearer_token("")
        assert result is None

    def test_returns_none_for_non_bearer(self):
        """Should return None for non-Bearer auth."""
        result = extract_bearer_token("Basic dXNlcjpwYXNz")
        assert result is None

    def test_case_sensitive_bearer(self):
        """Should be case-sensitive for 'Bearer' prefix."""
        result = extract_bearer_token("bearer token123")
        assert result is None

    def test_handles_bearer_only(self):
        """Should handle 'Bearer ' with no token."""
        result = extract_bearer_token("Bearer ")
        assert result == ""


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


class TestFhirJsonContentType:
    """Tests for FHIR_JSON_CONTENT_TYPE constant."""

    def test_content_type_value(self):
        """Should have correct FHIR JSON content type."""
        assert FHIR_JSON_CONTENT_TYPE == "application/fhir+json"
