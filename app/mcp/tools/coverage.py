"""
Coverage and prior authorization tools.

Thin wrappers around app.services.coverage.
Tokens are auto-fetched from session - clients should use auth tools to authenticate.
"""

from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from app.audit import AuditEvent, audit_log
from app.mcp.errors import error_response, handle_exception
from app.mcp.tools.fhir import get_access_token
from app.mcp.validation import validate_platform_id, validate_resource_id
from app.services.coverage import (
    check_coverage_requirements,
    fetch_questionnaire_package,
    get_platform_rules,
)
from app.services.fhir_client import get_fhir_client


def register_coverage_tools(mcp: FastMCP) -> None:
    """Register coverage and prior auth tools."""

    @mcp.tool(description="Check if prior authorization is required for a procedure.")
    async def check_prior_auth(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        patient_id: Annotated[str, Field(description="FHIR Patient resource ID")],
        coverage_id: Annotated[str, Field(description="FHIR Coverage resource ID")],
        procedure_code: Annotated[
            str, Field(description="CPT/HCPCS procedure code (e.g., '27447')")
        ],
        ctx: Context,
        code_system: Annotated[
            str, Field(description="Code system URL")
        ] = "http://www.ama-assn.org/go/cpt",
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
    ) -> dict[str, Any]:
        """Check coverage requirements for a procedure."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_id(patient_id):
            return error_response("validation_error", f"Invalid patient_id: {err}")
        if err := validate_resource_id(coverage_id):
            return error_response("validation_error", f"Invalid coverage_id: {err}")

        try:
            token = await get_access_token(ctx, platform_id, auth_handle)
            client = get_fhir_client(platform_id, token)
            result = await check_coverage_requirements(
                client=client,
                patient_id=patient_id,
                coverage_id=coverage_id,
                procedure_code=procedure_code,
                code_system=code_system,
                platform_id=platform_id,
            )
            audit_log(
                AuditEvent.RESOURCE_READ,
                platform_id=platform_id,
                resource_type="CoverageRequirements",
            )
            return result.model_dump(exclude_none=True)
        except Exception as e:
            return handle_exception(e, "check_prior_auth")

    @mcp.tool(description="Fetch DTR questionnaire package for prior auth documentation.")
    async def get_questionnaire_package(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        coverage_id: Annotated[str, Field(description="FHIR Coverage resource ID")],
        ctx: Context,
        questionnaire_url: Annotated[
            str | None, Field(description="Specific questionnaire canonical URL")
        ] = None,
        raw_format: Annotated[
            bool, Field(description="Return raw FHIR Bundle instead of transformed")
        ] = False,
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
    ) -> dict[str, Any]:
        """Fetch questionnaire package for prior authorization."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)
        if err := validate_resource_id(coverage_id):
            return error_response("validation_error", f"Invalid coverage_id: {err}")

        try:
            token = await get_access_token(ctx, platform_id, auth_handle)
            client = get_fhir_client(platform_id, token)
            result = await fetch_questionnaire_package(
                client=client,
                coverage_id=coverage_id,
                questionnaire_url=questionnaire_url,
                raw_format=raw_format,
                platform_id=platform_id,
            )
            audit_log(
                AuditEvent.RESOURCE_READ,
                platform_id=platform_id,
                resource_type="QuestionnairePackage",
            )
            if isinstance(result, dict):
                return result
            return result.model_dump(exclude_none=True)
        except Exception as e:
            return handle_exception(e, "get_questionnaire_package")

    @mcp.tool(description="Get platform policy rules for a procedure code.")
    async def get_policy_rules(
        platform_id: Annotated[str, Field(description="Platform identifier")],
        procedure_code: Annotated[str, Field(description="CPT/HCPCS procedure code")],
        ctx: Context,
        code_system: Annotated[
            str, Field(description="Code system URL")
        ] = "http://www.ama-assn.org/go/cpt",
        auth_handle: Annotated[
            str | None, Field(description="Auth handle from start_auth (for authenticated requests)")
        ] = None,
    ) -> dict[str, Any]:
        """Get medical policy rules for a procedure."""
        if err := validate_platform_id(platform_id):
            return error_response("validation_error", err)

        try:
            token = await get_access_token(ctx, platform_id, auth_handle)
            client = get_fhir_client(platform_id, token)
            result = await get_platform_rules(
                client=client,
                platform_id=platform_id,
                procedure_code=procedure_code,
                code_system=code_system,
            )
            audit_log(
                AuditEvent.RESOURCE_READ, platform_id=platform_id, resource_type="PlatformRules"
            )
            return result.model_dump(exclude_none=True)
        except Exception as e:
            return handle_exception(e, "get_policy_rules")
