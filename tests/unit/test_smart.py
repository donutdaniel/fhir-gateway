"""
Tests for the SMART on FHIR module.
"""

from app.auth.smart import (
    SMART_CLINICIAN_SCOPES,
    SMART_PATIENT_READ_SCOPES,
    SMART_SYSTEM_SCOPES,
    SmartLaunchContext,
    SmartLaunchType,
    SmartScope,
    SmartScopeCategory,
    build_smart_scopes,
    parse_smart_scopes,
)


class TestSmartLaunchType:
    """Tests for SmartLaunchType enum."""

    def test_ehr_launch(self):
        """Should have EHR launch type."""
        assert SmartLaunchType.EHR_LAUNCH.value == "ehr"

    def test_standalone(self):
        """Should have standalone launch type."""
        assert SmartLaunchType.STANDALONE.value == "standalone"


class TestSmartScopeCategory:
    """Tests for SmartScopeCategory enum."""

    def test_all_categories(self):
        """Should have all expected categories."""
        assert SmartScopeCategory.PATIENT.value == "patient"
        assert SmartScopeCategory.USER.value == "user"
        assert SmartScopeCategory.SYSTEM.value == "system"
        assert SmartScopeCategory.LAUNCH.value == "launch"
        assert SmartScopeCategory.OPENID.value == "openid"
        assert SmartScopeCategory.FHIRUSER.value == "fhirUser"
        assert SmartScopeCategory.OFFLINE.value == "offline_access"


class TestSmartScope:
    """Tests for SmartScope dataclass."""

    def test_basic_scope(self):
        """Should create basic scope."""
        scope = SmartScope(raw="patient/Patient.read")
        assert scope.raw == "patient/Patient.read"

    def test_can_read_with_read_permission(self):
        """Should report can_read with read permission."""
        scope = SmartScope(raw="test", permissions=["read"])
        assert scope.can_read is True
        assert scope.can_write is False

    def test_can_write_with_write_permission(self):
        """Should report can_write with write permission."""
        scope = SmartScope(raw="test", permissions=["write"])
        assert scope.can_read is False
        assert scope.can_write is True

    def test_can_read_write_with_wildcard(self):
        """Should report both with wildcard permission."""
        scope = SmartScope(raw="test", permissions=["*"])
        assert scope.can_read is True
        assert scope.can_write is True

    def test_str_returns_raw(self):
        """Should return raw string."""
        scope = SmartScope(raw="openid")
        assert str(scope) == "openid"


class TestParseSmartScopes:
    """Tests for parse_smart_scopes function."""

    def test_parses_openid(self):
        """Should parse openid scope."""
        scopes = parse_smart_scopes("openid")
        assert len(scopes) == 1
        assert scopes[0].category == SmartScopeCategory.OPENID

    def test_parses_fhiruser(self):
        """Should parse fhirUser scope."""
        scopes = parse_smart_scopes("fhirUser")
        assert len(scopes) == 1
        assert scopes[0].category == SmartScopeCategory.FHIRUSER

    def test_parses_offline_access(self):
        """Should parse offline_access scope."""
        scopes = parse_smart_scopes("offline_access")
        assert len(scopes) == 1
        assert scopes[0].category == SmartScopeCategory.OFFLINE

    def test_parses_launch(self):
        """Should parse launch scope."""
        scopes = parse_smart_scopes("launch")
        assert len(scopes) == 1
        assert scopes[0].category == SmartScopeCategory.LAUNCH

    def test_parses_launch_with_context(self):
        """Should parse launch scope with context."""
        scopes = parse_smart_scopes("launch/patient")
        assert len(scopes) == 1
        assert scopes[0].category == SmartScopeCategory.LAUNCH
        assert scopes[0].resource_type == "patient"

    def test_parses_patient_scope_v1_read(self):
        """Should parse SMART v1 patient read scope."""
        scopes = parse_smart_scopes("patient/Observation.read")
        assert len(scopes) == 1
        assert scopes[0].category == SmartScopeCategory.PATIENT
        assert scopes[0].resource_type == "Observation"
        assert scopes[0].permissions == ["read"]

    def test_parses_user_scope_wildcard(self):
        """Should parse user scope with wildcard."""
        scopes = parse_smart_scopes("user/Patient.*")
        assert len(scopes) == 1
        assert scopes[0].category == SmartScopeCategory.USER
        assert scopes[0].resource_type == "Patient"
        assert "read" in scopes[0].permissions
        assert "write" in scopes[0].permissions

    def test_parses_system_scope(self):
        """Should parse system scope."""
        scopes = parse_smart_scopes("system/Coverage.read")
        assert len(scopes) == 1
        assert scopes[0].category == SmartScopeCategory.SYSTEM
        assert scopes[0].resource_type == "Coverage"

    def test_parses_v2_scopes(self):
        """Should parse SMART v2 scope format."""
        scopes = parse_smart_scopes("patient/Observation.rs")
        assert len(scopes) == 1
        assert "read" in scopes[0].permissions
        assert "search" in scopes[0].permissions

    def test_parses_v2_cruds(self):
        """Should parse SMART v2 cruds permissions."""
        scopes = parse_smart_scopes("user/Patient.cruds")
        assert len(scopes) == 1
        assert "create" in scopes[0].permissions
        assert "read" in scopes[0].permissions
        assert "update" in scopes[0].permissions
        assert "delete" in scopes[0].permissions
        assert "search" in scopes[0].permissions

    def test_parses_multiple_scopes(self):
        """Should parse multiple scopes."""
        scopes = parse_smart_scopes("openid fhirUser patient/Patient.read")
        assert len(scopes) == 3
        assert scopes[0].category == SmartScopeCategory.OPENID
        assert scopes[1].category == SmartScopeCategory.FHIRUSER
        assert scopes[2].category == SmartScopeCategory.PATIENT

    def test_handles_malformed_scope(self):
        """Should handle malformed scope gracefully."""
        scopes = parse_smart_scopes("invalid_scope")
        assert len(scopes) == 1
        assert scopes[0].raw == "invalid_scope"


