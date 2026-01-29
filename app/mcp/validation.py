"""
Input validation helpers for MCP tools.

Thin wrappers around app.validation that return error messages instead of raising.
These only check format - existence checks are handled by the service layer.
"""

from app.validation import PLATFORM_ID_PATTERN, ValidationError
from app.validation import validate_resource_id as _validate_resource_id
from app.validation import validate_resource_type as _validate_resource_type


def validate_resource_type(resource_type: str) -> str | None:
    """Validate resource type, return error message if invalid."""
    try:
        _validate_resource_type(resource_type)
        return None
    except ValidationError as e:
        return str(e)


def validate_platform_id(platform_id: str) -> str | None:
    """
    Validate platform ID format only, return error message if invalid.

    Note: This only checks format, not existence. Existence is checked
    by the service layer which returns platform_not_found errors.
    """
    if not platform_id:
        return "Platform ID is required"

    if not PLATFORM_ID_PATTERN.match(platform_id):
        return (
            f"Invalid platform_id '{platform_id}'. "
            f"Must start with lowercase letter followed by lowercase letters, digits, and hyphens."
        )
    return None


def validate_resource_id(resource_id: str) -> str | None:
    """Validate resource ID, return error message if invalid."""
    try:
        _validate_resource_id(resource_id)
        return None
    except ValidationError as e:
        return str(e)
