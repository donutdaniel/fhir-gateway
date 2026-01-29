"""
FHIR client factory with platform routing.

This module provides functions to create FHIR clients that route
requests to platform-specific endpoints.
"""

from typing import Any

import aiohttp
from fhirpy import AsyncFHIRClient

from app.config.logging import get_logger
from app.config.platform import get_platform
from app.config.settings import get_settings
from app.errors import PlatformNotConfiguredError, PlatformNotFoundError

logger = get_logger(__name__)


class FHIRClientError(Exception):
    """Error creating or using FHIR client."""

    pass


class FHIRClientFactory:
    """Factory for creating platform-routed FHIR clients."""

    @classmethod
    def get_client(
        cls,
        platform_id: str,
        access_token: str | None = None,
        timeout: float | None = None,
    ) -> AsyncFHIRClient:
        """
        Get or create a FHIR client for a platform.

        Args:
            platform_id: The platform identifier
            access_token: Optional OAuth access token
            timeout: Request timeout in seconds

        Returns:
            AsyncFHIRClient configured for the platform

        Raises:
            PlatformNotFoundError: If platform is not registered
            PlatformNotConfiguredError: If platform has no FHIR URL
        """
        platform = get_platform(platform_id)
        if not platform:
            raise PlatformNotFoundError(platform_id)

        if not platform.fhir_base_url:
            raise PlatformNotConfiguredError(platform_id)

        settings = get_settings()
        timeout_val = timeout or settings.request_timeout

        # Build client kwargs
        client_kwargs: dict[str, Any] = {
            "url": platform.fhir_base_url,
            "aiohttp_config": {
                "timeout": aiohttp.ClientTimeout(total=timeout_val),
            },
            "extra_headers": {
                "Accept": "application/fhir+json",
                "Content-Type": "application/fhir+json",
            },
        }

        # Add custom headers from platform config
        if platform.client_headers:
            client_kwargs["extra_headers"].update(platform.client_headers)

        # Add authorization if provided
        if access_token:
            client_kwargs["authorization"] = f"Bearer {access_token}"

        logger.debug(f"Creating FHIR client for platform {platform_id} -> {platform.fhir_base_url}")
        return AsyncFHIRClient(**client_kwargs)


def get_fhir_client(
    platform_id: str,
    access_token: str | None = None,
    timeout: float | None = None,
) -> AsyncFHIRClient:
    """
    Get a FHIR client for a platform.

    This is the main entry point for obtaining FHIR clients.
    Each call returns a new client instance.

    Args:
        platform_id: The platform identifier
        access_token: Optional OAuth access token
        timeout: Request timeout in seconds

    Returns:
        AsyncFHIRClient configured for the platform

    Raises:
        PlatformNotFoundError: If platform is not registered
        PlatformNotConfiguredError: If platform has no FHIR URL
    """
    return FHIRClientFactory.get_client(
        platform_id=platform_id,
        access_token=access_token,
        timeout=timeout,
    )


async def fetch_capability_statement(
    platform_id: str,
    access_token: str | None = None,
    resource_type: str | None = None,
) -> dict[str, Any]:
    """
    Fetch the CapabilityStatement from a platform's FHIR server.

    Args:
        platform_id: The platform identifier
        access_token: Optional OAuth access token
        resource_type: Optional resource type to filter capabilities

    Returns:
        CapabilityStatement resource or filtered capabilities
    """
    platform = get_platform(platform_id)
    if not platform:
        raise PlatformNotFoundError(platform_id)

    if not platform.fhir_base_url:
        raise PlatformNotConfiguredError(platform_id)

    # Fetch metadata directly using aiohttp since fhirpy doesn't have a clean metadata method
    settings = get_settings()
    timeout_val = settings.request_timeout

    headers = {
        "Accept": "application/fhir+json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    url = f"{platform.fhir_base_url.rstrip('/')}/metadata"

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout_val)) as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise FHIRClientError(f"Failed to fetch metadata: {resp.status} - {error_text}")
            capability = await resp.json()

    if not resource_type:
        return capability

    # Filter to specific resource type
    rest_list = capability.get("rest", [])
    if not rest_list:
        return capability

    server_rest = rest_list[0]
    resources = server_rest.get("resource", [])

    for resource in resources:
        if resource.get("type") == resource_type:
            return {
                "resourceType": "CapabilityStatement",
                "resource": resource,
                "searchParam": resource.get("searchParam", []),
                "operation": resource.get("operation", []),
                "interaction": resource.get("interaction", []),
            }

    return {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "warning",
                "code": "not-found",
                "diagnostics": f"Resource type '{resource_type}' not found in CapabilityStatement",
            }
        ],
    }


async def search_resources(
    platform_id: str,
    resource_type: str,
    search_params: dict[str, Any] | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """
    Search for FHIR resources.

    Args:
        platform_id: The platform identifier
        resource_type: FHIR resource type
        search_params: Search parameters
        access_token: Optional OAuth access token

    Returns:
        FHIR Bundle with search results
    """
    client = get_fhir_client(platform_id, access_token)

    search = client.resources(resource_type)
    if search_params:
        search = search.search(**search_params)

    resources = await search.fetch()

    entries = []
    for resource in resources:
        entries.append(
            {
                "fullUrl": f"{resource_type}/{resource.get('id', '')}",
                "resource": resource,
                "search": {"mode": "match"},
            }
        )

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries,
    }
