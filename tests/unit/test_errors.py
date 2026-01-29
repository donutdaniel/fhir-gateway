"""
Tests for the custom error types module.
"""

from app.errors import (
    AuthenticationError,
    ConfigurationError,
    CoverageError,
    CoverageInactiveError,
    CoverageNotFoundError,
    FHIRGatewayError,
    FHIRResourceError,
    InsufficientScopeError,
    InvalidPatientIdError,
    InvalidProcedureCodeError,
    InvalidResourceError,
    MissingConfigurationError,
    MissingRequiredFieldError,
    PlatformConnectionError,
    PlatformEndpointNotConfiguredError,
    PlatformError,
    PlatformNotFoundError,
    PriorAuthorizationError,
    PriorAuthRequiredError,
    QuestionnaireNotFoundError,
    ResourceNotFoundError,
    TokenExpiredError,
    ValidationError,
)


class TestFHIRGatewayError:
    """Tests for base error class."""

    def test_message(self):
        """Should store message."""
        error = FHIRGatewayError("Test error")
        assert error.message == "Test error"
        assert str(error) == "Test error"

    def test_details(self):
        """Should store details."""
        error = FHIRGatewayError("Test", details={"key": "value"})
        assert error.details == {"key": "value"}

    def test_default_details(self):
        """Should have empty details by default."""
        error = FHIRGatewayError("Test")
        assert error.details == {}

    def test_to_dict(self):
        """Should convert to dictionary."""
        error = FHIRGatewayError("Test error", details={"foo": "bar"})
        result = error.to_dict()

        assert result["error"] == "FHIRGatewayError"
        assert result["message"] == "Test error"
        assert result["details"] == {"foo": "bar"}


class TestAuthenticationErrors:
    """Tests for authentication error classes."""

    def test_authentication_error(self):
        """Should inherit from base error."""
        error = AuthenticationError("Auth failed")
        assert isinstance(error, FHIRGatewayError)
        assert error.message == "Auth failed"

    def test_token_expired_error_default_message(self):
        """Should have default message."""
        error = TokenExpiredError()
        assert "expired" in error.message.lower()

    def test_token_expired_error_custom_message(self):
        """Should accept custom message."""
        error = TokenExpiredError("Custom message")
        assert error.message == "Custom message"

    def test_insufficient_scope_error(self):
        """Should include required scopes."""
        error = InsufficientScopeError(["patient/*.read", "user/*.read"])
        assert "patient/*.read" in error.message
        assert error.required_scopes == ["patient/*.read", "user/*.read"]
        assert error.details["required_scopes"] == ["patient/*.read", "user/*.read"]

    def test_insufficient_scope_error_custom_message(self):
        """Should accept custom message."""
        error = InsufficientScopeError(["scope1"], message="Custom")
        assert error.message == "Custom"


class TestPlatformErrors:
    """Tests for platform error classes."""

    def test_platform_not_found_with_id(self):
        """Should include platform ID."""
        error = PlatformNotFoundError(platform_id="aetna")
        assert "aetna" in error.message
        assert error.platform_id == "aetna"

    def test_platform_not_found_with_name(self):
        """Should include platform name."""
        error = PlatformNotFoundError(platform_name="Aetna Insurance")
        assert "Aetna Insurance" in error.message
        assert error.platform_name == "Aetna Insurance"

    def test_platform_not_found_generic(self):
        """Should have generic message."""
        error = PlatformNotFoundError()
        assert "not found" in error.message.lower()

    def test_platform_endpoint_not_configured(self):
        """Should include platform ID."""
        error = PlatformEndpointNotConfiguredError("cigna")
        assert "cigna" in error.message
        assert error.platform_id == "cigna"

    def test_platform_endpoint_not_configured_with_portal(self):
        """Should include developer portal."""
        error = PlatformEndpointNotConfiguredError(
            "cigna", developer_portal="https://developer.cigna.com"
        )
        assert "developer.cigna.com" in error.message
        assert error.developer_portal == "https://developer.cigna.com"

    def test_platform_connection_error(self):
        """Should include connection details."""
        error = PlatformConnectionError(
            platform_id="aetna",
            endpoint="https://fhir.aetna.com",
            original_error="Connection refused",
        )
        assert "fhir.aetna.com" in error.message
        assert error.details["original_error"] == "Connection refused"


