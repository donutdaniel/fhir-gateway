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

from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.config.logging import get_logger
from app.config.settings import get_settings
from app.mcp.prompts import register_prompts
from app.mcp.resources import register_resources
from app.mcp.tools import register_all_tools

logger = get_logger(__name__)


def _get_transport_security() -> TransportSecuritySettings | None:
    """Build transport security settings from configuration."""
    settings = get_settings()

    # Check if explicitly configured
    if settings.mcp_allowed_hosts:
        if settings.mcp_allowed_hosts == "*":
            # Disable DNS rebinding protection
            return TransportSecuritySettings(enable_dns_rebinding_protection=False)
        # Use explicit list
        hosts = [h.strip() for h in settings.mcp_allowed_hosts.split(",")]
    else:
        # Derive from public_url
        parsed = urlparse(settings.public_url)
        host = parsed.netloc
        hosts = [host]
        # Also allow with wildcard port for flexibility
        if ":" in host:
            base_host = host.rsplit(":", 1)[0]
            hosts.append(f"{base_host}:*")
        else:
            hosts.append(f"{host}:*")
        # Always include localhost for local development
        hosts.extend(["localhost:*", "127.0.0.1:*", "[::1]:*"])

    # Build allowed origins from allowed hosts
    origins = []
    for h in hosts:
        if not h.endswith(":*"):
            origins.append(f"http://{h}")
            origins.append(f"https://{h}")
        else:
            base = h[:-2]  # Remove :*
            origins.append(f"http://{base}:*")
            origins.append(f"https://{base}:*")

    logger.info("MCP transport security configured", allowed_hosts=hosts)

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


# Create the MCP server with transport security
mcp = FastMCP(
    name="fhir-gateway",
    instructions=(
        "FHIR Gateway MCP Server provides tools for interacting with healthcare platform FHIR APIs. "
        "Use list_platforms to discover available platforms, then use FHIR tools with the platform_id. "
        "For platforms with OAuth, use start_auth first to authenticate."
    ),
    transport_security=_get_transport_security(),
)

# Register all components
register_all_tools(mcp)
register_resources(mcp)
register_prompts(mcp)

logger.debug("MCP server configured with tools, resources, and prompts")
