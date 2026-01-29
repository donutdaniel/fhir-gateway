"""
MCP (Model Context Protocol) server for FHIR Gateway.

This module provides an MCP server that exposes FHIR operations as tools,
using the native MCP Python SDK. The MCP tools are thin wrappers around
the same services used by the REST API.

Usage:
    # Run standalone MCP server
    python -m app.mcp.server

    # Or via CLI
    fhir-gateway-mcp
"""

from app.mcp.server import mcp, run_mcp_server, run_mcp_stdio

__all__ = ["mcp", "run_mcp_server", "run_mcp_stdio"]
