"""
MCP Server for FHIR Gateway.

This is the main entry point that wires together all MCP components:
- Tools (FHIR, coverage, auth)
- Resources (platform info)
- Prompts (workflow templates)

Architecture:
- MCP tools are thin wrappers around services
- Services handle all business logic (same as REST API)
- MCP is mounted in the same FastAPI app as REST API
- OAuth handled by REST API at /auth/*
"""

from mcp.server.fastmcp import FastMCP

from app.config.logging import get_logger
from app.mcp.prompts import register_prompts
from app.mcp.resources import register_resources
from app.mcp.tools import register_all_tools

logger = get_logger(__name__)

# Create the MCP server
mcp = FastMCP(
    name="fhir-gateway",
    instructions=(
        "FHIR Gateway MCP Server provides tools for interacting with healthcare platform FHIR APIs. "
        "Use list_platforms to discover available platforms, then use FHIR tools with the platform_id. "
        "For platforms with OAuth, use start_auth first to authenticate."
    ),
)

# Register all components
register_all_tools(mcp)
register_resources(mcp)
register_prompts(mcp)

logger.debug("MCP server configured with tools, resources, and prompts")
