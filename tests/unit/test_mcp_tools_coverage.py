"""
Tests for MCP coverage tools.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from app.mcp.tools.coverage import register_coverage_tools
from app.models.coverage import (
    CoverageRequirement,
    CoverageRequirementStatus,
    PlatformRulesResult,
    QuestionnairePackageResult,
)
from app.services.fhir_client import PlatformNotConfiguredError, PlatformNotFoundError


class TestCheckPriorAuth:
    """Tests for check_prior_auth tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_coverage_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        return MagicMock()

    @pytest.fixture
    def mock_coverage_result(self):
        """Create mock coverage requirement result."""
        return CoverageRequirement(
            status=CoverageRequirementStatus.REQUIRED,
            procedure_code="27447",
            code_system="http://www.ama-assn.org/go/cpt",
            coverage_id="cov-123",
            patient_id="pat-456",
            documentation_required=True,
            questionnaire_url="http://example.org/Questionnaire/knee",
            reason="Prior authorization required for total knee replacement",
        )

    @pytest.mark.asyncio
    async def test_check_prior_auth_success(self, mcp, mock_fhir_client, mock_coverage_result):
        """Should return coverage requirements for valid request."""
        with (
            patch("app.mcp.tools.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.mcp.tools.coverage.check_coverage_requirements",
                new_callable=AsyncMock,
                return_value=mock_coverage_result,
            ),
            patch("app.mcp.tools.coverage.audit_log"),
        ):
            tools = mcp._tool_manager._tools
            check_prior_auth = tools["check_prior_auth"].fn

            result = await check_prior_auth(
                platform_id="aetna",
                patient_id="pat-456",
                coverage_id="cov-123",
                procedure_code="27447",
            )

        assert result["status"] == "required"
        assert result["procedure_code"] == "27447"
        assert result["documentation_required"] is True

    @pytest.mark.asyncio
    async def test_check_prior_auth_with_custom_code_system(self, mcp, mock_fhir_client, mock_coverage_result):
        """Should use custom code system."""
        with (
            patch("app.mcp.tools.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.mcp.tools.coverage.check_coverage_requirements",
                new_callable=AsyncMock,
                return_value=mock_coverage_result,
            ) as mock_check,
            patch("app.mcp.tools.coverage.audit_log"),
        ):
            tools = mcp._tool_manager._tools
            check_prior_auth = tools["check_prior_auth"].fn

            await check_prior_auth(
                platform_id="aetna",
                patient_id="pat-456",
                coverage_id="cov-123",
                procedure_code="G0219",
                code_system="https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets",
            )

        mock_check.assert_called_once()
        call_kwargs = mock_check.call_args.kwargs
        assert call_kwargs["code_system"] == "https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"

    @pytest.mark.asyncio
    async def test_check_prior_auth_invalid_platform_id(self, mcp):
        """Should return validation error for invalid platform_id."""
        tools = mcp._tool_manager._tools
        check_prior_auth = tools["check_prior_auth"].fn

        result = await check_prior_auth(
            platform_id="invalid@platform!",
            patient_id="pat-456",
            coverage_id="cov-123",
            procedure_code="27447",
        )

        assert result["error"] == "validation_error"
        assert "Invalid platform_id" in result["message"]

    @pytest.mark.asyncio
    async def test_check_prior_auth_invalid_patient_id(self, mcp):
        """Should return validation error for invalid patient_id."""
        tools = mcp._tool_manager._tools
        check_prior_auth = tools["check_prior_auth"].fn

        result = await check_prior_auth(
            platform_id="aetna",
            patient_id="",
            coverage_id="cov-123",
            procedure_code="27447",
        )

        assert result["error"] == "validation_error"
        assert "Invalid patient_id" in result["message"]

    @pytest.mark.asyncio
    async def test_check_prior_auth_invalid_coverage_id(self, mcp):
        """Should return validation error for invalid coverage_id."""
        tools = mcp._tool_manager._tools
        check_prior_auth = tools["check_prior_auth"].fn

        result = await check_prior_auth(
            platform_id="aetna",
            patient_id="pat-456",
            coverage_id="bad@id!",
            procedure_code="27447",
        )

        assert result["error"] == "validation_error"
        assert "Invalid coverage_id" in result["message"]

    @pytest.mark.asyncio
    async def test_check_prior_auth_platform_not_found(self, mcp):
        """Should return error when platform not found."""
        with patch(
            "app.mcp.tools.coverage.get_fhir_client",
            side_effect=PlatformNotFoundError("unknown"),
        ):
            tools = mcp._tool_manager._tools
            check_prior_auth = tools["check_prior_auth"].fn

            result = await check_prior_auth(
                platform_id="unknown",
                patient_id="pat-456",
                coverage_id="cov-123",
                procedure_code="27447",
            )

        assert result["error"] == "platform_not_found"

    @pytest.mark.asyncio
    async def test_check_prior_auth_platform_not_configured(self, mcp):
        """Should return error when platform not configured."""
        with patch(
            "app.mcp.tools.coverage.get_fhir_client",
            side_effect=PlatformNotConfiguredError("aetna"),
        ):
            tools = mcp._tool_manager._tools
            check_prior_auth = tools["check_prior_auth"].fn

            result = await check_prior_auth(
                platform_id="aetna",
                patient_id="pat-456",
                coverage_id="cov-123",
                procedure_code="27447",
            )

        assert result["error"] == "platform_not_configured"


