"""
FHIR REST API endpoints.

Provides FHIR operations with multi-platform routing:
- GET /api/fhir/{platform_id}/metadata - CapabilityStatement
- GET /api/fhir/{platform_id}/{resource_type} - Search
- GET /api/fhir/{platform_id}/{resource_type}/{id} - Read
- POST /api/fhir/{platform_id}/{resource_type} - Create
- PUT /api/fhir/{platform_id}/{resource_type}/{id} - Update
- DELETE /api/fhir/{platform_id}/{resource_type}/{id} - Delete
"""

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fhirpy.base.exceptions import OperationOutcome, ResourceNotFound

from app.audit import AuditEvent, audit_log
from app.services.fhir_client import (
    PlatformNotConfiguredError,
    PlatformNotFoundError,
    fetch_capability_statement,
    get_fhir_client,
)
from app.utils import extract_bearer_token
from app.validation import (
    ValidationError,
)
from app.validation import (
    validate_operation as _validate_operation,
)
from app.validation import (
    validate_platform_id as _validate_platform_id,
)
from app.validation import (
    validate_resource_id as _validate_resource_id,
)
from app.validation import (
    validate_resource_type as _validate_resource_type,
)

router = APIRouter(prefix="/api/fhir", tags=["fhir"])


def validate_resource_type(resource_type: str) -> None:
    """Validate FHIR resource type format."""
    try:
        _validate_resource_type(resource_type)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


def validate_resource_id(resource_id: str) -> None:
    """Validate FHIR resource ID format."""
    try:
        _validate_resource_id(resource_id)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


def validate_platform_id(platform_id: str) -> None:
    """Validate platform ID format and existence."""
    try:
        _validate_platform_id(platform_id)
    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))


def handle_fhir_error(e: Exception, platform_id: str) -> None:
    """Convert FHIR errors to HTTP exceptions."""
    if isinstance(e, PlatformNotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, PlatformNotConfiguredError):
        raise HTTPException(status_code=503, detail=str(e))
    if isinstance(e, ResourceNotFound):
        raise HTTPException(status_code=404, detail="Resource not found")
    if isinstance(e, OperationOutcome):
        raise HTTPException(status_code=422, detail=str(e))
    raise HTTPException(status_code=500, detail=f"FHIR operation failed: {str(e)}")


@router.get("/{platform_id}/metadata")
async def get_metadata(
    platform_id: str,
    resource_type: str | None = Query(None, description="Filter to specific resource type"),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Fetch CapabilityStatement from platform's FHIR server.

    Args:
        platform_id: The platform identifier
        resource_type: Optional resource type to filter capabilities
        authorization: Optional Bearer token
    """
    validate_platform_id(platform_id)

    access_token = extract_bearer_token(authorization)

    try:
        return await fetch_capability_statement(
            platform_id=platform_id,
            access_token=access_token,
            resource_type=resource_type,
        )
    except Exception as e:
        handle_fhir_error(e, platform_id)


@router.get("/{platform_id}/{resource_type}")
async def search_resources(
    platform_id: str,
    resource_type: str,
    request: Request,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Search for FHIR resources.

    All query parameters are passed as FHIR search parameters.

    Args:
        platform_id: The platform identifier
        resource_type: FHIR resource type (e.g., Patient, Observation)
        authorization: Optional Bearer token
    """
    validate_resource_type(resource_type)

    access_token = extract_bearer_token(authorization)

    # Get all query params as search params
    search_params = dict(request.query_params)

    try:
        client = get_fhir_client(platform_id, access_token)
        search = client.resources(resource_type)

        if search_params:
            search = search.search(**search_params)

        resources = await search.fetch()

        # Return as a Bundle
        entries = []
        for resource in resources:
            entries.append(
                {
                    "fullUrl": f"{resource_type}/{resource.get('id', '')}",
                    "resource": resource,
                    "search": {"mode": "match"},
                }
            )

        audit_log(
            AuditEvent.RESOURCE_SEARCH,
            platform_id=platform_id,
            resource_type=resource_type,
            details={"count": len(entries)},
        )

        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": len(entries),
            "entry": entries,
        }

    except Exception as e:
        handle_fhir_error(e, platform_id)


