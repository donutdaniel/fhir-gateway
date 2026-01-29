"""
Custom error types for the FHIR Gateway.

This module provides specific error classes for different failure scenarios,
enabling better error handling and more informative error messages.
"""

from typing import Any


class FHIRGatewayError(Exception):
    """Base exception for all FHIR Gateway errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# Authentication and Authorization Errors


class AuthenticationError(FHIRGatewayError):
    """Raised when authentication fails."""

    pass


class TokenExpiredError(AuthenticationError):
    """Raised when an access token has expired."""

    def __init__(self, message: str = "Access token has expired"):
        super().__init__(message)


class InsufficientScopeError(AuthenticationError):
    """Raised when the token lacks required scopes."""

    def __init__(self, required_scopes: list, message: str | None = None):
        self.required_scopes = required_scopes
        msg = message or f"Insufficient scopes. Required: {', '.join(required_scopes)}"
        super().__init__(msg, details={"required_scopes": required_scopes})


# Platform and Adapter Errors


class PlatformError(FHIRGatewayError):
    """Base exception for platform-related errors."""

    pass


class PlatformNotFoundError(PlatformError):
    """Raised when a platform cannot be identified or found."""

    def __init__(self, platform_id: str | None = None, platform_name: str | None = None):
        self.platform_id = platform_id
        self.platform_name = platform_name
        message = "Platform not found"
        if platform_id:
            message = f"Platform not found: {platform_id}"
        elif platform_name:
            message = f"Platform not found by name: {platform_name}"
        super().__init__(message, details={"platform_id": platform_id, "platform_name": platform_name})


class PlatformEndpointNotConfiguredError(PlatformError):
    """Raised when a platform's FHIR endpoint is not configured."""

    def __init__(self, platform_id: str, developer_portal: str | None = None):
        self.platform_id = platform_id
        self.developer_portal = developer_portal
        message = f"FHIR endpoint not configured for platform: {platform_id}"
        if developer_portal:
            message += f". Register at: {developer_portal}"
        super().__init__(
            message,
            details={"platform_id": platform_id, "developer_portal": developer_portal},
        )


class PlatformConnectionError(PlatformError):
    """Raised when connection to a platform's FHIR endpoint fails."""

    def __init__(self, platform_id: str, endpoint: str, original_error: str | None = None):
        self.platform_id = platform_id
        self.endpoint = endpoint
        message = f"Failed to connect to platform endpoint: {endpoint}"
        super().__init__(
            message,
            details={
                "platform_id": platform_id,
                "endpoint": endpoint,
                "original_error": original_error,
            },
        )


# Coverage and Prior Authorization Errors


class CoverageError(FHIRGatewayError):
    """Base exception for coverage-related errors."""

    pass


class CoverageNotFoundError(CoverageError):
    """Raised when coverage cannot be found for a patient."""

    def __init__(self, patient_id: str, coverage_id: str | None = None):
        self.patient_id = patient_id
        self.coverage_id = coverage_id
        if coverage_id:
            message = f"Coverage not found: {coverage_id} for patient: {patient_id}"
        else:
            message = f"No active coverage found for patient: {patient_id}"
        super().__init__(
            message,
            details={"patient_id": patient_id, "coverage_id": coverage_id},
        )


class CoverageInactiveError(CoverageError):
    """Raised when coverage exists but is not active."""

    def __init__(self, coverage_id: str, status: str):
        self.coverage_id = coverage_id
        self.status = status
        message = f"Coverage {coverage_id} is not active (status: {status})"
        super().__init__(
            message,
            details={"coverage_id": coverage_id, "status": status},
        )


class PriorAuthorizationError(CoverageError):
    """Base exception for prior authorization errors."""

    pass


class PriorAuthRequiredError(PriorAuthorizationError):
    """Raised when prior authorization is required for a procedure."""

    def __init__(
        self,
        procedure_code: str,
        platform_name: str,
        documentation_requirements: list | None = None,
    ):
        self.procedure_code = procedure_code
        self.platform_name = platform_name
        self.documentation_requirements = documentation_requirements or []
        message = f"Prior authorization required for {procedure_code} from {platform_name}"
        super().__init__(
            message,
            details={
                "procedure_code": procedure_code,
                "platform_name": platform_name,
                "documentation_requirements": documentation_requirements,
            },
        )


class QuestionnaireNotFoundError(PriorAuthorizationError):
    """Raised when a questionnaire for prior auth cannot be found."""

    def __init__(self, procedure_code: str, platform_id: str):
        self.procedure_code = procedure_code
        self.platform_id = platform_id
        message = f"No questionnaire found for procedure {procedure_code} from platform {platform_id}"
        super().__init__(
            message,
            details={"procedure_code": procedure_code, "platform_id": platform_id},
        )


# FHIR Resource Errors


class FHIRResourceError(FHIRGatewayError):
    """Base exception for FHIR resource errors."""

    pass


class ResourceNotFoundError(FHIRResourceError):
    """Raised when a FHIR resource cannot be found."""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        message = f"{resource_type}/{resource_id} not found"
        super().__init__(
            message,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class InvalidResourceError(FHIRResourceError):
    """Raised when a FHIR resource is invalid."""

    def __init__(self, resource_type: str, validation_errors: list):
        self.resource_type = resource_type
        self.validation_errors = validation_errors
        message = f"Invalid {resource_type} resource"
        super().__init__(
            message,
            details={
                "resource_type": resource_type,
                "validation_errors": validation_errors,
            },
        )


# Input Validation Errors


class ValidationError(FHIRGatewayError):
    """Base exception for input validation errors."""

    pass


class InvalidProcedureCodeError(ValidationError):
    """Raised when a procedure code is invalid."""

    def __init__(
        self,
        procedure_code: str,
        code_system: str | None = None,
        reason: str | None = None,
    ):
        self.procedure_code = procedure_code
        self.code_system = code_system
        message = f"Invalid procedure code: {procedure_code}"
        if code_system:
            message += f" (system: {code_system})"
        if reason:
            message += f". {reason}"
        super().__init__(
            message,
            details={
                "procedure_code": procedure_code,
                "code_system": code_system,
                "reason": reason,
            },
        )


class InvalidPatientIdError(ValidationError):
    """Raised when a patient ID is invalid."""

    def __init__(self, patient_id: str, reason: str | None = None):
        self.patient_id = patient_id
        message = f"Invalid patient ID: {patient_id}"
        if reason:
            message += f". {reason}"
        super().__init__(
            message,
            details={"patient_id": patient_id, "reason": reason},
        )


class MissingRequiredFieldError(ValidationError):
    """Raised when a required field is missing."""

    def __init__(self, field_name: str, operation: str | None = None):
        self.field_name = field_name
        self.operation = operation
        message = f"Missing required field: {field_name}"
        if operation:
            message = f"Missing required field '{field_name}' for {operation}"
        super().__init__(
            message,
            details={"field_name": field_name, "operation": operation},
        )


# Configuration Errors


class ConfigurationError(FHIRGatewayError):
    """Raised when there's a configuration error."""

    pass


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""

    def __init__(self, config_key: str, description: str | None = None):
        self.config_key = config_key
        message = f"Missing required configuration: {config_key}"
        if description:
            message += f". {description}"
        super().__init__(
            message,
            details={"config_key": config_key, "description": description},
        )
