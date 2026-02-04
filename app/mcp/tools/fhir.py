"""
FHIR operation tools.

Thin wrappers around app.services.fhir_client.
Tokens are auto-fetched from session - clients should use auth tools to authenticate.
"""

from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from app.audit import AuditEvent, audit_log
from app.auth.token_manager import get_token_manager
from app.config.platform import get_all_platforms
from app.mcp.auth_handle import verify_auth_handle
from app.mcp.errors import error_response, handle_exception
from app.mcp.session import get_session_id
from app.mcp.validation import (
    validate_platform_id,
    validate_resource_id,
    validate_resource_type,
)
from app.services.fhir_client import (
    fetch_bundle_page,
    fetch_capability_statement,
    get_fhir_client,
    search_resources,
)
from app.validation import ALLOWED_OPERATIONS


def _resolve_session_id(
    ctx: Context, auth_handle: str | None, platform_id: str | None = None
) -> str | None:
    """
    Resolve session ID from auth_handle or MCP context.

    Priority:
    1. Verify and extract from auth_handle if provided
    2. Fall back to MCP transport session ID
    """
    if auth_handle:
        session_id = verify_auth_handle(auth_handle, platform_id)
        if session_id:
            return session_id
        # Invalid handle - don't fall back, return None to signal error
        return None

    return get_session_id(ctx)


