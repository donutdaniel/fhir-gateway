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
    SECURITY_SCOPE_VIOLATION = "security.scope_violation"

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


def sanitize_resource_for_audit(resource: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize a FHIR resource for audit logging.

    Removes large/sensitive fields that shouldn't be logged:
    - Binary data (base64 encoded)
    - Large text fields
    - Attachments

    Args:
        resource: FHIR resource dict

    Returns:
        Sanitized copy of the resource
    """
    if not resource:
        return {}

    # Fields to exclude from audit logs
    sensitive_fields = {
        "data",  # Binary.data
        "content",  # DocumentReference.content, Attachment.data
        "attachment",  # Various resources
        "photo",  # Patient.photo, Practitioner.photo
        "text",  # Resource.text (narrative, can be large)
    }

    # Max length for string values
    max_string_length = 500

    def sanitize_value(value: Any, key: str = "") -> Any:
        if key.lower() in sensitive_fields:
            return "[REDACTED]"
        if isinstance(value, str):
            if len(value) > max_string_length:
                return (
                    value[:max_string_length]
                    + f"...[truncated {len(value) - max_string_length} chars]"
                )
            return value
        if isinstance(value, dict):
            return {k: sanitize_value(v, k) for k, v in value.items()}
        if isinstance(value, list):
            # Limit list length for audit
            if len(value) > 10:
                return [sanitize_value(item) for item in value[:10]] + [
                    f"...[{len(value) - 10} more items]"
                ]
            return [sanitize_value(item) for item in value]
        return value

    return sanitize_value(resource)


def compute_change_summary(
    previous: dict[str, Any] | None,
    current: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Compute a summary of changes between two resource versions.

    Args:
        previous: Previous resource state (None for create)
        current: Current resource state (None for delete)

    Returns:
        Dictionary with changed_fields list and operation type
    """
    if previous is None and current is not None:
        return {
            "operation": "create",
            "fields_set": list(current.keys()),
        }

    if current is None and previous is not None:
        return {
            "operation": "delete",
            "fields_removed": list(previous.keys()),
        }

    if previous is None or current is None:
        return {"operation": "unknown"}

    # Compare fields for update
    changed_fields = []
    added_fields = []
    removed_fields = []

    all_keys = set(previous.keys()) | set(current.keys())

    for key in all_keys:
        prev_val = previous.get(key)
        curr_val = current.get(key)

        if key not in previous:
            added_fields.append(key)
        elif key not in current:
            removed_fields.append(key)
        elif prev_val != curr_val:
            changed_fields.append(key)

    return {
        "operation": "update",
        "changed_fields": changed_fields,
        "added_fields": added_fields,
        "removed_fields": removed_fields,
    }


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
    previous_state: dict[str, Any] | None = None,
    new_state: dict[str, Any] | None = None,
    change_summary: dict[str, Any] | None = None,
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
        previous_state: Previous resource state (for update/delete tracking)
        new_state: New resource state (for create/update tracking)
        change_summary: Summary of changes between states
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
    if previous_state:
        log_data["previous_state"] = sanitize_resource_for_audit(previous_state)
    if new_state:
        log_data["new_state"] = sanitize_resource_for_audit(new_state)
    if change_summary:
        log_data["change_summary"] = change_summary

    if success:
        _audit_logger.info(event, **log_data)
    else:
        _audit_logger.warning(event, **log_data)
