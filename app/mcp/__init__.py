"""
MCP (Model Context Protocol) server for FHIR Gateway.

This module provides an MCP server that exposes FHIR operations as tools,
using the native MCP Python SDK. The MCP tools are thin wrappers around
the same services used by the REST API.

The MCP server is mounted at /mcp in the main FastAPI app.
"""

from app.mcp.server import mcp

__all__ = ["mcp"]
