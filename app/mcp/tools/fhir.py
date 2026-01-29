"""
FHIR operation tools.

Thin wrappers around app.services.fhir_client.
"""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from app.audit import AuditEvent, audit_log
from app.config.platform import get_all_platforms
from app.mcp.errors import error_response, handle_exception
from app.mcp.validation import (
    validate_platform_id,
    validate_resource_id,
    validate_resource_type,
)
from app.services.fhir_client import (
    fetch_capability_statement,
    get_fhir_client,
    search_resources,
)


def register_fhir_tools(mcp: FastMCP) -> None:
    """Register FHIR operation tools."""

    @mcp.tool(description="List all available platforms and their FHIR/OAuth capabilities.")
    async def list_platforms() -> dict[str, Any]:
        """List available platforms for FHIR operations."""
        platforms = get_all_platforms()
        platform_list = [
            {
                "id": pid,
                "name": p.display_name or p.name,
                "has_fhir": p.fhir_base_url is not None,
                "has_oauth": p.oauth is not None and p.oauth.authorize_url is not None,
            }
            for pid, p in platforms.items()
        ]
        return {"platforms": platform_list, "total": len(platform_list)}

    @mcp.tool(
        description="Get FHIR server capabilities for a resource type. Call this first to discover search parameters."
    )
    async def get_capabilities(
        platform_id: Annotated[str, Field(description="Platform identifier (e.g., 'aetna', 'cigna')")],
        resource_type: Annotated[
            str | None, Field(description="FHIR resource type to filter (e.g., 'Patient')")
        ] = None,
        access_token: Annotated[
            str | None, Field(description="OAuth access token (if required)")
        ] = None,
    ) -> dict[str, Any]:
        """Fetch CapabilityStatement from platform's FHIR server."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if resource_type and (err := validate_resource_type(resource_type)):
            return error_response("validation_error", err)

        try:
            result = await fetch_capability_statement(
                platform_id=platform_id,
                access_token=access_token,
                resource_type=resource_type,
            )
            audit_log(
                AuditEvent.RESOURCE_READ, platform_id=platform_id, resource_type="CapabilityStatement"
            )
            return result
        except Exception as e:
            return handle_exception(e, "get_capabilities")

    @mcp.tool(
        description="Search for FHIR resources. Use get_capabilities first to discover valid search parameters."
    )
    async def search(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        resource_type: Annotated[
            str, Field(description="FHIR resource type (e.g., Patient, Observation)")
        ],
        params: Annotated[
            dict[str, Any] | None, Field(description="Search parameters as key-value pairs")
        ] = None,
        access_token: Annotated[str | None, Field(description="OAuth access token")] = None,
    ) -> dict[str, Any]:
        """Search for FHIR resources by type and parameters."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_type(resource_type):
            return error_response("validation_error", err)

        try:
            result = await search_resources(
                platform_id=platform_id,
                resource_type=resource_type,
                search_params=params,
                access_token=access_token,
            )
            audit_log(AuditEvent.RESOURCE_SEARCH, platform_id=platform_id, resource_type=resource_type)
            return result
        except Exception as e:
            return handle_exception(e, "search")

    @mcp.tool(description="Read a specific FHIR resource by ID.")
    async def read(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        resource_type: Annotated[str, Field(description="FHIR resource type")],
        resource_id: Annotated[str, Field(description="Resource ID")],
        access_token: Annotated[str | None, Field(description="OAuth access token")] = None,
    ) -> dict[str, Any]:
        """Read a single FHIR resource by type and ID."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_type(resource_type):
            return error_response("validation_error", err)
        if err := validate_resource_id(resource_id):
            return error_response("validation_error", err)

        try:
            client = get_fhir_client(platform_id, access_token)
            resource = await client.reference(resource_type, resource_id).to_resource()
            audit_log(
                AuditEvent.RESOURCE_READ,
                platform_id=platform_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            return dict(resource)
        except Exception as e:
            return handle_exception(e, "read")

    @mcp.tool(description="Execute a FHIR operation like $everything on a resource.")
    async def execute_operation(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        resource_type: Annotated[str, Field(description="FHIR resource type")],
        resource_id: Annotated[str, Field(description="Resource ID")],
        operation: Annotated[
            str, Field(description="Operation name (e.g., '$everything', '$validate')")
        ],
        params: Annotated[dict[str, Any] | None, Field(description="Operation parameters")] = None,
        access_token: Annotated[str | None, Field(description="OAuth access token")] = None,
    ) -> dict[str, Any]:
        """Execute a FHIR operation on a resource."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_type(resource_type):
            return error_response("validation_error", err)
        if err := validate_resource_id(resource_id):
            return error_response("validation_error", err)

        if not operation.startswith("$"):
            return error_response("validation_error", "Operation must start with '$'")

        allowed = {"$everything", "$validate", "$summary", "$document", "$expand", "$lookup"}
        if operation not in allowed:
            return error_response(
                "validation_error",
                f"Operation not allowed. Supported: {', '.join(sorted(allowed))}",
            )

        try:
            client = get_fhir_client(platform_id, access_token)
            result = await client.resource(resource_type, id=resource_id).execute(
                operation=operation,
                method="GET",
                params=params,
            )
            audit_log(
                AuditEvent.RESOURCE_OPERATION,
                platform_id=platform_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            return result
        except Exception as e:
            return handle_exception(e, "execute_operation")

    @mcp.tool(description="Create a new FHIR resource.")
    async def create(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        resource_type: Annotated[str, Field(description="FHIR resource type")],
        resource: Annotated[dict[str, Any], Field(description="FHIR resource data")],
        access_token: Annotated[str | None, Field(description="OAuth access token")] = None,
    ) -> dict[str, Any]:
        """Create a new FHIR resource."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_type(resource_type):
            return error_response("validation_error", err)

        try:
            client = get_fhir_client(platform_id, access_token)
            created = await client.resource(resource_type, **resource).save()
            audit_log(AuditEvent.RESOURCE_CREATE, platform_id=platform_id, resource_type=resource_type)
            return dict(created)
        except Exception as e:
            return handle_exception(e, "create")

    @mcp.tool(description="Update an existing FHIR resource (full replacement).")
    async def update(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        resource_type: Annotated[str, Field(description="FHIR resource type")],
        resource_id: Annotated[str, Field(description="Resource ID")],
        resource: Annotated[dict[str, Any], Field(description="Updated FHIR resource data")],
        access_token: Annotated[str | None, Field(description="OAuth access token")] = None,
    ) -> dict[str, Any]:
        """Update a FHIR resource."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_type(resource_type):
            return error_response("validation_error", err)
        if err := validate_resource_id(resource_id):
            return error_response("validation_error", err)

        try:
            resource["id"] = resource_id
            client = get_fhir_client(platform_id, access_token)
            updated = await client.resource(resource_type, **resource).save()
            audit_log(
                AuditEvent.RESOURCE_UPDATE,
                platform_id=platform_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            return dict(updated)
        except Exception as e:
            return handle_exception(e, "update")

    @mcp.tool(description="Delete a FHIR resource.")
    async def delete(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        resource_type: Annotated[str, Field(description="FHIR resource type")],
        resource_id: Annotated[str, Field(description="Resource ID")],
        access_token: Annotated[str | None, Field(description="OAuth access token")] = None,
    ) -> dict[str, Any]:
        """Delete a FHIR resource."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_type(resource_type):
            return error_response("validation_error", err)
        if err := validate_resource_id(resource_id):
            return error_response("validation_error", err)

        try:
            client = get_fhir_client(platform_id, access_token)
            await client.resource(resource_type, id=resource_id).delete()
            audit_log(
                AuditEvent.RESOURCE_DELETE,
                platform_id=platform_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            return {"success": True, "message": f"Deleted {resource_type}/{resource_id}"}
        except Exception as e:
            return handle_exception(e, "delete")
