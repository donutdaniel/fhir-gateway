"""
SMART on FHIR scope validation.

Validates OAuth scopes before allowing FHIR operations.
Implements SMART App Launch Framework v2.0 scope semantics.
"""

import re
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException

from app.audit import AuditEvent, audit_log
from app.auth.token_manager import get_token_manager
from app.config.logging import get_logger

logger = get_logger(__name__)

# FHIR operation types
OperationType = Literal["read", "search", "create", "update", "delete"]


@dataclass
class SmartScope:
    """
    Parsed SMART on FHIR scope.

    SMART scopes follow the pattern: context/resource.permissions
    Examples:
        - patient/Patient.read
        - user/Observation.write
        - patient/*.read
        - system/*.cruds
    """

    context: str  # "patient", "user", or "system"
    resource_type: str  # FHIR resource type or "*" for wildcard
    permissions: str  # "read", "write", "*", or "cruds" string

    def allows_operation(self, resource_type: str, operation: OperationType) -> bool:
        """
        Check if this scope allows the given operation on the resource type.

        Args:
            resource_type: FHIR resource type (e.g., "Patient", "Observation")
            operation: Operation being performed

        Returns:
            True if scope allows the operation
        """
        # Check resource type match
        if self.resource_type != "*" and self.resource_type != resource_type:
            return False

        # Map operation to permission character
        operation_map = {
            "create": "c",
            "read": "r",
            "search": "r",  # Search requires read permission
            "update": "u",
            "delete": "d",
        }
        required_permission = operation_map.get(operation, "r")

        # Check permission
        if self.permissions == "*":
            return True
        if self.permissions == "read" and required_permission == "r":
            return True
        if self.permissions == "write" and required_permission in ("c", "u", "d"):
            return True
        if required_permission in self.permissions:
            return True

        return False


@dataclass
class ScopeCheckResult:
    """Result of a scope permission check."""

    allowed: bool
    reason: str
    matching_scope: SmartScope | None = None


# Regex for parsing SMART scopes
# Matches: context/resource.permission (with optional s suffix)
SMART_SCOPE_PATTERN = re.compile(
    r"^(patient|user|system|launch)/([A-Za-z*]+)\.(read|write|\*|[cruds]+)$"
)


def parse_scope(scope_str: str) -> SmartScope | None:
    """
    Parse a SMART scope string into a SmartScope object.

    Args:
        scope_str: Scope string (e.g., "patient/Patient.read")

    Returns:
        SmartScope object or None if not a valid SMART scope
    """
    match = SMART_SCOPE_PATTERN.match(scope_str)
    if not match:
        return None

    context, resource_type, permissions = match.groups()
    return SmartScope(
        context=context,
        resource_type=resource_type,
        permissions=permissions,
    )


def parse_scopes(scope_string: str | None) -> list[SmartScope]:
    """
    Parse a space-separated scope string into SmartScope objects.

    Args:
        scope_string: Space-separated scopes (e.g., "openid patient/Patient.read")

    Returns:
        List of parsed SmartScope objects (non-SMART scopes are filtered out)
    """
    if not scope_string:
        return []

    scopes = []
    for scope_str in scope_string.split():
        parsed = parse_scope(scope_str)
        if parsed:
            scopes.append(parsed)

    return scopes


def check_scope_permission(
    scopes: list[SmartScope],
    resource_type: str,
    operation: OperationType,
) -> ScopeCheckResult:
    """
    Check if the given scopes allow an operation on a resource type.

    Args:
        scopes: List of parsed SMART scopes
        resource_type: FHIR resource type to access
        operation: Operation being performed

    Returns:
        ScopeCheckResult with allowed status and reason
    """
    if not scopes:
        return ScopeCheckResult(
            allowed=False,
            reason="No SMART scopes found in token",
        )

    for scope in scopes:
        if scope.allows_operation(resource_type, operation):
            return ScopeCheckResult(
                allowed=True,
                reason=f"Allowed by scope {scope.context}/{scope.resource_type}.{scope.permissions}",
                matching_scope=scope,
            )

    # Build helpful error message
    scope_strs = [f"{s.context}/{s.resource_type}.{s.permissions}" for s in scopes]
    return ScopeCheckResult(
        allowed=False,
        reason=f"No scope grants {operation} access to {resource_type}. "
        f"Available scopes: {', '.join(scope_strs)}",
    )


async def validate_scope_for_operation(
    session_id: str | None,
    platform_id: str,
    resource_type: str,
    operation: OperationType,
    user_id: str | None = None,
) -> None:
    """
    Validate that the session has appropriate scope for a FHIR operation.

    This function checks the OAuth token scopes stored in the session
    and raises an HTTPException if access is denied.

    Args:
        session_id: Session ID (if None, validation is skipped)
        platform_id: Platform ID to check scopes for
        resource_type: FHIR resource type being accessed
        operation: Operation being performed
        user_id: Optional user ID for audit logging

    Raises:
        HTTPException: 403 if scope validation fails
    """
    # Skip validation if no session (unauthenticated request)
    if not session_id:
        return

    token_manager = get_token_manager()
    token = await token_manager.get_token(session_id, platform_id, auto_refresh=False)

    # No token = no scope restrictions (unauthenticated access)
    if not token:
        return

    # Parse scopes from token
    scopes = parse_scopes(token.scope)

    # No SMART scopes = allow (some servers don't use SMART scopes)
    if not scopes:
        logger.debug(
            "No SMART scopes in token, allowing operation",
            platform_id=platform_id,
            resource_type=resource_type,
            operation=operation,
        )
        return

    # Check scope permission
    result = check_scope_permission(scopes, resource_type, operation)

    if not result.allowed:
        # Log security violation
        audit_log(
            AuditEvent.SECURITY_SCOPE_VIOLATION,
            session_id=session_id,
            platform_id=platform_id,
            resource_type=resource_type,
            user_id=user_id,
            success=False,
            error=result.reason,
            details={
                "operation": operation,
                "scopes": token.scope,
            },
        )

        logger.warning(
            "Scope validation failed",
            platform_id=platform_id,
            resource_type=resource_type,
            operation=operation,
            reason=result.reason,
        )

        raise HTTPException(
            status_code=403,
            detail=f"Insufficient scope: {result.reason}",
        )

    logger.debug(
        "Scope validation passed",
        platform_id=platform_id,
        resource_type=resource_type,
        operation=operation,
        matching_scope=result.reason,
    )