class TestCoverageErrors:
    """Tests for coverage error classes."""

    def test_coverage_not_found_with_id(self):
        """Should include coverage ID."""
        error = CoverageNotFoundError(patient_id="patient-123", coverage_id="cov-456")
        assert "cov-456" in error.message
        assert "patient-123" in error.message

    def test_coverage_not_found_without_id(self):
        """Should have generic message."""
        error = CoverageNotFoundError(patient_id="patient-123")
        assert "patient-123" in error.message
        assert "active" in error.message.lower()

    def test_coverage_inactive_error(self):
        """Should include status."""
        error = CoverageInactiveError(coverage_id="cov-123", status="cancelled")
        assert "cancelled" in error.message
        assert error.status == "cancelled"

    def test_prior_auth_required_error(self):
        """Should include procedure and platform."""
        error = PriorAuthRequiredError(
            procedure_code="27447",
            platform_name="Aetna",
            documentation_requirements=["X-ray", "MRI"],
        )
        assert "27447" in error.message
        assert "Aetna" in error.message
        assert error.documentation_requirements == ["X-ray", "MRI"]

    def test_questionnaire_not_found_error(self):
        """Should include procedure and platform."""
        error = QuestionnaireNotFoundError(procedure_code="99213", platform_id="cigna")
        assert "99213" in error.message
        assert "cigna" in error.message


class TestFHIRResourceErrors:
    """Tests for FHIR resource error classes."""

    def test_resource_not_found_error(self):
        """Should include resource type and ID."""
        error = ResourceNotFoundError(resource_type="Patient", resource_id="123")
        assert "Patient/123" in error.message
        assert error.resource_type == "Patient"
        assert error.resource_id == "123"

    def test_invalid_resource_error(self):
        """Should include validation errors."""
        error = InvalidResourceError(
            resource_type="Observation",
            validation_errors=["Missing code", "Invalid value"],
        )
        assert "Observation" in error.message
        assert error.validation_errors == ["Missing code", "Invalid value"]


class TestValidationErrors:
    """Tests for validation error classes."""

    def test_invalid_procedure_code_basic(self):
        """Should include procedure code."""
        error = InvalidProcedureCodeError("invalid-code")
        assert "invalid-code" in error.message

    def test_invalid_procedure_code_with_system(self):
        """Should include code system."""
        error = InvalidProcedureCodeError("ABC", code_system="CPT", reason="Unknown code")
        assert "CPT" in error.message
        assert "Unknown code" in error.message

    def test_invalid_patient_id_error(self):
        """Should include patient ID and reason."""
        error = InvalidPatientIdError("bad-id", reason="Invalid format")
        assert "bad-id" in error.message
        assert "Invalid format" in error.message

    def test_missing_required_field_error(self):
        """Should include field name."""
        error = MissingRequiredFieldError("patient_id")
        assert "patient_id" in error.message

    def test_missing_required_field_with_operation(self):
        """Should include operation name."""
        error = MissingRequiredFieldError("resource", operation="create")
        assert "resource" in error.message
        assert "create" in error.message


class TestConfigurationErrors:
    """Tests for configuration error classes."""

    def test_missing_configuration_error(self):
        """Should include config key."""
        error = MissingConfigurationError("REDIS_URL")
        assert "REDIS_URL" in error.message

    def test_missing_configuration_with_description(self):
        """Should include description."""
        error = MissingConfigurationError("MASTER_KEY", description="Required for encryption")
        assert "Required for encryption" in error.message


class TestErrorHierarchy:
    """Tests for error class hierarchy."""

    def test_all_inherit_from_base(self):
        """All errors should inherit from FHIRGatewayError."""
        errors = [
            AuthenticationError("test"),
            PlatformError("test"),
            CoverageError("test"),
            FHIRResourceError("test"),
            ValidationError("test"),
            ConfigurationError("test"),
        ]

        for error in errors:
            assert isinstance(error, FHIRGatewayError)

    def test_token_expired_is_auth_error(self):
        """TokenExpiredError should be AuthenticationError."""
        error = TokenExpiredError()
        assert isinstance(error, AuthenticationError)
        assert isinstance(error, FHIRGatewayError)

    def test_prior_auth_is_coverage_error(self):
        """PriorAuthorizationError should be CoverageError."""
        error = PriorAuthRequiredError("code", "payer")
        assert isinstance(error, PriorAuthorizationError)
        assert isinstance(error, CoverageError)
        assert isinstance(error, FHIRGatewayError)
