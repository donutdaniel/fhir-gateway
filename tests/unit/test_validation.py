"""
Tests for input validation.
"""

import pytest

from app.validation import (
    ValidationError,
    validate_operation,
    validate_procedure_code,
    validate_resource_id,
    validate_resource_type,
)


class TestValidateResourceType:
    """Tests for validate_resource_type."""

    def test_valid_resource_types(self):
        """Test valid FHIR resource types."""
        valid_types = [
            "Patient",
            "Observation",
            "MedicationRequest",
            "AllergyIntolerance",
            "Coverage",
            "Claim",
            "ExplanationOfBenefit",
        ]
        for rt in valid_types:
            assert validate_resource_type(rt) == rt

    def test_invalid_lowercase(self):
        """Test lowercase resource types are invalid."""
        with pytest.raises(ValidationError) as exc:
            validate_resource_type("patient")
        assert "Invalid resource type" in str(exc.value)

    def test_invalid_with_numbers(self):
        """Test resource types with numbers are invalid."""
        with pytest.raises(ValidationError):
            validate_resource_type("Patient1")

    def test_invalid_with_underscore(self):
        """Test resource types with underscore are invalid."""
        with pytest.raises(ValidationError):
            validate_resource_type("Patient_Resource")

    def test_invalid_empty(self):
        """Test empty resource type is invalid."""
        with pytest.raises(ValidationError):
            validate_resource_type("")

    def test_invalid_special_chars(self):
        """Test resource types with special chars are invalid."""
        with pytest.raises(ValidationError):
            validate_resource_type("Patient<script>")


class TestValidateResourceId:
    """Tests for validate_resource_id."""

    def test_valid_resource_ids(self):
        """Test valid FHIR resource IDs."""
        valid_ids = [
            "123",
            "abc-123",
            "patient.001",
            "A1b2C3",
            "test-id-with-hyphens",
        ]
        for rid in valid_ids:
            assert validate_resource_id(rid) == rid

    def test_invalid_empty(self):
        """Test empty resource ID is invalid."""
        with pytest.raises(ValidationError):
            validate_resource_id("")

    def test_invalid_too_long(self):
        """Test resource ID over 64 chars is invalid."""
        long_id = "a" * 65
        with pytest.raises(ValidationError):
            validate_resource_id(long_id)

    def test_invalid_special_chars(self):
        """Test resource IDs with invalid chars are rejected."""
        with pytest.raises(ValidationError):
            validate_resource_id("id/with/slashes")
        with pytest.raises(ValidationError):
            validate_resource_id("id<script>")


class TestValidateProcedureCode:
    """Tests for validate_procedure_code."""

    def test_valid_cpt_codes(self):
        """Test valid CPT codes (5 digits)."""
        cpt_system = "http://www.ama-assn.org/go/cpt"
        valid_codes = ["99213", "27447", "12345"]
        for code in valid_codes:
            result = validate_procedure_code(code, cpt_system)
            assert result == code.upper()

    def test_invalid_cpt_code(self):
        """Test invalid CPT codes."""
        cpt_system = "http://www.ama-assn.org/go/cpt"
        with pytest.raises(ValidationError):
            validate_procedure_code("1234", cpt_system)  # Too short
        with pytest.raises(ValidationError):
            validate_procedure_code("123456", cpt_system)  # Too long
        with pytest.raises(ValidationError):
            validate_procedure_code("ABCDE", cpt_system)  # Letters

    def test_valid_hcpcs_codes(self):
        """Test valid HCPCS codes (letter + 4 digits)."""
        hcpcs_system = "https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"
        valid_codes = ["A1234", "J0123", "L5000"]
        for code in valid_codes:
            result = validate_procedure_code(code, hcpcs_system)
            assert result == code.upper()

    def test_invalid_hcpcs_code(self):
        """Test invalid HCPCS codes."""
        hcpcs_system = "https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"
        with pytest.raises(ValidationError):
            validate_procedure_code("12345", hcpcs_system)  # No letter
        with pytest.raises(ValidationError):
            validate_procedure_code("AB123", hcpcs_system)  # Two letters

    def test_valid_generic_codes(self):
        """Test valid codes without specific system."""
        valid_codes = ["ABC", "12345", "A1B2C3"]
        for code in valid_codes:
            result = validate_procedure_code(code)
            assert result == code.upper()

    def test_empty_code(self):
        """Test empty procedure code is invalid."""
        with pytest.raises(ValidationError):
            validate_procedure_code("")


class TestValidateOperation:
    """Tests for validate_operation."""

    def test_valid_operations(self):
        """Test valid FHIR operations."""
        valid_ops = [
            "$everything",
            "$validate",
            "$summary",
            "$expand",
        ]
        for op in valid_ops:
            assert validate_operation(op) == op

    def test_invalid_no_dollar(self):
        """Test operations without $ prefix are invalid."""
        with pytest.raises(ValidationError):
            validate_operation("everything")

    def test_invalid_unknown_operation(self):
        """Test unknown operations are rejected."""
        with pytest.raises(ValidationError):
            validate_operation("$malicious-op")

    def test_invalid_empty(self):
        """Test empty operation is invalid."""
        with pytest.raises(ValidationError):
            validate_operation("")
