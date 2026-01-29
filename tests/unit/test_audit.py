"""
Tests for audit logging.
"""

from unittest.mock import patch

from app.audit import AuditEvent, audit_log


class TestAuditEvents:
    """Tests for audit event constants."""

    def test_auth_events_defined(self):
        """Test authentication events are defined."""
        assert AuditEvent.AUTH_START == "auth.start"
        assert AuditEvent.AUTH_SUCCESS == "auth.success"
        assert AuditEvent.AUTH_FAILURE == "auth.failure"
        assert AuditEvent.AUTH_REVOKE == "auth.revoke"

    def test_token_events_defined(self):
        """Test token events are defined."""
        assert AuditEvent.TOKEN_REFRESH == "token.refresh"
        assert AuditEvent.TOKEN_EXPIRED == "token.expired"

    def test_resource_events_defined(self):
        """Test resource events are defined."""
        assert AuditEvent.RESOURCE_READ == "resource.read"
        assert AuditEvent.RESOURCE_SEARCH == "resource.search"
        assert AuditEvent.RESOURCE_CREATE == "resource.create"
        assert AuditEvent.RESOURCE_UPDATE == "resource.update"
        assert AuditEvent.RESOURCE_DELETE == "resource.delete"

    def test_coverage_events_defined(self):
        """Test coverage events are defined."""
        assert AuditEvent.COVERAGE_CHECK == "coverage.check"
        assert AuditEvent.QUESTIONNAIRE_FETCH == "coverage.questionnaire_fetch"
        assert AuditEvent.PLATFORM_RULES_FETCH == "coverage.platform_rules_fetch"

    def test_security_events_defined(self):
        """Test security events are defined."""
        assert AuditEvent.SECURITY_INVALID_STATE == "security.invalid_state"
        assert AuditEvent.SECURITY_INVALID_TOKEN == "security.invalid_token"
        assert AuditEvent.SECURITY_RATE_LIMIT == "security.rate_limit"


class TestAuditLog:
    """Tests for audit_log function."""

    @patch("app.audit._audit_logger")
    def test_audit_log_success(self, mock_logger):
        """Test logging successful event."""
        audit_log(
            AuditEvent.AUTH_SUCCESS,
            session_id="test-session-12345",
            platform_id="cigna",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == AuditEvent.AUTH_SUCCESS
        assert call_args[1]["platform_id"] == "cigna"
        assert call_args[1]["success"] is True

    @patch("app.audit._audit_logger")
    def test_audit_log_failure(self, mock_logger):
        """Test logging failed event."""
        audit_log(
            AuditEvent.AUTH_FAILURE,
            session_id="test-session",
            platform_id="cigna",
            success=False,
            error="Invalid credentials",
        )

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[1]["success"] is False
        assert call_args[1]["error"] == "Invalid credentials"

    @patch("app.audit._audit_logger")
    def test_audit_log_session_truncation(self, mock_logger):
        """Test session ID is truncated for privacy."""
        long_session = "abcdefghijklmnopqrstuvwxyz1234567890"

        audit_log(
            AuditEvent.RESOURCE_READ,
            session_id=long_session,
        )

        call_args = mock_logger.info.call_args
        session_logged = call_args[1]["session_id"]
        # Session should be truncated to 16 chars + "..."
        assert len(session_logged) == 19
        assert session_logged.endswith("...")

    @patch("app.audit._audit_logger")
    def test_audit_log_resource_info(self, mock_logger):
        """Test logging resource information."""
        audit_log(
            AuditEvent.RESOURCE_READ,
            platform_id="aetna",
            resource_type="Patient",
            resource_id="patient-123",
        )

        call_args = mock_logger.info.call_args
        assert call_args[1]["resource_type"] == "Patient"
        assert call_args[1]["resource_id"] == "patient-123"

    @patch("app.audit._audit_logger")
    def test_audit_log_with_details(self, mock_logger):
        """Test logging additional details."""
        audit_log(
            AuditEvent.COVERAGE_CHECK,
            platform_id="uhc",
            details={
                "patient_id": "pat-123",
                "procedure_code": "27447",
                "status": "required",
            },
        )

        call_args = mock_logger.info.call_args
        assert call_args[1]["details"]["procedure_code"] == "27447"
        assert call_args[1]["details"]["status"] == "required"

    @patch("app.audit._audit_logger")
    def test_audit_log_minimal(self, mock_logger):
        """Test logging with minimal parameters."""
        audit_log(AuditEvent.SESSION_CREATE)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == AuditEvent.SESSION_CREATE
        assert call_args[1]["success"] is True
