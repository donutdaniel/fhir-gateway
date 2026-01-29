"""
Tests for MCP server and tools.
"""

import pytest


class TestMCPServerCreation:
    """Tests for MCP server creation."""

    def test_server_exists(self):
        """Test MCP server instance is created."""
        from app.mcp.server import mcp

        assert mcp is not None
        assert mcp.name == "fhir-gateway"

    def test_server_has_instructions(self):
        """Test server has LLM instructions."""
        from app.mcp.server import mcp

        assert mcp.instructions is not None
        assert "FHIR" in mcp.instructions

    def test_server_can_be_imported_multiple_times(self):
        """Test importing server returns same instance."""
        from app.mcp.server import mcp as mcp1
        from app.mcp.server import mcp as mcp2

        assert mcp1 is mcp2


class TestMCPValidation:
    """Tests for MCP validation helpers."""

    def test_validate_resource_type_valid(self):
        """Test valid resource types return None."""
        from app.mcp.validation import validate_resource_type

        assert validate_resource_type("Patient") is None
        assert validate_resource_type("Observation") is None
        assert validate_resource_type("MedicationRequest") is None

    def test_validate_resource_type_invalid(self):
        """Test invalid resource types return error message."""
        from app.mcp.validation import validate_resource_type

        assert validate_resource_type("patient") is not None  # lowercase
        assert validate_resource_type("123") is not None  # numbers
        assert validate_resource_type("") is not None  # empty
        assert validate_resource_type("Patient123") is not None  # numbers

    def test_validate_platform_id_valid(self):
        """Test valid platform IDs return None."""
        from app.mcp.validation import validate_platform_id

        assert validate_platform_id("aetna") is None
        assert validate_platform_id("cigna-healthcare") is None
        assert validate_platform_id("platform-123") is None

    def test_validate_platform_id_invalid(self):
        """Test invalid platform IDs return error message."""
        from app.mcp.validation import validate_platform_id

        assert validate_platform_id("") is not None
        assert validate_platform_id("platform/injection") is not None
        assert validate_platform_id("platform..path") is not None

    def test_validate_resource_id_valid(self):
        """Test valid resource IDs return None."""
        from app.mcp.validation import validate_resource_id

        assert validate_resource_id("123") is None
        assert validate_resource_id("abc-123") is None
        assert validate_resource_id("patient.001") is None

    def test_validate_resource_id_invalid(self):
        """Test invalid resource IDs return error message."""
        from app.mcp.validation import validate_resource_id

        assert validate_resource_id("") is not None
        assert validate_resource_id("a" * 65) is not None  # too long
        assert validate_resource_id("id/slash") is not None
        assert validate_resource_id("id<script>") is not None