@router.get("/{platform_id}/{resource_type}/{resource_id}")
async def read_resource(
    platform_id: str,
    resource_type: str,
    resource_id: str,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Read a specific FHIR resource by ID.

    Args:
        platform_id: The platform identifier
        resource_type: FHIR resource type
        resource_id: Resource ID
        authorization: Optional Bearer token
    """
    validate_resource_type(resource_type)
    validate_resource_id(resource_id)

    access_token = extract_bearer_token(authorization)

    try:
        client = get_fhir_client(platform_id, access_token)
        resource = await client.get(resource_type, resource_id)

        audit_log(
            AuditEvent.RESOURCE_READ,
            platform_id=platform_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )

        return resource

    except Exception as e:
        handle_fhir_error(e, platform_id)


@router.get("/{platform_id}/{resource_type}/{resource_id}/{operation}")
async def execute_operation(
    platform_id: str,
    resource_type: str,
    resource_id: str,
    operation: str,
    request: Request,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Execute a FHIR operation on a resource (e.g., $everything).

    Args:
        platform_id: The platform identifier
        resource_type: FHIR resource type
        resource_id: Resource ID
        operation: Operation name (must start with $)
        authorization: Optional Bearer token
    """
    validate_resource_type(resource_type)
    validate_resource_id(resource_id)

    try:
        _validate_operation(operation)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    access_token = extract_bearer_token(authorization)

    params = dict(request.query_params)

    try:
        client = get_fhir_client(platform_id, access_token)
        result = await client.resource(resource_type, id=resource_id).execute(
            operation=operation,
            method="GET",
            params=params if params else None,
        )

        audit_log(
            AuditEvent.RESOURCE_OPERATION,
            platform_id=platform_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details={"operation": operation},
        )

        return result

    except Exception as e:
        handle_fhir_error(e, platform_id)


@router.post("/{platform_id}/{resource_type}")
async def create_resource(
    platform_id: str,
    resource_type: str,
    resource: dict[str, Any],
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Create a new FHIR resource.

    Args:
        platform_id: The platform identifier
        resource_type: FHIR resource type
        resource: The resource to create
        authorization: Optional Bearer token
    """
    validate_resource_type(resource_type)

    access_token = extract_bearer_token(authorization)

    # Validate resource type matches
    if resource.get("resourceType") != resource_type:
        raise HTTPException(
            status_code=400,
            detail=f"Resource type mismatch: URL says '{resource_type}' "
            f"but resource has '{resource.get('resourceType')}'",
        )

    try:
        client = get_fhir_client(platform_id, access_token)
        created = await client.resource(resource_type, **resource).save()

        audit_log(
            AuditEvent.RESOURCE_CREATE,
            platform_id=platform_id,
            resource_type=resource_type,
            resource_id=created.get("id"),
        )

        return created

    except Exception as e:
        handle_fhir_error(e, platform_id)


@router.put("/{platform_id}/{resource_type}/{resource_id}")
async def update_resource(
    platform_id: str,
    resource_type: str,
    resource_id: str,
    resource: dict[str, Any],
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Update an existing FHIR resource (full replacement).

    Args:
        platform_id: The platform identifier
        resource_type: FHIR resource type
        resource_id: Resource ID
        resource: The updated resource
        authorization: Optional Bearer token
    """
    validate_resource_type(resource_type)
    validate_resource_id(resource_id)

    access_token = extract_bearer_token(authorization)

    # Validate resource type and ID match
    if resource.get("resourceType") != resource_type:
        raise HTTPException(
            status_code=400,
            detail=f"Resource type mismatch: URL says '{resource_type}' "
            f"but resource has '{resource.get('resourceType')}'",
        )

    if resource.get("id") and resource.get("id") != resource_id:
        raise HTTPException(
            status_code=400,
            detail=f"Resource ID mismatch: URL says '{resource_id}' "
            f"but resource has '{resource.get('id')}'",
        )

    # Ensure ID is set
    resource["id"] = resource_id

    try:
        client = get_fhir_client(platform_id, access_token)
        updated = await client.resource(resource_type, **resource).save()

        audit_log(
            AuditEvent.RESOURCE_UPDATE,
            platform_id=platform_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )

        return updated

    except Exception as e:
        handle_fhir_error(e, platform_id)


@router.delete("/{platform_id}/{resource_type}/{resource_id}")
async def delete_resource(
    platform_id: str,
    resource_type: str,
    resource_id: str,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Delete a FHIR resource.

    Args:
        platform_id: The platform identifier
        resource_type: FHIR resource type
        resource_id: Resource ID
        authorization: Optional Bearer token
    """
    validate_resource_type(resource_type)
    validate_resource_id(resource_id)

    access_token = extract_bearer_token(authorization)

    try:
        client = get_fhir_client(platform_id, access_token)
        await client.resource(resource_type, id=resource_id).delete()

        audit_log(
            AuditEvent.RESOURCE_DELETE,
            platform_id=platform_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )

        return {
            "resourceType": "OperationOutcome",
            "issue": [
                {
                    "severity": "information",
                    "code": "deleted",
                    "diagnostics": f"Successfully deleted {resource_type}/{resource_id}",
                }
            ],
        }

    except Exception as e:
        handle_fhir_error(e, platform_id)
