"""
Coverage REST API endpoints.

Provides coverage and prior authorization endpoints:
- POST /api/coverage/{platform_id}/requirements - Check coverage requirements
- POST /api/coverage/{platform_id}/questionnaire-package - Fetch questionnaire package
- GET /api/coverage/{platform_id}/rules/{procedure_code} - Get platform rules
"""

from typing import Any

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field

from app.audit import AuditEvent, audit_log
from app.routers.validation import (
    handle_platform_error,
    validate_platform_id,
    validate_procedure_code,
    validate_resource_id,
)
from app.services.coverage import (
    check_coverage_requirements,
    fetch_questionnaire_package,
    get_platform_rules,
)
from app.services.fhir_client import get_fhir_client
from app.utils import extract_bearer_token

router = APIRouter(prefix="/api/coverage", tags=["coverage"])


# Request/Response models
class CoverageRequirementsRequest(BaseModel):
    """Request body for coverage requirements check."""

    patient_id: str = Field(..., description="FHIR Patient resource ID")
    coverage_id: str = Field(..., description="FHIR Coverage resource ID")
    procedure_code: str = Field(..., description="CPT/HCPCS procedure code")
    code_system: str = Field(
        default="http://www.ama-assn.org/go/cpt",
        description="Code system URL for the procedure code",
    )


class QuestionnairePackageRequest(BaseModel):
    """Request body for questionnaire package fetch."""

    coverage_id: str = Field(..., description="FHIR Coverage resource ID")
    questionnaire_url: str | None = Field(
        default=None, description="Optional specific questionnaire canonical URL"
    )
    raw_format: bool = Field(default=False, description="If true, return raw FHIR Bundle")


@router.post("/{platform_id}/requirements")
async def check_requirements(
    platform_id: str,
    request: CoverageRequirementsRequest,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Check if prior authorization is required for a procedure.

    This endpoint simulates the CRD (Coverage Requirements Discovery) workflow.

    Args:
        platform_id: The platform identifier
        request: Coverage requirements request body
        authorization: Optional Bearer token

    Returns:
        Coverage requirement status and details
    """
    validate_platform_id(platform_id)
    validate_resource_id(request.patient_id, "patient_id")
    validate_resource_id(request.coverage_id, "coverage_id")
    validate_procedure_code(request.procedure_code, request.code_system)

    access_token = extract_bearer_token(authorization)

    try:
        client = get_fhir_client(platform_id, access_token)
        result = await check_coverage_requirements(
            client=client,
            patient_id=request.patient_id,
            coverage_id=request.coverage_id,
            procedure_code=request.procedure_code,
            code_system=request.code_system,
            platform_id=platform_id,
        )

        audit_log(
            AuditEvent.COVERAGE_CHECK,
            platform_id=platform_id,
            details={
                "patient_id": request.patient_id,
                "procedure_code": request.procedure_code,
                "status": result.status.value,
            },
        )

        return result.model_dump(exclude_none=True)

    except Exception as e:
        handle_platform_error(e, platform_id=platform_id)


@router.post("/{platform_id}/questionnaire-package")
async def get_questionnaire_package(
    platform_id: str,
    request: QuestionnairePackageRequest,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Fetch questionnaire package for prior authorization documentation.

    This endpoint executes the DTR $questionnaire-package operation.

    Args:
        platform_id: The platform identifier
        request: Questionnaire package request body
        authorization: Optional Bearer token

    Returns:
        Transformed questionnaires or raw FHIR Bundle
    """
    validate_platform_id(platform_id)
    validate_resource_id(request.coverage_id, "coverage_id")

    access_token = extract_bearer_token(authorization)

    try:
        client = get_fhir_client(platform_id, access_token)
        result = await fetch_questionnaire_package(
            client=client,
            coverage_id=request.coverage_id,
            questionnaire_url=request.questionnaire_url,
            raw_format=request.raw_format,
            platform_id=platform_id,
        )

        audit_log(
            AuditEvent.QUESTIONNAIRE_FETCH,
            platform_id=platform_id,
            details={"coverage_id": request.coverage_id},
        )

        if isinstance(result, dict):
            return result
        return result.model_dump(exclude_none=True)

    except Exception as e:
        handle_platform_error(e, platform_id=platform_id)


@router.get("/{platform_id}/rules/{procedure_code}")
async def get_rules(
    platform_id: str,
    procedure_code: str,
    code_system: str = Query(
        default="http://www.ama-assn.org/go/cpt",
        description="Code system URL for the procedure code",
    ),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Get platform policy rules for a procedure.

    Args:
        platform_id: The platform identifier
        procedure_code: CPT/HCPCS procedure code
        code_system: Code system URL
        authorization: Optional Bearer token

    Returns:
        Policy rules with markdown summary
    """
    validate_platform_id(platform_id)
    validate_procedure_code(procedure_code, code_system)

    access_token = extract_bearer_token(authorization)

    try:
        client = get_fhir_client(platform_id, access_token)
        result = await get_platform_rules(
            client=client,
            platform_id=platform_id,
            procedure_code=procedure_code,
            code_system=code_system,
        )

        audit_log(
            AuditEvent.PLATFORM_RULES_FETCH,
            platform_id=platform_id,
            details={"procedure_code": procedure_code},
        )

        return result.model_dump(exclude_none=True)

    except Exception as e:
        handle_platform_error(e, platform_id=platform_id)
