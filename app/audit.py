"""
Audit logging for security-relevant events.

Provides structured audit logging for authentication, token operations,
resource access, and session lifecycle events.
"""

import logging
from typing import Any

import structlog

# Create dedicated audit logger
_audit_logger = structlog.wrap_logger(
    logging.getLogger("fhir.audit"),
    wrapper_class=structlog.stdlib.BoundLogger,
)


class AuditEvent:
    """Constants for audit event types."""

    # Authentication events
    AUTH_START = "auth.start"
    AUTH_CALLBACK = "auth.callback"
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_REVOKE = "auth.revoke"

    # Token events
    TOKEN_REFRESH = "token.refresh"
    TOKEN_REFRESH_FAILURE = "token.refresh_failure"
    TOKEN_EXPIRED = "token.expired"

    # Resource access events
    RESOURCE_READ = "resource.read"
    RESOURCE_SEARCH = "resource.search"
    RESOURCE_CREATE = "resource.create"
    RESOURCE_UPDATE = "resource.update"
    RESOURCE_DELETE = "resource.delete"
    RESOURCE_OPERATION = "resource.operation"

    # Session events
    SESSION_CREATE = "session.create"
    SESSION_DESTROY = "session.destroy"
    SESSION_CLEANUP = "session.cleanup"

    # Security events
    SECURITY_INVALID_STATE = "security.invalid_state"
    SECURITY_INVALID_TOKEN = "security.invalid_token"
    SECURITY_RATE_LIMIT = "security.rate_limit"
    SECURITY_CSRF_VIOLATION = "security.csrf_violation"
    SECURITY_SESSION_MISMATCH = "security.session_mismatch"

    # Coverage events
    COVERAGE_CHECK = "coverage.check"
    QUESTIONNAIRE_FETCH = "coverage.questionnaire_fetch"
    PLATFORM_RULES_FETCH = "coverage.platform_rules_fetch"

    # Error events
    RESOURCE_ACCESS_ERROR = "error.resource_access"
    COVERAGE_ERROR = "error.coverage"
    VALIDATION_ERROR = "error.validation"
    PLATFORM_ERROR = "error.platform"


# Logging constants
SESSION_ID_VISIBLE_CHARS = 16


def truncate_session_id(session_id: str, visible_chars: int = SESSION_ID_VISIBLE_CHARS) -> str:
    """Truncate session ID for logging while preserving enough for correlation."""
    if len(session_id) > visible_chars:
        return session_id[:visible_chars] + "..."
    return session_id


def audit_log(
    event: str,
    *,
    session_id: str | None = None,
    platform_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    user_id: str | None = None,
    success: bool = True,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Log an audit event.

    Args:
        event: Event type from AuditEvent constants
        session_id: Optional session identifier
        platform_id: Optional platform identifier
        resource_type: Optional FHIR resource type
        resource_id: Optional resource ID
        user_id: Optional user identifier
        success: Whether the operation succeeded
        error: Optional error message if failed
        details: Optional additional details
    """
    log_data: dict[str, Any] = {
        "audit_event": event,
        "success": success,
    }

    if session_id:
        log_data["session_id"] = truncate_session_id(session_id)
    if platform_id:
        log_data["platform_id"] = platform_id
    if resource_type:
        log_data["resource_type"] = resource_type
    if resource_id:
        log_data["resource_id"] = resource_id
    if user_id:
        log_data["user_id"] = user_id
    if error:
        log_data["error"] = error
    if details:
        log_data["details"] = details

    if success:
        _audit_logger.info(event, **log_data)
    else:
        _audit_logger.warning(event, **log_data)
