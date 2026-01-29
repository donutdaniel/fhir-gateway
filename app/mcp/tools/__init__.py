"""
MCP Tools for FHIR Gateway.

This package contains thin tool wrappers that delegate to services.
"""

from app.mcp.tools.auth import register_auth_tools
from app.mcp.tools.coverage import register_coverage_tools
from app.mcp.tools.fhir import register_fhir_tools


def register_all_tools(mcp) -> None:
    """Register all MCP tools with the server."""
    register_fhir_tools(mcp)
    register_coverage_tools(mcp)
    register_auth_tools(mcp)


__all__ = [
    "register_all_tools",
    "register_fhir_tools",
    "register_coverage_tools",
    "register_auth_tools",
]
