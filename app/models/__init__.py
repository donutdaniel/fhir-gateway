"""
Pydantic models for FHIR Gateway.

This module contains models for:
- FHIR operations (requests/responses)
- Platform information
- OAuth tokens
"""

from app.models.auth import (
    AuthStatus,
    AuthStatusResponse,
    OAuthToken,
)
from app.models.fhir import (
    FHIROperationResponse,
    FHIRSearchParams,
)
from app.models.platform import (
    PlatformDetailResponse,
    PlatformInfo,
    PlatformListResponse,
)

__all__ = [
    "PlatformInfo",
    "PlatformListResponse",
    "PlatformDetailResponse",
    "FHIRSearchParams",
    "FHIROperationResponse",
    "OAuthToken",
    "AuthStatus",
    "AuthStatusResponse",
]
