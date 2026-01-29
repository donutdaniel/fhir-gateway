"""
Tests for MCP FHIR tools.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fhirpy.base.exceptions import OperationOutcome, ResourceNotFound
from mcp.server.fastmcp import FastMCP

from app.mcp.tools.fhir import register_fhir_tools
from app.services.fhir_client import PlatformNotConfiguredError, PlatformNotFoundError


@pytest.fixture
def mock_ctx():
    """Create mock MCP context with session ID."""
    ctx = MagicMock()
    ctx.client_id = "sess-123"
    ctx.request_id = "req-456"
    request = MagicMock()
    request.headers = MagicMock()
    request.headers.get = MagicMock(return_value=None)
    ctx.request_context = MagicMock()
    ctx.request_context.request = request
    return ctx


class TestListPlatforms:
    """Tests for list_platforms tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_fhir_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_list_platforms_returns_platform_list(self, mcp):
        """Should return list of platforms with capabilities."""
        # Create platform mocks with proper attribute values
        aetna_mock = MagicMock()
        aetna_mock.display_name = "Aetna"
        aetna_mock.name = "Aetna Health"
        aetna_mock.fhir_base_url = "https://fhir.aetna.com/r4"
        aetna_mock.oauth = MagicMock()
        aetna_mock.oauth.authorize_url = "https://auth.aetna.com"

        cigna_mock = MagicMock()
        cigna_mock.display_name = None
        cigna_mock.name = "Cigna Health"
        cigna_mock.fhir_base_url = None
        cigna_mock.oauth = None

        mock_platforms = {
            "aetna": aetna_mock,
            "cigna": cigna_mock,
        }

        with patch("app.mcp.tools.fhir.get_all_platforms", return_value=mock_platforms):
            # Get the list_platforms tool
            tools = mcp._tool_manager._tools
            list_platforms = tools["list_platforms"].fn

            result = await list_platforms()

        assert result["total"] == 2
        assert len(result["platforms"]) == 2

        # Check aetna
        aetna = next(p for p in result["platforms"] if p["id"] == "aetna")
        assert aetna["name"] == "Aetna"
        assert aetna["has_fhir"] is True
        assert aetna["has_oauth"] is True

        # Check cigna
        cigna = next(p for p in result["platforms"] if p["id"] == "cigna")
        assert cigna["name"] == "Cigna Health"
        assert cigna["has_fhir"] is False
        assert cigna["has_oauth"] is False


