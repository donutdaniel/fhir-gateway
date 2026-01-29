"""
Input validation helpers for MCP tools.

These are lightweight validators that return error messages (or None if valid).
They complement the more comprehensive validation in app.validation.
"""

import re

RESOURCE_TYPE_PATTERN = re.compile(r"^[A-Z][A-Za-z]+$")
PLATFORM_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-_]+$")
RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-\.]{1,64}$")


def validate_resource_type(resource_type: str) -> str | None:
    """Validate resource type, return error message if invalid."""
    if not resource_type or not RESOURCE_TYPE_PATTERN.match(resource_type.strip()):
        return f"Invalid resource type '{resource_type}'. Must be PascalCase (e.g., Patient, Observation)."
    return None


def validate_platform_id(platform_id: str) -> str | None:
    """Validate platform ID, return error message if invalid."""
    if not platform_id or not PLATFORM_ID_PATTERN.match(platform_id.strip()):
        return f"Invalid platform_id '{platform_id}'. Must be alphanumeric with hyphens/underscores."
    return None


def validate_resource_id(resource_id: str) -> str | None:
    """Validate resource ID, return error message if invalid."""
    if not resource_id or not RESOURCE_ID_PATTERN.match(resource_id.strip()):
        return f"Invalid resource_id '{resource_id}'. Must be 1-64 alphanumeric characters."
    return None
