"""
SMART on FHIR launch framework implementation.

This module provides SMART App Launch support including:
- EHR Launch and Standalone Launch
- Launch context handling (patient, encounter, user)
- Scope management and parsing
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.config.logging import get_logger

logger = get_logger(__name__)


class SmartLaunchType(Enum):
    """SMART launch types."""

    EHR_LAUNCH = "ehr"
    STANDALONE = "standalone"


class SmartScopeCategory(Enum):
    """SMART scope categories."""

    PATIENT = "patient"
    USER = "user"
    SYSTEM = "system"
    LAUNCH = "launch"
    OPENID = "openid"
    FHIRUSER = "fhirUser"
    OFFLINE = "offline_access"


@dataclass
class SmartScope:
    """Parsed SMART scope."""

    raw: str
    category: SmartScopeCategory | None = None
    resource_type: str | None = None
    permissions: list[str] = field(default_factory=list)

    @property
    def can_read(self) -> bool:
        """Check if scope allows read access."""
        return "read" in self.permissions or "*" in self.permissions

    @property
    def can_write(self) -> bool:
        """Check if scope allows write access."""
        return "write" in self.permissions or "*" in self.permissions

    def __str__(self) -> str:
        return self.raw


def parse_smart_scopes(scope_string: str) -> list[SmartScope]:
    """
    Parse SMART scopes from a space-separated string.

    Supports SMART v1 and v2 scope formats:
    - v1: patient/Observation.read, user/Patient.*, system/*.*
    - v2: patient/Observation.rs, user/Patient.cruds

    Args:
        scope_string: Space-separated scope string

    Returns:
        List of parsed SmartScope objects
    """
    scopes = []

    for raw_scope in scope_string.split():
        scope = SmartScope(raw=raw_scope)

        # Handle special scopes
        if raw_scope == "openid":
            scope.category = SmartScopeCategory.OPENID
            scopes.append(scope)
            continue
        elif raw_scope == "fhirUser":
            scope.category = SmartScopeCategory.FHIRUSER
            scopes.append(scope)
            continue
        elif raw_scope == "offline_access":
            scope.category = SmartScopeCategory.OFFLINE
            scopes.append(scope)
            continue
        elif raw_scope.startswith("launch"):
            scope.category = SmartScopeCategory.LAUNCH
            # Extract context if present (e.g., launch/patient)
            if "/" in raw_scope:
                scope.resource_type = raw_scope.split("/")[1]
            scopes.append(scope)
            continue

        # Parse resource scopes (patient/Observation.read)
        if "/" in raw_scope and "." in raw_scope:
            try:
                category_part, rest = raw_scope.split("/", 1)
                resource_part, permission_part = rest.rsplit(".", 1)

                # Determine category
                if category_part == "patient":
                    scope.category = SmartScopeCategory.PATIENT
                elif category_part == "user":
                    scope.category = SmartScopeCategory.USER
                elif category_part == "system":
                    scope.category = SmartScopeCategory.SYSTEM

                # Set resource type
                scope.resource_type = resource_part

                # Parse permissions
                if permission_part == "*":
                    scope.permissions = ["read", "write", "delete"]
                elif permission_part == "read":
                    scope.permissions = ["read"]
                elif permission_part == "write":
                    scope.permissions = ["write"]
                else:
                    # SMART v2 format (cruds)
                    perm_map = {
                        "c": "create",
                        "r": "read",
                        "u": "update",
                        "d": "delete",
                        "s": "search",
                    }
                    scope.permissions = [perm_map[c] for c in permission_part if c in perm_map]

            except ValueError:
                logger.warning(f"Failed to parse scope: {raw_scope}")

        scopes.append(scope)

    return scopes


def build_smart_scopes(
    resource_types: list[str],
    category: SmartScopeCategory = SmartScopeCategory.PATIENT,
    permissions: list[str] | None = None,
    include_launch: bool = True,
    include_openid: bool = True,
    include_offline: bool = False,
) -> str:
    """
    Build a SMART scope string.

    Args:
        resource_types: List of FHIR resource types
        category: Scope category (patient, user, system)
        permissions: Permission types (read, write, or *)
        include_launch: Include launch scope
        include_openid: Include openid and fhirUser scopes
        include_offline: Include offline_access scope

    Returns:
        Space-separated scope string
    """
    scopes = []

    # Add standard scopes
    if include_openid:
        scopes.extend(["openid", "fhirUser"])
    if include_launch:
        scopes.append("launch")
    if include_offline:
        scopes.append("offline_access")

    # Build resource scopes
    perm_string = ".".join(permissions) if permissions else "*"
    for resource_type in resource_types:
        scopes.append(f"{category.value}/{resource_type}.{perm_string}")

    return " ".join(scopes)


@dataclass
class SmartLaunchContext:
    """
    SMART launch context from token response.

    Contains context information returned after successful authorization.
    """

    # Required context
    patient: str | None = None  # Patient ID in context
    encounter: str | None = None  # Encounter ID in context
    user: str | None = None  # User ID (fhirUser)

    # Optional context
    location: str | None = None
    intent: str | None = None
    need_patient_banner: bool | None = None
    smart_style_url: str | None = None

    # Token info
    access_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None
    scope: str | None = None
    id_token: str | None = None
    refresh_token: str | None = None

    @classmethod
    def from_token_response(cls, response: dict[str, Any]) -> "SmartLaunchContext":
        """
        Create launch context from token response.

        Args:
            response: Token response dictionary

        Returns:
            SmartLaunchContext instance
        """
        return cls(
            patient=response.get("patient"),
            encounter=response.get("encounter"),
            user=response.get("fhirUser") or response.get("user"),
            location=response.get("location"),
            intent=response.get("intent"),
            need_patient_banner=response.get("need_patient_banner"),
            smart_style_url=response.get("smart_style_url"),
            access_token=response.get("access_token"),
            token_type=response.get("token_type"),
            expires_in=response.get("expires_in"),
            scope=response.get("scope"),
            id_token=response.get("id_token"),
            refresh_token=response.get("refresh_token"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            k: v
            for k, v in {
                "patient": self.patient,
                "encounter": self.encounter,
                "user": self.user,
                "location": self.location,
                "intent": self.intent,
                "need_patient_banner": self.need_patient_banner,
                "smart_style_url": self.smart_style_url,
                "access_token": self.access_token,
                "token_type": self.token_type,
                "expires_in": self.expires_in,
                "scope": self.scope,
                "id_token": self.id_token,
                "refresh_token": self.refresh_token,
            }.items()
            if v is not None
        }

    @property
    def has_patient_context(self) -> bool:
        """Check if patient context is available."""
        return self.patient is not None

    @property
    def has_encounter_context(self) -> bool:
        """Check if encounter context is available."""
        return self.encounter is not None

    @property
    def parsed_scopes(self) -> list[SmartScope]:
        """Get parsed scopes."""
        if self.scope:
            return parse_smart_scopes(self.scope)
        return []


# Common SMART scope sets
SMART_PATIENT_READ_SCOPES = [
    "openid",
    "fhirUser",
    "launch/patient",
    "patient/Patient.read",
    "patient/Observation.read",
    "patient/Condition.read",
    "patient/MedicationRequest.read",
    "patient/AllergyIntolerance.read",
    "patient/Immunization.read",
    "patient/Procedure.read",
    "patient/CarePlan.read",
    "patient/CareTeam.read",
    "patient/Goal.read",
]

SMART_CLINICIAN_SCOPES = [
    "openid",
    "fhirUser",
    "launch",
    "user/Patient.read",
    "user/Encounter.read",
    "user/Observation.*",
    "user/Condition.*",
    "user/MedicationRequest.*",
    "user/DiagnosticReport.read",
    "user/Procedure.*",
]

SMART_SYSTEM_SCOPES = [
    "system/Patient.read",
    "system/Coverage.read",
    "system/Claim.*",
    "system/ClaimResponse.read",
    "system/Task.*",
]
