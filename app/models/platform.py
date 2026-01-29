"""
Pydantic models for platform information.
"""

from pydantic import BaseModel, Field


class PlatformInfo(BaseModel):
    """Information about a platform (payer or EHR)."""

    id: str = Field(description="Platform identifier")
    name: str | None = Field(default=None, description="Platform display name")
    type: str | None = Field(default=None, description="Platform type (payer, ehr, sandbox)")
    fhir_base_url: str | None = Field(default=None, description="FHIR API base URL")
    developer_portal: str | None = Field(default=None, description="Developer portal URL")
    has_oauth: bool = Field(default=False, description="Whether OAuth is configured")
    verification_status: str | None = Field(default=None, description="Verification status")


class PlatformCapabilitiesResponse(BaseModel):
    """Platform capabilities summary."""

    patient_access: bool = Field(default=False)
    provider_directory: bool = Field(default=False)
    patient_everything: bool = Field(default=False)
    bulk_data: bool = Field(default=False)


class PlatformDetailResponse(BaseModel):
    """Detailed platform information."""

    id: str = Field(description="Platform identifier")
    name: str = Field(description="Platform name")
    display_name: str | None = Field(default=None, description="Display name")
    type: str | None = Field(default=None, description="Platform type")
    fhir_base_url: str | None = Field(default=None, description="FHIR API base URL")
    sandbox_url: str | None = Field(default=None, description="Sandbox URL")
    developer_portal: str | None = Field(default=None, description="Developer portal URL")
    support_email: str | None = Field(default=None, description="Support email")
    fhir_version: str | None = Field(default=None, description="FHIR version (R4, R5)")
    capabilities: PlatformCapabilitiesResponse = Field(
        default_factory=PlatformCapabilitiesResponse, description="FHIR capabilities"
    )
    has_oauth: bool = Field(default=False, description="Whether OAuth is configured")
    oauth_authorize_url: str | None = Field(default=None, description="OAuth authorize URL")
    verification_status: str | None = Field(default=None)


class PlatformListResponse(BaseModel):
    """Response for listing all platforms."""

    platforms: list[PlatformInfo] = Field(default_factory=list, description="List of platforms")
    total: int = Field(description="Total number of platforms")
