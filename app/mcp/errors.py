"""
Error handling utilities for MCP tools.

Provides consistent error responses and exception handling.
"""

from typing import Any

from fhirpy.base.exceptions import OperationOutcome, ResourceNotFound

from app.config.logging import get_logger
from app.errors import PlatformNotConfiguredError, PlatformNotFoundError

logger = get_logger(__name__)


def error_response(code: str, message: str) -> dict[str, Any]:
    """Create a standardized error response."""
    return {"error": code, "message": message}


def handle_exception(e: Exception, operation: str) -> dict[str, Any]:
    """
    Handle exceptions consistently, sanitizing error messages.

    Returns a standardized error dict. Logs full error details internally
    but returns sanitized messages to clients.
    """
    if isinstance(e, PlatformNotFoundError):
        return error_response("platform_not_found", f"Platform '{e.platform_id}' not found")

    if isinstance(e, PlatformNotConfiguredError):
        return error_response(
            "platform_not_configured", f"Platform '{e.platform_id}' has no FHIR endpoint"
        )

    if isinstance(e, ResourceNotFound):
        return error_response("not_found", "Resource not found")

    if isinstance(e, OperationOutcome):
        return error_response("operation_outcome", "FHIR server returned an error")

    if isinstance(e, ValueError):
        # ValueError often contains user-facing messages
        return error_response("invalid_request", str(e))

    # Log full error but return sanitized message
    logger.exception(f"{operation} failed", exc_info=e)
    return error_response("internal_error", f"Operation failed: {operation}")
