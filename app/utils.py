"""
FHIR utility functions for bundle processing, capability handling, and resource extraction.
"""

import json
from typing import Any

import httpx

from app.config.logging import get_logger

logger = get_logger(__name__)

# Standard FHIR media type for JSON format
FHIR_JSON_CONTENT_TYPE = "application/fhir+json"


def extract_bearer_token(authorization: str | None) -> str | None:
    """
    Extract the bearer token from an Authorization header.

    Args:
        authorization: The Authorization header value (e.g., "Bearer eyJhbG...")

    Returns:
        The token string if present and valid, otherwise None
    """
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


def fhir_request_headers(
    accept: str = FHIR_JSON_CONTENT_TYPE,
    content_type: str | None = FHIR_JSON_CONTENT_TYPE,
) -> dict[str, str]:
    """
    Build HTTP headers for FHIR API requests.

    Args:
        accept: Accept header value for response format
        content_type: Content-Type header for request body (None to omit)

    Returns:
        Dictionary of HTTP headers for FHIR requests
    """
    headers = {"Accept": accept}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


async def extract_bundle_resources(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    Extract resources from a FHIR Bundle, unwrapping the entry wrapper objects.

    Takes a Bundle response and returns a simplified structure containing
    just the resources without the entry metadata (fullUrl, search, request, etc.).

    Args:
        bundle: A FHIR Bundle dictionary with optional 'entry' array

    Returns:
        Dictionary with 'entry' containing extracted resources,
        or the original bundle if no entries present
    """
    entries = bundle.get("entry") if bundle else None

    if not isinstance(entries, list) or not entries:
        return bundle

    resources = []
    for entry in entries:
        resource = entry.get("resource")
        if resource is not None:
            resources.append(resource)

    logger.debug("Extracted %d resources from bundle", len(resources))
    return {"entry": resources}


def truncate_fhir_response(
    response: dict[str, Any] | list[dict[str, Any]],
    max_entries: int = 50,
    max_chars: int = 100_000,
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Truncate a FHIR response to stay within size limits.

    Applies two limits:
    1. Max number of bundle entries (truncates entries list)
    2. Max serialized JSON character count (removes entries from the end until under limit)

    A '_truncated' metadata field is added when truncation occurs.

    Args:
        response: FHIR response dict or list
        max_entries: Maximum number of bundle entries to return
        max_chars: Maximum total JSON character count

    Returns:
        The response, possibly truncated with metadata indicating what was cut
    """
    if isinstance(response, list):
        # Raw list of resources (e.g., from search before bundle extraction)
        total = len(response)
        if total > max_entries:
            response = response[:max_entries]
            logger.info("Truncated response list from %d to %d entries", total, max_entries)

        serialized = json.dumps(response, default=str)
        if len(serialized) > max_chars:
            while len(response) > 1:
                response.pop()
                serialized = json.dumps(response, default=str)
                if len(serialized) <= max_chars:
                    break
            logger.info(
                "Truncated response list to %d entries to fit %d char limit",
                len(response),
                max_chars,
            )

        if len(response) < total:
            return {
                "_truncated": True,
                "_total_available": total,
                "_returned": len(response),
                "_message": f"Response truncated from {total} to {len(response)} entries. Use search parameters like _count, _offset, or more specific filters to narrow results.",
                "entry": response,
            }
        return response

    if not isinstance(response, dict):
        return response

    entries = response.get("entry")
    if not isinstance(entries, list):
        # No entries to truncate — still check overall size
        serialized = json.dumps(response, default=str)
        if len(serialized) > max_chars:
            return {
                "_truncated": True,
                "_message": "Response exceeded size limit and could not be truncated. Use more specific search parameters.",
                "resourceType": response.get("resourceType"),
                "total": response.get("total"),
            }
        return response

    total = len(entries)
    if total > max_entries:
        entries = entries[:max_entries]
        response = {**response, "entry": entries}

    serialized = json.dumps(response, default=str)
    if len(serialized) > max_chars:
        while len(entries) > 1:
            entries.pop()
            response = {**response, "entry": entries}
            serialized = json.dumps(response, default=str)
            if len(serialized) <= max_chars:
                break

    if len(entries) < total:
        response["_truncated"] = True
        response["_total_available"] = total
        response["_returned"] = len(entries)
        response["_message"] = (
            f"Response truncated from {total} to {len(entries)} entries. "
            "Use search parameters like _count, _offset, or more specific filters to narrow results."
        )
        logger.info("Truncated bundle from %d to %d entries", total, len(entries))

    return response


def simplify_search_params(
    search_params: list[dict[str, Any]],
) -> list[dict[str, str | None]]:
    """
    Reduce search parameter definitions to essential fields for display.

    Extracts only the name and documentation from each search parameter,
    filtering out parameters that lack both fields.

    Args:
        search_params: List of FHIR SearchParameter-like dictionaries

    Returns:
        List of simplified dictionaries with 'name' and 'documentation' keys
    """
    result = []
    for param in search_params:
        name = param.get("name")
        docs = param.get("documentation")

        if name is not None or docs is not None:
            result.append({"name": name, "documentation": docs})

    logger.debug("Simplified %d search params to %d entries", len(search_params), len(result))
    return result


def create_operation_outcome(
    code: str,
    diagnostics: str,
    severity: str = "error",
) -> dict[str, Any]:
    """
    Construct a FHIR OperationOutcome resource.

    Args:
        code: Issue type code (e.g., 'exception', 'required', 'not-found')
        diagnostics: Human-readable diagnostic message
        severity: Issue severity ('fatal', 'error', 'warning', 'information')

    Returns:
        A FHIR OperationOutcome resource dictionary
    """
    return {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": severity,
                "code": code,
                "diagnostics": diagnostics,
            }
        ],
    }