class TestGetQuestionnairePackage:
    """Tests for get_questionnaire_package tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_coverage_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        return MagicMock()

    @pytest.fixture
    def mock_package_result(self):
        """Create mock questionnaire package result."""
        return QuestionnairePackageResult(
            questionnaires=[],
            value_sets=None,
            libraries=None,
        )

    @pytest.fixture
    def mock_raw_bundle(self):
        """Create mock raw FHIR bundle."""
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Questionnaire",
                        "id": "test-q",
                    }
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_get_questionnaire_package_success(self, mcp, mock_fhir_client, mock_package_result):
        """Should return questionnaire package for valid request."""
        with (
            patch("app.mcp.tools.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.mcp.tools.coverage.fetch_questionnaire_package",
                new_callable=AsyncMock,
                return_value=mock_package_result,
            ),
            patch("app.mcp.tools.coverage.audit_log"),
        ):
            tools = mcp._tool_manager._tools
            get_questionnaire_package = tools["get_questionnaire_package"].fn

            result = await get_questionnaire_package(
                platform_id="aetna",
                coverage_id="cov-123",
            )

        assert "questionnaires" in result

    @pytest.mark.asyncio
    async def test_get_questionnaire_package_raw_format(self, mcp, mock_fhir_client, mock_raw_bundle):
        """Should return raw bundle when raw_format=True."""
        with (
            patch("app.mcp.tools.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.mcp.tools.coverage.fetch_questionnaire_package",
                new_callable=AsyncMock,
                return_value=mock_raw_bundle,
            ),
            patch("app.mcp.tools.coverage.audit_log"),
        ):
            tools = mcp._tool_manager._tools
            get_questionnaire_package = tools["get_questionnaire_package"].fn

            result = await get_questionnaire_package(
                platform_id="aetna",
                coverage_id="cov-123",
                raw_format=True,
            )

        assert result["resourceType"] == "Bundle"

    @pytest.mark.asyncio
    async def test_get_questionnaire_package_with_url(self, mcp, mock_fhir_client, mock_package_result):
        """Should pass questionnaire URL to service."""
        with (
            patch("app.mcp.tools.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.mcp.tools.coverage.fetch_questionnaire_package",
                new_callable=AsyncMock,
                return_value=mock_package_result,
            ) as mock_fetch,
            patch("app.mcp.tools.coverage.audit_log"),
        ):
            tools = mcp._tool_manager._tools
            get_questionnaire_package = tools["get_questionnaire_package"].fn

            await get_questionnaire_package(
                platform_id="aetna",
                coverage_id="cov-123",
                questionnaire_url="http://example.org/Questionnaire/knee",
            )

        mock_fetch.assert_called_once()
        call_kwargs = mock_fetch.call_args.kwargs
        assert call_kwargs["questionnaire_url"] == "http://example.org/Questionnaire/knee"

    @pytest.mark.asyncio
    async def test_get_questionnaire_package_invalid_platform_id(self, mcp):
        """Should return validation error for invalid platform_id."""
        tools = mcp._tool_manager._tools
        get_questionnaire_package = tools["get_questionnaire_package"].fn

        result = await get_questionnaire_package(
            platform_id="",
            coverage_id="cov-123",
        )

        assert result["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_get_questionnaire_package_invalid_coverage_id(self, mcp):
        """Should return validation error for invalid coverage_id."""
        tools = mcp._tool_manager._tools
        get_questionnaire_package = tools["get_questionnaire_package"].fn

        result = await get_questionnaire_package(
            platform_id="aetna",
            coverage_id="",
        )

        assert result["error"] == "validation_error"
        assert "Invalid coverage_id" in result["message"]

    @pytest.mark.asyncio
    async def test_get_questionnaire_package_platform_not_found(self, mcp):
        """Should return error when platform not found."""
        with patch(
            "app.mcp.tools.coverage.get_fhir_client",
            side_effect=PlatformNotFoundError("unknown"),
        ):
            tools = mcp._tool_manager._tools
            get_questionnaire_package = tools["get_questionnaire_package"].fn

            result = await get_questionnaire_package(
                platform_id="unknown",
                coverage_id="cov-123",
            )

        assert result["error"] == "platform_not_found"


class TestGetPolicyRules:
    """Tests for get_policy_rules tool."""

    @pytest.fixture
    def mcp(self):
        """Create MCP instance with registered tools."""
        mcp = FastMCP("test")
        register_coverage_tools(mcp)
        return mcp

    @pytest.fixture
    def mock_fhir_client(self):
        """Create mock FHIR client."""
        return MagicMock()

    @pytest.fixture
    def mock_rules_result(self):
        """Create mock platform rules result."""
        return PlatformRulesResult(
            platform_id="aetna",
            procedure_code="27447",
            code_system="http://www.ama-assn.org/go/cpt",
            rules=[],
            markdown_summary="No policy rules found for procedure code 27447",
        )

    @pytest.mark.asyncio
    async def test_get_policy_rules_success(self, mcp, mock_fhir_client, mock_rules_result):
        """Should return policy rules for valid request."""
        with (
            patch("app.mcp.tools.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.mcp.tools.coverage.get_platform_rules",
                new_callable=AsyncMock,
                return_value=mock_rules_result,
            ),
            patch("app.mcp.tools.coverage.audit_log"),
        ):
            tools = mcp._tool_manager._tools
            get_policy_rules = tools["get_policy_rules"].fn

            result = await get_policy_rules(
                platform_id="aetna",
                procedure_code="27447",
            )

        assert result["platform_id"] == "aetna"
        assert result["procedure_code"] == "27447"
        assert "markdown_summary" in result

    @pytest.mark.asyncio
    async def test_get_policy_rules_with_custom_code_system(self, mcp, mock_fhir_client, mock_rules_result):
        """Should use custom code system."""
        with (
            patch("app.mcp.tools.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.mcp.tools.coverage.get_platform_rules",
                new_callable=AsyncMock,
                return_value=mock_rules_result,
            ) as mock_get_rules,
            patch("app.mcp.tools.coverage.audit_log"),
        ):
            tools = mcp._tool_manager._tools
            get_policy_rules = tools["get_policy_rules"].fn

            await get_policy_rules(
                platform_id="aetna",
                procedure_code="G0219",
                code_system="https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets",
            )

        mock_get_rules.assert_called_once()
        call_kwargs = mock_get_rules.call_args.kwargs
        assert call_kwargs["code_system"] == "https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"

    @pytest.mark.asyncio
    async def test_get_policy_rules_invalid_platform_id(self, mcp):
        """Should return validation error for invalid platform_id."""
        tools = mcp._tool_manager._tools
        get_policy_rules = tools["get_policy_rules"].fn

        result = await get_policy_rules(
            platform_id="invalid@platform!",
            procedure_code="27447",
        )

        assert result["error"] == "validation_error"

    @pytest.mark.asyncio
    async def test_get_policy_rules_platform_not_found(self, mcp):
        """Should return error when platform not found."""
        with patch(
            "app.mcp.tools.coverage.get_fhir_client",
            side_effect=PlatformNotFoundError("unknown"),
        ):
            tools = mcp._tool_manager._tools
            get_policy_rules = tools["get_policy_rules"].fn

            result = await get_policy_rules(
                platform_id="unknown",
                procedure_code="27447",
            )

        assert result["error"] == "platform_not_found"

    @pytest.mark.asyncio
    async def test_get_policy_rules_general_exception(self, mcp, mock_fhir_client):
        """Should handle general exceptions gracefully."""
        with (
            patch("app.mcp.tools.coverage.get_fhir_client", return_value=mock_fhir_client),
            patch(
                "app.mcp.tools.coverage.get_platform_rules",
                new_callable=AsyncMock,
                side_effect=Exception("Service error"),
            ),
        ):
            tools = mcp._tool_manager._tools
            get_policy_rules = tools["get_policy_rules"].fn

            result = await get_policy_rules(
                platform_id="aetna",
                procedure_code="27447",
            )

        assert result["error"] == "internal_error"
