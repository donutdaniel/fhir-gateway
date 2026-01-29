"""
Shared validation utilities for router endpoints.

Converts validation errors to appropriate HTTP exceptions.
"""

from fastapi import HTTPException
from fhirpy.base.exceptions import OperationOutcome, ResourceNotFound

from app.audit import AuditEvent, audit_log
from app.errors import PlatformNotConfiguredError, PlatformNotFoundError
from app.validation import ValidationError
from app.validation import validate_operation as _validate_operation
from app.validation import validate_platform_id as _validate_platform_id
from app.validation import validate_procedure_code as _validate_procedure_code
from app.validation import validate_resource_id as _validate_resource_id
from app.validation import validate_resource_type as _validate_resource_type


def validate_platform_id(platform_id: str) -> None:
    """
    Validate platform ID format and existence.

    Raises:
        HTTPException: 400 for invalid format, 404 for platform not found
    """
    try:
        _validate_platform_id(platform_id)
    except ValidationError as e:
        # Platform not found should be 404, format errors should be 400
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


def validate_resource_type(resource_type: str) -> None:
    """
    Validate FHIR resource type format.

    Raises:
        HTTPException: 400 for invalid format
    """
    try:
        _validate_resource_type(resource_type)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


def validate_resource_id(resource_id: str, field_name: str = "resource_id") -> None:
    """
    Validate FHIR resource ID format.

    Args:
        resource_id: The resource ID to validate
        field_name: Name of the field for error messages

    Raises:
        HTTPException: 400 for invalid format
    """
    try:
        _validate_resource_id(resource_id)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {str(e)}")


def validate_procedure_code(code: str, code_system: str) -> None:
    """
    Validate procedure code format.

    Raises:
        HTTPException: 400 for invalid format
    """
    try:
        _validate_procedure_code(code, code_system)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


def validate_operation(operation: str) -> None:
    """
    Validate FHIR operation name.

    Raises:
        HTTPException: 400 for invalid format or disallowed operation
    """
    try:
        _validate_operation(operation)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


def handle_platform_error(e: Exception, platform_id: str | None = None) -> None:
    """
    Convert platform errors to HTTP exceptions with audit logging.

    Raises:
        HTTPException: 404 for not found, 503 for not configured, 500 for other errors
    """
    if isinstance(e, PlatformNotFoundError):
        audit_log(
            AuditEvent.PLATFORM_ERROR,
            platform_id=platform_id or getattr(e, "platform_id", None),
            success=False,
            error="platform_not_found",
        )
        raise HTTPException(status_code=404, detail=str(e))

    if isinstance(e, PlatformNotConfiguredError):
        audit_log(
            AuditEvent.PLATFORM_ERROR,
            platform_id=platform_id or getattr(e, "platform_id", None),
            success=False,
            error="platform_not_configured",
        )
        raise HTTPException(status_code=503, detail=str(e))

    audit_log(
        AuditEvent.COVERAGE_ERROR,
        platform_id=platform_id,
        success=False,
        error=str(e),
    )
    raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")


def handle_fhir_error(
    e: Exception,
    platform_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> None:
    """
    Convert FHIR operation errors to HTTP exceptions with audit logging.

    Handles platform errors plus FHIR-specific errors like ResourceNotFound.

    Raises:
        HTTPException: appropriate status code for the error type
    """
    if isinstance(e, PlatformNotFoundError):
        audit_log(
            AuditEvent.PLATFORM_ERROR,
            platform_id=platform_id or getattr(e, "platform_id", None),
            success=False,
            error="platform_not_found",
        )
        raise HTTPException(status_code=404, detail=str(e))

    if isinstance(e, PlatformNotConfiguredError):
        audit_log(
            AuditEvent.PLATFORM_ERROR,
            platform_id=platform_id or getattr(e, "platform_id", None),
            success=False,
            error="platform_not_configured",
        )
        raise HTTPException(status_code=503, detail=str(e))

    if isinstance(e, ResourceNotFound):
        audit_log(
            AuditEvent.RESOURCE_ACCESS_ERROR,
            platform_id=platform_id,
            resource_type=resource_type,
            resource_id=resource_id,
            success=False,
            error="resource_not_found",
        )
        raise HTTPException(status_code=404, detail="Resource not found")

    if isinstance(e, OperationOutcome):
        audit_log(
            AuditEvent.RESOURCE_ACCESS_ERROR,
            platform_id=platform_id,
            resource_type=resource_type,
            resource_id=resource_id,
            success=False,
            error="operation_outcome",
            details={"message": str(e)},
        )
        raise HTTPException(status_code=422, detail=str(e))

    audit_log(
        AuditEvent.RESOURCE_ACCESS_ERROR,
        platform_id=platform_id,
        resource_type=resource_type,
        resource_id=resource_id,
        success=False,
        error=str(e),
    )
    raise HTTPException(status_code=500, detail=f"FHIR operation failed: {str(e)}")