class TestBuildSmartScopes:
    """Tests for build_smart_scopes function."""

    def test_builds_basic_scopes(self):
        """Should build basic scope string."""
        result = build_smart_scopes(["Patient", "Observation"])
        assert "openid" in result
        assert "fhirUser" in result
        assert "launch" in result
        assert "patient/Patient.*" in result
        assert "patient/Observation.*" in result

    def test_respects_category(self):
        """Should respect category parameter."""
        result = build_smart_scopes(["Patient"], category=SmartScopeCategory.USER)
        assert "user/Patient.*" in result

    def test_respects_permissions(self):
        """Should respect permissions parameter."""
        result = build_smart_scopes(["Patient"], permissions=["read"])
        assert "patient/Patient.read" in result

    def test_excludes_launch(self):
        """Should exclude launch when specified."""
        result = build_smart_scopes(["Patient"], include_launch=False)
        assert "launch" not in result

    def test_excludes_openid(self):
        """Should exclude openid when specified."""
        result = build_smart_scopes(["Patient"], include_openid=False)
        assert "openid" not in result
        assert "fhirUser" not in result

    def test_includes_offline(self):
        """Should include offline_access when specified."""
        result = build_smart_scopes(["Patient"], include_offline=True)
        assert "offline_access" in result


class TestSmartLaunchContext:
    """Tests for SmartLaunchContext dataclass."""

    def test_from_token_response(self):
        """Should create context from token response."""
        response = {
            "access_token": "token123",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid patient/Patient.read",
            "patient": "patient-123",
            "encounter": "encounter-456",
            "fhirUser": "Practitioner/789",
        }

        context = SmartLaunchContext.from_token_response(response)

        assert context.access_token == "token123"
        assert context.patient == "patient-123"
        assert context.encounter == "encounter-456"
        assert context.user == "Practitioner/789"

    def test_from_token_response_with_user(self):
        """Should handle 'user' field fallback."""
        response = {
            "access_token": "token",
            "user": "User/123",
        }

        context = SmartLaunchContext.from_token_response(response)
        assert context.user == "User/123"

    def test_has_patient_context(self):
        """Should report patient context availability."""
        context = SmartLaunchContext(patient="123")
        assert context.has_patient_context is True

        context_no_patient = SmartLaunchContext()
        assert context_no_patient.has_patient_context is False

    def test_has_encounter_context(self):
        """Should report encounter context availability."""
        context = SmartLaunchContext(encounter="456")
        assert context.has_encounter_context is True

        context_no_encounter = SmartLaunchContext()
        assert context_no_encounter.has_encounter_context is False

    def test_to_dict(self):
        """Should convert to dictionary."""
        context = SmartLaunchContext(
            patient="123",
            access_token="token",
            scope="openid",
        )

        result = context.to_dict()

        assert result["patient"] == "123"
        assert result["access_token"] == "token"
        assert "encounter" not in result  # None values filtered

    def test_parsed_scopes(self):
        """Should parse scopes property."""
        context = SmartLaunchContext(scope="openid patient/Patient.read")

        scopes = context.parsed_scopes

        assert len(scopes) == 2
        assert scopes[0].category == SmartScopeCategory.OPENID

    def test_parsed_scopes_empty(self):
        """Should return empty list if no scope."""
        context = SmartLaunchContext()
        assert context.parsed_scopes == []


class TestPredefinedScopeSets:
    """Tests for predefined scope sets."""

    def test_patient_read_scopes(self):
        """Should have patient read scopes."""
        assert "openid" in SMART_PATIENT_READ_SCOPES
        assert "fhirUser" in SMART_PATIENT_READ_SCOPES
        assert "patient/Patient.read" in SMART_PATIENT_READ_SCOPES
        assert "patient/Observation.read" in SMART_PATIENT_READ_SCOPES

    def test_clinician_scopes(self):
        """Should have clinician scopes."""
        assert "openid" in SMART_CLINICIAN_SCOPES
        assert "launch" in SMART_CLINICIAN_SCOPES
        assert "user/Patient.read" in SMART_CLINICIAN_SCOPES
        assert "user/Observation.*" in SMART_CLINICIAN_SCOPES

    def test_system_scopes(self):
        """Should have system scopes."""
        assert "system/Patient.read" in SMART_SYSTEM_SCOPES
        assert "system/Coverage.read" in SMART_SYSTEM_SCOPES
        assert "system/Claim.*" in SMART_SYSTEM_SCOPES
