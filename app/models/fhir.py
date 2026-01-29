"""
Pydantic models for FHIR operations.
"""

from typing import Any

from pydantic import BaseModel, Field


class FHIRSearchParams(BaseModel):
    """FHIR search parameters model."""

    # Common search parameters - use aliases for FHIR _params
    count: int | None = Field(
        default=None, serialization_alias="_count", description="Number of results"
    )
    sort: str | None = Field(default=None, serialization_alias="_sort", description="Sort order")
    include: str | None = Field(
        default=None, serialization_alias="_include", description="Include references"
    )
    revinclude: str | None = Field(
        default=None, serialization_alias="_revinclude", description="Reverse include"
    )

    model_config = {"extra": "allow", "populate_by_name": True}


class FHIROperationResponse(BaseModel):
    """Generic FHIR operation response."""

    success: bool = Field(description="Whether the operation succeeded")
    resource_type: str | None = Field(default=None, description="FHIR resource type")
    resource_id: str | None = Field(default=None, description="Resource ID if applicable")
    data: dict[str, Any] | None = Field(default=None, description="Response data")
    error: str | None = Field(default=None, description="Error message if failed")


class FHIRBundleEntry(BaseModel):
    """A single entry in a FHIR Bundle."""

    fullUrl: str | None = Field(default=None)
    resource: dict[str, Any] | None = Field(default=None)
    search: dict[str, Any] | None = Field(default=None)


class FHIRBundle(BaseModel):
    """FHIR Bundle response."""

    resourceType: str = Field(default="Bundle")
    type: str = Field(description="Bundle type (searchset, batch, etc.)")
    total: int | None = Field(default=None, description="Total matching resources")
    entry: list[FHIRBundleEntry] = Field(default_factory=list, description="Bundle entries")
    link: list[dict[str, str]] | None = Field(default=None, description="Pagination links")


class OperationOutcomeIssue(BaseModel):
    """A single issue in an OperationOutcome."""

    severity: str = Field(description="fatal | error | warning | information")
    code: str = Field(description="Error code")
    diagnostics: str | None = Field(default=None, description="Additional diagnostic info")
    details: dict[str, Any] | None = Field(default=None)


class OperationOutcome(BaseModel):
    """FHIR OperationOutcome for error responses."""

    resourceType: str = Field(default="OperationOutcome")
    issue: list[OperationOutcomeIssue] = Field(description="List of issues")
