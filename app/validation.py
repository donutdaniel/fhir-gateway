"""
Input validation for FHIR Gateway.

Provides validation functions for platform IDs, resource types, and other inputs.
"""

import re

from app.config.platform import get_platform

# Validation patterns
RESOURCE_TYPE_PATTERN = re.compile(r"^[A-Z][A-Za-z]+$")
RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-\.]{1,64}$")
PLATFORM_ID_PATTERN = re.compile(r"^[a-z][a-z0-9\-]+$")
PROCEDURE_CODE_PATTERN = re.compile(r"^[A-Z0-9]{3,10}$")

# Allowed FHIR operations
ALLOWED_OPERATIONS = frozenset({
    "$everything",
    "$validate",
    "$summary",
    "$document",
    "$expand",
    "$lookup",
    "$translate",
    "$subsumes",
    "$closure",
    "$process-message",
    "$evaluate-measure",
    "$submit-data",
    "$collect-data",
})


class ValidationError(ValueError):
    """Validation error with details."""

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)


def validate_resource_type(resource_type: str) -> str:
    """
    Validate FHIR resource type format.

    Args:
        resource_type: Resource type string to validate

    Returns:
        The validated resource type

    Raises:
        ValidationError: If format is invalid
    """
    if not resource_type:
        raise ValidationError("Resource type is required", field="resource_type")

    if not RESOURCE_TYPE_PATTERN.match(resource_type):
        raise ValidationError(
            f"Invalid resource type '{resource_type}'. "
            f"Must start with uppercase letter followed by letters only.",
            field="resource_type",
        )

    return resource_type


def validate_resource_id(resource_id: str) -> str:
    """
    Validate FHIR resource ID format.

    Args:
        resource_id: Resource ID string to validate

    Returns:
        The validated resource ID

    Raises:
        ValidationError: If format is invalid
    """
    if not resource_id:
        raise ValidationError("Resource ID is required", field="resource_id")

    if not RESOURCE_ID_PATTERN.match(resource_id):
        raise ValidationError(
            f"Invalid resource ID '{resource_id}'. "
            f"Must be 1-64 characters with letters, digits, hyphens, and dots.",
            field="resource_id",
        )

    return resource_id


def validate_platform_id(platform_id: str) -> str:
    """
    Validate platform ID exists and is properly formatted.

    Args:
        platform_id: Platform ID string to validate

    Returns:
        The validated platform ID

    Raises:
        ValidationError: If platform ID is invalid or not found
    """
    if not platform_id:
        raise ValidationError("Platform ID is required", field="platform_id")

    # Check format
    if not PLATFORM_ID_PATTERN.match(platform_id):
        raise ValidationError(
            f"Invalid platform ID format '{platform_id}'. "
            f"Must start with lowercase letter followed by lowercase letters, digits, and hyphens.",
            field="platform_id",
        )

    # Check if platform exists
    platform = get_platform(platform_id)
    if not platform:
        raise ValidationError(f"Platform '{platform_id}' not found", field="platform_id")

    return platform_id


def validate_procedure_code(
    code: str,
    code_system: str | None = None,
) -> str:
    """
    Validate procedure code format (CPT, HCPCS, ICD-10, SNOMED).

    Args:
        code: Procedure code to validate
        code_system: Optional code system URL for context

    Returns:
        The validated procedure code

    Raises:
        ValidationError: If format is invalid
    """
    if not code:
        raise ValidationError("Procedure code is required", field="procedure_code")

    # Normalize to uppercase
    code = code.upper()

    # Code system specific validation
    if code_system:
        if "cpt" in code_system.lower():
            # CPT codes: 5 digits
            if not re.match(r"^\d{5}$", code):
                raise ValidationError(
                    f"Invalid CPT code '{code}'. Must be 5 digits.",
                    field="procedure_code",
                )
        elif "hcpcs" in code_system.lower():
            # HCPCS codes: letter + 4 digits
            if not re.match(r"^[A-Z]\d{4}$", code):
                raise ValidationError(
                    f"Invalid HCPCS code '{code}'. Must be letter + 4 digits.",
                    field="procedure_code",
                )
        elif "icd" in code_system.lower():
            # ICD codes: alphanumeric with possible dots
            if not re.match(r"^[A-Z0-9]{3,7}\.?[A-Z0-9]*$", code):
                raise ValidationError(
                    f"Invalid ICD code '{code}'.",
                    field="procedure_code",
                )
        elif "snomed" in code_system.lower():
            # SNOMED codes: numeric
            if not re.match(r"^\d{6,18}$", code):
                raise ValidationError(
                    f"Invalid SNOMED code '{code}'.",
                    field="procedure_code",
                )
        else:
            # Generic validation
            if not PROCEDURE_CODE_PATTERN.match(code):
                raise ValidationError(
                    f"Invalid procedure code '{code}'. "
                    f"Must be 3-10 uppercase alphanumeric characters.",
                    field="procedure_code",
                )
    else:
        # Generic validation
        if not PROCEDURE_CODE_PATTERN.match(code):
            raise ValidationError(
                f"Invalid procedure code '{code}'. Must be 3-10 uppercase alphanumeric characters.",
                field="procedure_code",
            )

    return code


def validate_operation(operation: str) -> str:
    """
    Validate FHIR operation name.

    Args:
        operation: Operation name to validate

    Returns:
        The validated operation name

    Raises:
        ValidationError: If operation is not allowed
    """
    if not operation:
        raise ValidationError("Operation name is required", field="operation")

    # Must start with $
    if not operation.startswith("$"):
        raise ValidationError(
            f"Invalid operation '{operation}'. Operations must start with $.",
            field="operation",
        )

    if operation not in ALLOWED_OPERATIONS:
        raise ValidationError(
            f"Operation '{operation}' is not allowed. "
            f"Supported: {', '.join(sorted(ALLOWED_OPERATIONS))}",
            field="operation",
        )

    return operation