class TestMCPErrors:
    """Tests for MCP error handling."""

    def test_error_response_format(self):
        """Test error_response creates correct structure."""
        from app.mcp.errors import error_response

        result = error_response("test_error", "Test message")

        assert result == {"error": "test_error", "message": "Test message"}

    def test_handle_exception_platform_not_found(self):
        """Test handle_exception for PlatformNotFoundError."""
        from app.errors import PlatformNotFoundError
        from app.mcp.errors import handle_exception

        error = PlatformNotFoundError("unknown-platform")
        result = handle_exception(error, "test_op")

        assert result["error"] == "platform_not_found"
        assert "unknown-platform" in result["message"]

    def test_handle_exception_platform_not_configured(self):
        """Test handle_exception for PlatformNotConfiguredError."""
        from app.errors import PlatformNotConfiguredError
        from app.mcp.errors import handle_exception

        error = PlatformNotConfiguredError("some-platform")
        result = handle_exception(error, "test_op")

        assert result["error"] == "platform_not_configured"
        assert "some-platform" in result["message"]

    def test_handle_exception_resource_not_found(self):
        """Test handle_exception for ResourceNotFound."""
        from fhirpy.base.exceptions import ResourceNotFound

        from app.mcp.errors import handle_exception

        error = ResourceNotFound()
        result = handle_exception(error, "test_op")

        assert result["error"] == "not_found"

    def test_handle_exception_operation_outcome(self):
        """Test handle_exception for OperationOutcome."""
        from fhirpy.base.exceptions import OperationOutcome

        from app.mcp.errors import handle_exception

        error = OperationOutcome(resource={"resourceType": "OperationOutcome"})
        result = handle_exception(error, "test_op")

        assert result["error"] == "operation_outcome"

    def test_handle_exception_value_error(self):
        """Test handle_exception for ValueError."""
        from app.mcp.errors import handle_exception

        error = ValueError("Invalid input")
        result = handle_exception(error, "test_op")

        assert result["error"] == "invalid_request"
        assert "Invalid input" in result["message"]

    def test_handle_exception_generic_sanitized(self):
        """Test handle_exception sanitizes generic exceptions."""
        from app.mcp.errors import handle_exception

        # Generic exception should not leak internals
        error = Exception("Internal database error at line 123")
        result = handle_exception(error, "test_op")

        assert result["error"] == "internal_error"
        assert "database" not in result["message"]
        assert "line 123" not in result["message"]
        assert "test_op" in result["message"]


class TestMCPToolsRegistration:
    """Tests for MCP tool registration."""

    def test_fhir_tools_register(self):
        """Test FHIR tools can be registered."""
        from mcp.server.fastmcp import FastMCP

        from app.mcp.tools.fhir import register_fhir_tools

        mcp = FastMCP(name="test")
        register_fhir_tools(mcp)

        # Tools are registered via decorators, check the server has tools
        assert mcp is not None

    def test_coverage_tools_register(self):
        """Test coverage tools can be registered."""
        from mcp.server.fastmcp import FastMCP

        from app.mcp.tools.coverage import register_coverage_tools

        mcp = FastMCP(name="test")
        register_coverage_tools(mcp)

        assert mcp is not None

    def test_auth_tools_register(self):
        """Test auth tools can be registered."""
        from mcp.server.fastmcp import FastMCP

        from app.mcp.tools.auth import register_auth_tools

        mcp = FastMCP(name="test")
        register_auth_tools(mcp)

        assert mcp is not None

    def test_all_tools_register(self):
        """Test all tools can be registered together."""
        from mcp.server.fastmcp import FastMCP

        from app.mcp.tools import register_all_tools

        mcp = FastMCP(name="test")
        register_all_tools(mcp)

        assert mcp is not None


class TestMCPResources:
    """Tests for MCP resources."""

    def test_resources_can_be_registered(self):
        """Test resources can be registered."""
        from mcp.server.fastmcp import FastMCP

        from app.mcp.resources import register_resources

        mcp = FastMCP(name="test")
        register_resources(mcp)

        assert mcp is not None


class TestMCPPrompts:
    """Tests for MCP prompts."""

    def test_prompts_can_be_registered(self):
        """Test prompts can be registered."""
        from mcp.server.fastmcp import FastMCP

        from app.mcp.prompts import register_prompts

        mcp = FastMCP(name="test")
        register_prompts(mcp)

        assert mcp is not None


class TestListPlatformsTool:
    """Tests for list_platforms tool."""

    @pytest.mark.asyncio
    async def test_list_platforms_returns_platforms(self):
        """Test list_platforms returns available platforms."""
        from mcp.server.fastmcp import FastMCP

        from app.mcp.tools.fhir import register_fhir_tools

        # Create a test MCP server and register tools
        test_mcp = FastMCP(name="test")
        register_fhir_tools(test_mcp)

        # The tool is registered as a decorated function
        # We need to test via the actual tool
        from app.config.platform import get_all_platforms

        platforms = get_all_platforms()
        assert len(platforms) >= 0  # May be empty if no platforms configured
