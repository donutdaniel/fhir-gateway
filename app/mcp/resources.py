"""
MCP Resources for FHIR Gateway.

Exposes platform configuration as MCP resources.
"""

import json

from mcp.server.fastmcp import FastMCP

from app.config.platform import get_all_platforms, get_platform


def register_resources(mcp: FastMCP) -> None:
    """Register MCP resources."""

    @mcp.resource(
        uri="fhir://platforms",
        name="Available Platforms",
        description="List of registered platforms with OAuth credentials configured.",
        mime_type="application/json",
    )
    async def platforms_resource() -> str:
        """Get list of registered platforms as JSON."""
        platforms = get_all_platforms()
        platform_list = [
            {
                "id": pid,
                "name": p.display_name or p.name,
            }
            for pid, p in platforms.items()
            if p.oauth is not None and p.oauth.is_registered
        ]
        return json.dumps({"platforms": platform_list, "total": len(platform_list)}, indent=2)

    @mcp.resource(
        uri="fhir://platform/{platform_id}",
        name="Platform Details",
        description="Detailed information about a specific platform.",
        mime_type="application/json",
    )
    async def platform_resource(platform_id: str) -> str:
        """Get details for a specific platform as JSON."""
        platform = get_platform(platform_id)
        if not platform:
            return json.dumps({"error": f"Platform '{platform_id}' not found"})

        details = {
            "id": platform.id,
            "name": platform.display_name or platform.name,
            "fhir_base_url": platform.fhir_base_url,
        }
        if platform.capabilities:
            details["capabilities"] = {
                "patient_access": platform.capabilities.patient_access,
                "crd": platform.capabilities.crd,
                "dtr": platform.capabilities.dtr,
            }
        return json.dumps(details, indent=2)
