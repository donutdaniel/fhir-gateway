"""
MCP session utilities.

Provides helper functions to extract session information from MCP context.
"""

from mcp.server.fastmcp import Context


def get_session_id(ctx: Context | None) -> str | None:
    """
    Extract session ID from MCP context.

    Priority:
    1. MCP session ID from transport headers (stable across calls)
    2. client_id from context metadata
    3. request_id (last resort)

    Args:
        ctx: MCP context (may be None)

    Returns:
        Session ID if available, None otherwise
    """
    if ctx is None:
        return None

    # Try to get stable MCP session ID from transport headers
    try:
        request = ctx.request_context.request
        if request is not None:
            mcp_session_id = request.headers.get("mcp-session-id")
            if mcp_session_id:
                return mcp_session_id
    except (AttributeError, LookupError):
        pass

    # Try client_id
    client_id = ctx.client_id
    if client_id:
        return client_id

    # Fall back to request_id
    return ctx.request_id
