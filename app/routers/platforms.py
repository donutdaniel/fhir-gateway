"""
Platform information endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.config.platform import get_all_platforms, get_platform
from app.models.platform import (
    PlatformCapabilitiesResponse,
    PlatformDetailResponse,
    PlatformInfo,
    PlatformListResponse,
)

router = APIRouter(prefix="/api/platforms", tags=["platforms"])


@router.get("", response_model=PlatformListResponse)
async def list_platforms(
    registered_only: Annotated[
        bool,
        Query(
            description="If true, only return platforms with OAuth credentials configured"
        ),
    ] = False,
) -> PlatformListResponse:
    """
    List all available platforms.

    Returns basic information about all registered platforms.
    Use registered_only=true to filter to only platforms with OAuth credentials configured.
    """
    all_platforms = get_all_platforms()

    platforms = []
    for platform_id, platform in all_platforms.items():
        has_oauth = bool(platform.oauth and platform.oauth.authorize_url)
        oauth_registered = bool(platform.oauth and platform.oauth.is_registered)

        # Skip unregistered platforms if filter is enabled
        if registered_only and not oauth_registered:
            continue

        platforms.append(
            PlatformInfo(
                id=platform_id,
                name=platform.display_name or platform.name,
                type=platform.type,
                fhir_base_url=platform.fhir_base_url,
                developer_portal=platform.developer_portal,
                has_oauth=has_oauth,
                oauth_registered=oauth_registered,
                verification_status=platform.verification_status,
            )
        )

    # Sort by name
    platforms.sort(key=lambda p: p.name or p.id)

    return PlatformListResponse(
        platforms=platforms,
        total=len(platforms),
    )


@router.get("/{platform_id}", response_model=PlatformDetailResponse)
async def get_platform_details(platform_id: str) -> PlatformDetailResponse:
    """
    Get detailed information about a specific platform.

    Args:
        platform_id: The platform identifier
    """
    platform = get_platform(platform_id)
    if not platform:
        raise HTTPException(
            status_code=404,
            detail=f"Platform '{platform_id}' not found",
        )

    capabilities = PlatformCapabilitiesResponse(
        patient_access=platform.capabilities.patient_access,
        provider_directory=platform.capabilities.provider_directory,
        patient_everything=platform.capabilities.patient_everything,
        bulk_data=platform.capabilities.bulk_data,
    )

    return PlatformDetailResponse(
        id=platform.id,
        name=platform.name,
        display_name=platform.display_name,
        type=platform.type,
        fhir_base_url=platform.fhir_base_url,
        sandbox_url=platform.sandbox_url,
        developer_portal=platform.developer_portal,
        support_email=platform.support_email,
        fhir_version=platform.fhir_version,
        capabilities=capabilities,
        has_oauth=bool(platform.oauth and platform.oauth.authorize_url),
        oauth_registered=bool(platform.oauth and platform.oauth.is_registered),
        oauth_authorize_url=platform.oauth.authorize_url if platform.oauth else None,
        verification_status=platform.verification_status,
    )
