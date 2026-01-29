"""
FHIR utility functions for request handling and token extraction.
"""

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