def operation_outcome_exception() -> dict[str, Any]:
    """Create an OperationOutcome for unexpected internal errors."""
    return create_operation_outcome(
        code="exception",
        diagnostics="An unexpected internal error has occurred.",
    )


def operation_outcome_missing_required(element: str = "") -> dict[str, Any]:
    """Create an OperationOutcome for missing required elements."""
    msg = (
        f"Required element '{element}' is missing." if element else "A required element is missing."
    )
    return create_operation_outcome(code="required", diagnostics=msg)


# Known safe exception types that can have their messages exposed to users
_SAFE_EXCEPTION_TYPES: tuple[type, ...] = (ValueError, KeyError)


def sanitize_error_for_user(error: Exception, operation: str = "operation") -> str:
    """
    Return a user-safe error message, hiding internal implementation details.

    This function sanitizes exception messages to avoid leaking sensitive
    information like stack traces, internal paths, or system details.

    Args:
        error: The exception that occurred
        operation: Name of the operation for the generic message

    Returns:
        A user-safe error message string
    """
    # Import here to avoid circular imports
    from app.adapters.registry import PlatformAdapterNotFoundError, PlatformNotConfiguredError

    # These exception types have user-friendly messages that are safe to expose
    safe_types = _SAFE_EXCEPTION_TYPES + (PlatformAdapterNotFoundError, PlatformNotConfiguredError)

    if isinstance(error, safe_types):
        return str(error)

    # Generic message for unexpected/unknown errors
    return f"An unexpected error occurred during {operation}. Please try again."


async def fetch_server_metadata(
    base_url: str,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """
    Retrieve the CapabilityStatement from a FHIR server's metadata endpoint.

    Args:
        base_url: FHIR server base URL (with or without trailing slash)
        timeout_seconds: Request timeout in seconds

    Returns:
        The CapabilityStatement resource as a dictionary

    Raises:
        ValueError: If the metadata endpoint cannot be reached or returns an error
    """
    endpoint = f"{base_url.rstrip('/')}/metadata"
    logger.debug("Requesting CapabilityStatement from %s", endpoint)

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.get(endpoint, headers=fhir_request_headers())
            resp.raise_for_status()
            capability_statement = resp.json()
            logger.debug(
                "Retrieved CapabilityStatement: fhirVersion=%s",
                capability_statement.get("fhirVersion", "unknown"),
            )
            return capability_statement

    except httpx.TimeoutException:
        logger.error("Timeout fetching metadata from %s", endpoint)
        raise ValueError(f"Timeout connecting to FHIR server: {base_url}") from None
    except httpx.HTTPStatusError as e:
        logger.error("HTTP %d from metadata endpoint: %s", e.response.status_code, endpoint)
        raise ValueError(f"FHIR server returned {e.response.status_code}") from None
    except Exception as e:
        logger.exception("Failed to fetch FHIR metadata from %s", endpoint)
        raise ValueError(f"Unable to fetch FHIR metadata: {e}") from None


# User profile field configuration
_USER_PROFILE_FIELDS = frozenset(
    {
        "id",
        "resourceType",
        "name",
        "gender",
        "birthDate",
        "telecom",
        "address",
    }
)


def extract_user_demographics(
    resource: dict[str, Any],
    additional_fields: list[str] | None = None,
) -> dict[str, Any]:
    """
    Extract demographic information from a FHIR Person/Patient/Practitioner resource.

    Pulls standard demographic fields from the resource, optionally including
    additional fields specified by the caller.

    Args:
        resource: A FHIR resource dictionary (typically Patient, Practitioner, or Person)
        additional_fields: Optional list of extra fields to include

    Returns:
        Dictionary containing only the requested fields that have values
    """
    fields_to_include = _USER_PROFILE_FIELDS
    if additional_fields:
        fields_to_include = fields_to_include | set(additional_fields)

    return {
        key: value
        for key, value in resource.items()
        if key in fields_to_include and value is not None
    }