async def get_access_token(
    ctx: Context, platform_id: str, auth_handle: str | None = None
) -> str | None:
    """Get access token from session for a platform."""
    session_id = _resolve_session_id(ctx, auth_handle, platform_id)
    if not session_id:
        return None

    token_manager = get_token_manager()
    token = await token_manager.get_token(session_id, platform_id, auto_refresh=True)
    return token.access_token if token else None


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
        description="Get FHIR server capabilities. Returns a summary by default. Use resource_type for details on a specific resource."
    )
    async def get_capabilities(
        platform_id: Annotated[
            str, Field(description="Platform identifier (e.g., 'aetna', 'cigna')")
        ],
        ctx: Context,
        resource_type: Annotated[
            str | None, Field(description="FHIR resource type for full details (e.g., 'Patient')")
        ] = None,
        full: Annotated[
            bool, Field(description="Return full CapabilityStatement instead of summary")
        ] = False,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
    ) -> dict[str, Any]:
        """Fetch CapabilityStatement from platform's FHIR server."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if resource_type and (err := validate_resource_type(resource_type)):
            return error_response("validation_error", err)

        try:
            token = await get_access_token(ctx, platform_id, auth_handle)
            result = await fetch_capability_statement(
                platform_id=platform_id,
                access_token=token,
                resource_type=resource_type,
                summarize=not full,
            )
            audit_log(
                AuditEvent.RESOURCE_READ,
                platform_id=platform_id,
                resource_type="CapabilityStatement",
            )
            return result
        except Exception as e:
            return handle_exception(e, "get_capabilities")

    @mcp.tool(
        description="Search for FHIR resources with pagination. Returns max 10 results by default to avoid large responses. Use limit to adjust (max 50). Use get_capabilities first to discover valid search parameters."
    )
    async def search(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        resource_type: Annotated[
            str, Field(description="FHIR resource type (e.g., Patient, Observation)")
        ],
        ctx: Context,
        params: Annotated[
            dict[str, Any] | None,
            Field(description="Search parameters as key-value pairs (e.g., {\"name\": \"Smith\"})"),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Max results to return (default 10, max 50)", ge=1, le=50),
        ] = 10,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
    ) -> dict[str, Any]:
        """Search for FHIR resources by type and parameters."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_type(resource_type):
            return error_response("validation_error", err)

        # Cap limit at 50 to prevent huge responses
        effective_limit = min(limit, 50)

        try:
            token = await get_access_token(ctx, platform_id, auth_handle)
            result = await search_resources(
                platform_id=platform_id,
                resource_type=resource_type,
                search_params=params,
                access_token=token,
                limit=effective_limit,
            )
            audit_log(
                AuditEvent.RESOURCE_SEARCH, platform_id=platform_id, resource_type=resource_type
            )
            return result
        except Exception as e:
            return handle_exception(e, "search")

    @mcp.tool(
        description="Fetch the next page of search results using a pagination URL from a Bundle's 'next' link."
    )
    async def get_next_page(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        url: Annotated[
            str,
            Field(description="The 'next' link URL from a Bundle response"),
        ],
        ctx: Context,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
    ) -> dict[str, Any]:
        """Fetch next page of results using Bundle pagination link."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)

        try:
            token = await get_access_token(ctx, platform_id, auth_handle)
            result = await fetch_bundle_page(
                platform_id=platform_id,
                url=url,
                access_token=token,
            )
            audit_log(
                AuditEvent.RESOURCE_SEARCH, platform_id=platform_id, resource_type="Bundle"
            )
            return result
        except ValueError as e:
            return error_response("validation_error", str(e))
        except Exception as e:
            return handle_exception(e, "get_next_page")

    @mcp.tool(description="Read a specific FHIR resource by ID.")
    async def read(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        resource_type: Annotated[str, Field(description="FHIR resource type")],
        resource_id: Annotated[str, Field(description="Resource ID")],
        ctx: Context,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
    ) -> dict[str, Any]:
        """Read a single FHIR resource by type and ID."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_type(resource_type):
            return error_response("validation_error", err)
        if err := validate_resource_id(resource_id):
            return error_response("validation_error", err)

        try:
            token = await get_access_token(ctx, platform_id, auth_handle)
            client = get_fhir_client(platform_id, token)
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

    @mcp.tool(
        description="Execute a FHIR operation like $everything on a resource. For $everything, use _count param to limit results (default 10, max 50)."
    )
    async def execute_operation(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        resource_type: Annotated[str, Field(description="FHIR resource type")],
        resource_id: Annotated[str, Field(description="Resource ID")],
        operation: Annotated[
            str, Field(description="Operation name (e.g., '$everything', '$validate')")
        ],
        ctx: Context,
        params: Annotated[
            dict[str, Any] | None,
            Field(description="Operation parameters. For $everything, use _count to limit results."),
        ] = None,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
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

        if operation not in ALLOWED_OPERATIONS:
            return error_response(
                "validation_error",
                f"Operation not allowed. Supported: {', '.join(sorted(ALLOWED_OPERATIONS))}",
            )

        # Enforce pagination for $everything to prevent huge responses
        op_params = dict(params) if params else {}
        if operation == "$everything":
            if "_count" not in op_params:
                op_params["_count"] = 10
            else:
                try:
                    count = int(op_params["_count"])
                    op_params["_count"] = min(count, 50)
                except (ValueError, TypeError):
                    op_params["_count"] = 10

        try:
            token = await get_access_token(ctx, platform_id, auth_handle)
            client = get_fhir_client(platform_id, token)
            result = await client.resource(resource_type, id=resource_id).execute(
                operation=operation,
                method="GET",
                params=op_params if op_params else None,
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
        ctx: Context,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
    ) -> dict[str, Any]:
        """Create a new FHIR resource."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_type(resource_type):
            return error_response("validation_error", err)

        try:
            token = await get_access_token(ctx, platform_id, auth_handle)
            client = get_fhir_client(platform_id, token)
            created = await client.resource(resource_type, **resource).save()
            audit_log(
                AuditEvent.RESOURCE_CREATE, platform_id=platform_id, resource_type=resource_type
            )
            return dict(created)
        except Exception as e:
            return handle_exception(e, "create")

    @mcp.tool(description="Update an existing FHIR resource (full replacement).")
    async def update(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        resource_type: Annotated[str, Field(description="FHIR resource type")],
        resource_id: Annotated[str, Field(description="Resource ID")],
        resource: Annotated[dict[str, Any], Field(description="Updated FHIR resource data")],
        ctx: Context,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
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
            token = await get_access_token(ctx, platform_id, auth_handle)
            client = get_fhir_client(platform_id, token)
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
        ctx: Context,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
    ) -> dict[str, Any]:
        """Delete a FHIR resource."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_type(resource_type):
            return error_response("validation_error", err)
        if err := validate_resource_id(resource_id):
            return error_response("validation_error", err)

        try:
            token = await get_access_token(ctx, platform_id, auth_handle)
            client = get_fhir_client(platform_id, token)
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