class TestGetCapabilities:
    """Tests for get_capabilities tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_fhir_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_capability_statement(self):
        """Sample CapabilityStatement."""
        return {
            "resourceType": "CapabilityStatement",
            "status": "active",
            "rest": [
                {
                    "mode": "server",
                    "resource": [
                        {
                            "type": "Patient",
                            "searchParam": [
                                {"name": "identifier", "type": "token"},
                                {"name": "name", "type": "string"},
                            ],
                        }
                    ],
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_get_capabilities_success(self, mcp, mock_capability_statement, mock_ctx):
        """Should return CapabilityStatement for valid platform."""
        with patch(
            "app.mcp.tools.fhir.fetch_capability_statement",
            new_callable=AsyncMock,
            return_value=mock_capability_statement,
        ):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                get_capabilities = tools["get_capabilities"].fn

                result = await get_capabilities(platform_id="aetna", ctx=mock_ctx)

        assert result["resourceType"] == "CapabilityStatement"
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_capabilities_with_resource_type(self, mcp, mock_capability_statement, mock_ctx):
        """Should filter capabilities by resource type."""
        with patch(
            "app.mcp.tools.fhir.fetch_capability_statement",
            new_callable=AsyncMock,
            return_value=mock_capability_statement,
        ):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                get_capabilities = tools["get_capabilities"].fn

                result = await get_capabilities(
                    platform_id="aetna",
                    ctx=mock_ctx,
                    resource_type="Patient",
                )

        assert result["resourceType"] == "CapabilityStatement"

    @pytest.mark.asyncio
    async def test_get_capabilities_invalid_platform_id(self, mcp, mock_ctx):
        """Should return validation error for invalid platform_id."""
        tools = mcp._tool_manager._tools
        get_capabilities = tools["get_capabilities"].fn

        result = await get_capabilities(platform_id="invalid@platform!", ctx=mock_ctx)

        assert result["error"] == "validation_error"
        assert "Invalid platform_id" in result["message"]

    @pytest.mark.asyncio
    async def test_get_capabilities_invalid_resource_type(self, mcp, mock_ctx):
        """Should return validation error for invalid resource_type."""
        tools = mcp._tool_manager._tools
        get_capabilities = tools["get_capabilities"].fn

        result = await get_capabilities(
            platform_id="aetna",
            ctx=mock_ctx,
            resource_type="invalid_type",
        )

        assert result["error"] == "validation_error"
        assert "Invalid resource type" in result["message"]

    @pytest.mark.asyncio
    async def test_get_capabilities_platform_not_found(self, mcp, mock_ctx):
        """Should return error when platform not found."""
        with patch(
            "app.mcp.tools.fhir.fetch_capability_statement",
            new_callable=AsyncMock,
            side_effect=PlatformNotFoundError("aetna"),
        ):
            tools = mcp._tool_manager._tools
            get_capabilities = tools["get_capabilities"].fn

            result = await get_capabilities(platform_id="aetna", ctx=mock_ctx)

        assert result["error"] == "platform_not_found"

    @pytest.mark.asyncio
    async def test_get_capabilities_platform_not_configured(self, mcp, mock_ctx):
        """Should return error when platform has no FHIR endpoint."""
        with patch(
            "app.mcp.tools.fhir.fetch_capability_statement",
            new_callable=AsyncMock,
            side_effect=PlatformNotConfiguredError("aetna"),
        ):
            tools = mcp._tool_manager._tools
            get_capabilities = tools["get_capabilities"].fn

            result = await get_capabilities(platform_id="aetna", ctx=mock_ctx)

        assert result["error"] == "platform_not_configured"


class TestSearch:
    """Tests for search tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_fhir_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_search_bundle(self):
        """Sample search result bundle."""
        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 2,
            "entry": [
                {
                    "fullUrl": "Patient/123",
                    "resource": {
                        "resourceType": "Patient",
                        "id": "123",
                        "name": [{"family": "Smith", "given": ["John"]}],
                    },
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_search_success(self, mcp, mock_search_bundle, mock_ctx):
        """Should return search results for valid request."""
        with patch(
            "app.mcp.tools.fhir.search_resources",
            new_callable=AsyncMock,
            return_value=mock_search_bundle,
        ):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                search = tools["search"].fn

                result = await search(
                    platform_id="aetna",
                    resource_type="Patient",
                    ctx=mock_ctx,
                    params={"name": "Smith"},
                )

        assert result["resourceType"] == "Bundle"
        assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_search_invalid_platform_id(self, mcp, mock_ctx):
        """Should return validation error for invalid platform_id."""
        tools = mcp._tool_manager._tools
        search = tools["search"].fn

        result = await search(
            platform_id="",
            resource_type="Patient",
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_search_invalid_resource_type(self, mcp, mock_ctx):
        """Should return validation error for invalid resource_type."""
        tools = mcp._tool_manager._tools
        search = tools["search"].fn

        result = await search(
            platform_id="aetna",
            resource_type="patient",  # lowercase is invalid
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"
        assert "Invalid resource type" in result["message"]

    @pytest.mark.asyncio
    async def test_search_platform_not_found(self, mcp, mock_ctx):
        """Should return error when platform not found."""
        with patch(
            "app.mcp.tools.fhir.search_resources",
            new_callable=AsyncMock,
            side_effect=PlatformNotFoundError("unknown"),
        ):
            tools = mcp._tool_manager._tools
            search = tools["search"].fn

            result = await search(
                platform_id="unknown",
                resource_type="Patient",
                ctx=mock_ctx,
            )

        assert result["error"] == "platform_not_found"


class TestRead:
    """Tests for read tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_fhir_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        mock_ref = AsyncMock()
        # Create a dict-like mock that supports dict() conversion
        resource_data = {"resourceType": "Patient", "id": "123", "name": [{"family": "Smith"}]}
        mock_resource = MagicMock()
        mock_resource.keys = MagicMock(return_value=resource_data.keys())
        mock_resource.__getitem__ = lambda self, key: resource_data[key]
        mock_resource.__iter__ = lambda self: iter(resource_data)
        mock_ref.to_resource = AsyncMock(return_value=mock_resource)
        client.reference = MagicMock(return_value=mock_ref)
        return client

    @pytest.mark.asyncio
    async def test_read_success(self, mcp, mock_fhir_client, mock_ctx):
        """Should return resource for valid request."""
        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_fhir_client):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                read = tools["read"].fn

                result = await read(
                    platform_id="aetna",
                    resource_type="Patient",
                    resource_id="123",
                    ctx=mock_ctx,
                )

        assert result["resourceType"] == "Patient"
        mock_fhir_client.reference.assert_called_once_with("Patient", "123")

    @pytest.mark.asyncio
    async def test_read_invalid_platform_id(self, mcp, mock_ctx):
        """Should return validation error for invalid platform_id."""
        tools = mcp._tool_manager._tools
        read = tools["read"].fn

        result = await read(
            platform_id="bad@id",
            resource_type="Patient",
            resource_id="123",
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_read_invalid_resource_type(self, mcp, mock_ctx):
        """Should return validation error for invalid resource_type."""
        tools = mcp._tool_manager._tools
        read = tools["read"].fn

        result = await read(
            platform_id="aetna",
            resource_type="invalid",
            resource_id="123",
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_read_invalid_resource_id(self, mcp, mock_ctx):
        """Should return validation error for invalid resource_id."""
        tools = mcp._tool_manager._tools
        read = tools["read"].fn

        result = await read(
            platform_id="aetna",
            resource_type="Patient",
            resource_id="",
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_read_resource_not_found(self, mcp, mock_ctx):
        """Should return error when resource not found."""
        mock_client = MagicMock()
        mock_ref = MagicMock()
        mock_ref.to_resource = AsyncMock(side_effect=ResourceNotFound())
        mock_client.reference = MagicMock(return_value=mock_ref)

        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_client):
            tools = mcp._tool_manager._tools
            read = tools["read"].fn

            result = await read(
                platform_id="aetna",
                resource_type="Patient",
                resource_id="nonexistent",
                ctx=mock_ctx,
            )

        assert result["error"] == "not_found"


class TestExecuteOperation:
    """Tests for execute_operation tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_fhir_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        mock_resource = MagicMock()
        mock_resource.execute = AsyncMock(return_value={"resourceType": "Bundle"})
        client.resource = MagicMock(return_value=mock_resource)
        return client

    @pytest.mark.asyncio
    async def test_execute_operation_success(self, mcp, mock_fhir_client, mock_ctx):
        """Should execute operation successfully."""
        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_fhir_client):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                execute_operation = tools["execute_operation"].fn

                result = await execute_operation(
                    platform_id="aetna",
                    resource_type="Patient",
                    resource_id="123",
                    operation="$everything",
                    ctx=mock_ctx,
                )

        assert result["resourceType"] == "Bundle"
        mock_fhir_client.resource.assert_called_once_with("Patient", id="123")

    @pytest.mark.asyncio
    async def test_execute_operation_missing_dollar_sign(self, mcp, mock_ctx):
        """Should return validation error for operation without $."""
        tools = mcp._tool_manager._tools
        execute_operation = tools["execute_operation"].fn

        result = await execute_operation(
            platform_id="aetna",
            resource_type="Patient",
            resource_id="123",
            operation="everything",  # Missing $
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"
        assert "must start with '$'" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_operation_not_allowed(self, mcp, mock_ctx):
        """Should return validation error for disallowed operation."""
        tools = mcp._tool_manager._tools
        execute_operation = tools["execute_operation"].fn

        result = await execute_operation(
            platform_id="aetna",
            resource_type="Patient",
            resource_id="123",
            operation="$unknown",
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"
        assert "not allowed" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_operation_allowed_operations(self, mcp, mock_fhir_client, mock_ctx):
        """Should allow all supported operations."""
        allowed_ops = ["$everything", "$validate", "$summary", "$document", "$expand", "$lookup"]

        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_fhir_client):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                execute_operation = tools["execute_operation"].fn

                for op in allowed_ops:
                    result = await execute_operation(
                        platform_id="aetna",
                        resource_type="Patient",
                        resource_id="123",
                        operation=op,
                        ctx=mock_ctx,
                    )
                    assert "error" not in result, f"Operation {op} should be allowed"

    @pytest.mark.asyncio
    async def test_execute_operation_with_params(self, mcp, mock_fhir_client, mock_ctx):
        """Should pass parameters to operation."""
        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_fhir_client):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                execute_operation = tools["execute_operation"].fn

                await execute_operation(
                    platform_id="aetna",
                    resource_type="Patient",
                    resource_id="123",
                    operation="$everything",
                    ctx=mock_ctx,
                    params={"_count": 10},
                )

        mock_fhir_client.resource().execute.assert_called_once_with(
            operation="$everything",
            method="GET",
            params={"_count": 10},
        )


class TestCreate:
    """Tests for create tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_fhir_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        # Create a dict-like mock that supports dict() conversion
        resource_data = {"resourceType": "Patient", "id": "new-123"}
        created_resource = MagicMock()
        created_resource.keys = MagicMock(return_value=resource_data.keys())
        created_resource.__getitem__ = lambda self, key: resource_data[key]
        created_resource.__iter__ = lambda self: iter(resource_data)
        mock_resource = MagicMock()
        mock_resource.save = AsyncMock(return_value=created_resource)
        client.resource = MagicMock(return_value=mock_resource)
        return client

    @pytest.mark.asyncio
    async def test_create_success(self, mcp, mock_fhir_client, mock_ctx):
        """Should create resource successfully."""
        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_fhir_client):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                create = tools["create"].fn

                result = await create(
                    platform_id="aetna",
                    resource_type="Patient",
                    resource={"resourceType": "Patient", "name": [{"family": "Smith"}]},
                    ctx=mock_ctx,
                )

        assert result["resourceType"] == "Patient"
        mock_fhir_client.resource.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_invalid_platform_id(self, mcp, mock_ctx):
        """Should return validation error for invalid platform_id."""
        tools = mcp._tool_manager._tools
        create = tools["create"].fn

        result = await create(
            platform_id="",
            resource_type="Patient",
            resource={"resourceType": "Patient"},
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_create_invalid_resource_type(self, mcp, mock_ctx):
        """Should return validation error for invalid resource_type."""
        tools = mcp._tool_manager._tools
        create = tools["create"].fn

        result = await create(
            platform_id="aetna",
            resource_type="invalid",
            resource={"resourceType": "Patient"},
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"


class TestUpdate:
    """Tests for update tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_fhir_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        # Create a dict-like mock that supports dict() conversion
        resource_data = {"resourceType": "Patient", "id": "123"}
        updated_resource = MagicMock()
        updated_resource.keys = MagicMock(return_value=resource_data.keys())
        updated_resource.__getitem__ = lambda self, key: resource_data[key]
        updated_resource.__iter__ = lambda self: iter(resource_data)
        mock_resource = MagicMock()
        mock_resource.save = AsyncMock(return_value=updated_resource)
        client.resource = MagicMock(return_value=mock_resource)
        return client

    @pytest.mark.asyncio
    async def test_update_success(self, mcp, mock_fhir_client, mock_ctx):
        """Should update resource successfully."""
        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_fhir_client):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                update = tools["update"].fn

                result = await update(
                    platform_id="aetna",
                    resource_type="Patient",
                    resource_id="123",
                    resource={"resourceType": "Patient", "name": [{"family": "Jones"}]},
                    ctx=mock_ctx,
                )

        assert result["resourceType"] == "Patient"

    @pytest.mark.asyncio
    async def test_update_sets_resource_id(self, mcp, mock_fhir_client, mock_ctx):
        """Should set resource ID in the resource data."""
        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_fhir_client):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                update = tools["update"].fn

                resource_data = {"resourceType": "Patient"}
                await update(
                    platform_id="aetna",
                    resource_type="Patient",
                    resource_id="123",
                    resource=resource_data,
                    ctx=mock_ctx,
                )

        # Check that id was set in the resource
        assert resource_data["id"] == "123"

    @pytest.mark.asyncio
    async def test_update_invalid_resource_id(self, mcp, mock_ctx):
        """Should return validation error for invalid resource_id."""
        tools = mcp._tool_manager._tools
        update = tools["update"].fn

        result = await update(
            platform_id="aetna",
            resource_type="Patient",
            resource_id="",
            resource={"resourceType": "Patient"},
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"


class TestDelete:
    """Tests for delete tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_fhir_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        client = MagicMock()
        mock_resource = MagicMock()
        mock_resource.delete = AsyncMock()
        client.resource = MagicMock(return_value=mock_resource)
        return client

    @pytest.mark.asyncio
    async def test_delete_success(self, mcp, mock_fhir_client, mock_ctx):
        """Should delete resource successfully."""
        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_fhir_client):
            with patch("app.mcp.tools.fhir.audit_log"):
                tools = mcp._tool_manager._tools
                delete = tools["delete"].fn

                result = await delete(
                    platform_id="aetna",
                    resource_type="Patient",
                    resource_id="123",
                    ctx=mock_ctx,
                )

        assert result["success"] is True
        assert "Patient/123" in result["message"]

    @pytest.mark.asyncio
    async def test_delete_invalid_platform_id(self, mcp, mock_ctx):
        """Should return validation error for invalid platform_id."""
        tools = mcp._tool_manager._tools
        delete = tools["delete"].fn

        result = await delete(
            platform_id="",
            resource_type="Patient",
            resource_id="123",
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_delete_invalid_resource_type(self, mcp, mock_ctx):
        """Should return validation error for invalid resource_type."""
        tools = mcp._tool_manager._tools
        delete = tools["delete"].fn

        result = await delete(
            platform_id="aetna",
            resource_type="invalid",
            resource_id="123",
            ctx=mock_ctx,
        )

        assert result["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_delete_resource_not_found(self, mcp, mock_ctx):
        """Should return error when resource not found."""
        mock_client = MagicMock()
        mock_resource = MagicMock()
        mock_resource.delete = AsyncMock(side_effect=ResourceNotFound())
        mock_client.resource = MagicMock(return_value=mock_resource)

        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_client):
            tools = mcp._tool_manager._tools
            delete = tools["delete"].fn

            result = await delete(
                platform_id="aetna",
                resource_type="Patient",
                resource_id="nonexistent",
                ctx=mock_ctx,
            )

        assert result["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_delete_operation_outcome(self, mcp, mock_ctx):
        """Should handle OperationOutcome exception."""
        mock_client = MagicMock()
        mock_resource = MagicMock()
        mock_resource.delete = AsyncMock(side_effect=OperationOutcome())
        mock_client.resource = MagicMock(return_value=mock_resource)

        with patch("app.mcp.tools.fhir.get_fhir_client", return_value=mock_client):
            tools = mcp._tool_manager._tools
            delete = tools["delete"].fn

            result = await delete(
                platform_id="aetna",
                resource_type="Patient",
                resource_id="123",
                ctx=mock_ctx,
            )

        assert result["error"] == "operation_outcome"
