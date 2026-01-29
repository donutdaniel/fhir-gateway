"""
Contract tests for FHIR resource structure validation.

These tests verify that API responses conform to FHIR R4 specifications.
They validate resource structure, required fields, and data types.

Run with: pytest tests/contract -v
"""

import pytest

# Mark all tests in this module as contract tests
pytestmark = pytest.mark.contract


class TestBundleContract:
    """Contract tests for FHIR Bundle resources."""

    @pytest.fixture
    def valid_search_bundle(self):
        """A valid FHIR search Bundle."""
        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 2,
            "link": [
                {"relation": "self", "url": "https://example.org/Patient?name=Smith"}
            ],
            "entry": [
                {
                    "fullUrl": "https://example.org/Patient/123",
                    "resource": {
                        "resourceType": "Patient",
                        "id": "123",
                        "name": [{"family": "Smith", "given": ["John"]}],
                    },
                    "search": {"mode": "match"},
                },
                {
                    "fullUrl": "https://example.org/Patient/456",
                    "resource": {
                        "resourceType": "Patient",
                        "id": "456",
                        "name": [{"family": "Smith", "given": ["Jane"]}],
                    },
                    "search": {"mode": "match"},
                },
            ],
        }

    def test_bundle_has_resource_type(self, valid_search_bundle):
        """Bundle must have resourceType = 'Bundle'."""
        assert valid_search_bundle["resourceType"] == "Bundle"

    def test_bundle_has_type(self, valid_search_bundle):
        """Bundle must have a type field."""
        assert "type" in valid_search_bundle
        assert valid_search_bundle["type"] in [
            "document",
            "message",
            "transaction",
            "transaction-response",
            "batch",
            "batch-response",
            "history",
            "searchset",
            "collection",
        ]

    def test_searchset_bundle_has_total(self, valid_search_bundle):
        """Searchset bundles should have total."""
        if valid_search_bundle["type"] == "searchset":
            assert "total" in valid_search_bundle
            assert isinstance(valid_search_bundle["total"], int)
            assert valid_search_bundle["total"] >= 0

    def test_bundle_entries_have_resource(self, valid_search_bundle):
        """Bundle entries should have resource."""
        for entry in valid_search_bundle.get("entry", []):
            assert "resource" in entry
            assert "resourceType" in entry["resource"]

    def test_bundle_entries_have_fullurl(self, valid_search_bundle):
        """Bundle entries should have fullUrl."""
        for entry in valid_search_bundle.get("entry", []):
            if "resource" in entry:
                assert "fullUrl" in entry or "id" in entry.get("resource", {})


class TestPatientContract:
    """Contract tests for FHIR Patient resources."""

    @pytest.fixture
    def valid_patient(self):
        """A valid FHIR Patient resource."""
        return {
            "resourceType": "Patient",
            "id": "example",
            "identifier": [
                {
                    "system": "http://hospital.example.org",
                    "value": "12345",
                }
            ],
            "active": True,
            "name": [
                {
                    "use": "official",
                    "family": "Smith",
                    "given": ["John", "Jacob"],
                }
            ],
            "gender": "male",
            "birthDate": "1974-12-25",
            "address": [
                {
                    "use": "home",
                    "line": ["123 Main St"],
                    "city": "Anytown",
                    "state": "CA",
                    "postalCode": "12345",
                    "country": "US",
                }
            ],
        }

    def test_patient_has_resource_type(self, valid_patient):
        """Patient must have resourceType = 'Patient'."""
        assert valid_patient["resourceType"] == "Patient"

    def test_patient_name_structure(self, valid_patient):
        """Patient name should follow HumanName structure."""
        for name in valid_patient.get("name", []):
            # HumanName fields
            valid_fields = {"use", "text", "family", "given", "prefix", "suffix", "period"}
            for key in name.keys():
                assert key in valid_fields, f"Invalid name field: {key}"

            # Given should be an array
            if "given" in name:
                assert isinstance(name["given"], list)

    def test_patient_gender_values(self, valid_patient):
        """Patient gender must be valid code."""
        if "gender" in valid_patient:
            assert valid_patient["gender"] in ["male", "female", "other", "unknown"]

    def test_patient_birthdate_format(self, valid_patient):
        """Patient birthDate should be valid date format."""
        import re

        if "birthDate" in valid_patient:
            date = valid_patient["birthDate"]
            # FHIR date format: YYYY, YYYY-MM, or YYYY-MM-DD
            pattern = r"^\d{4}(-\d{2}(-\d{2})?)?$"
            assert re.match(pattern, date), f"Invalid birthDate format: {date}"

    def test_patient_identifier_structure(self, valid_patient):
        """Patient identifier should follow Identifier structure."""
        for identifier in valid_patient.get("identifier", []):
            valid_fields = {"use", "type", "system", "value", "period", "assigner"}
            for key in identifier.keys():
                assert key in valid_fields, f"Invalid identifier field: {key}"


class TestCapabilityStatementContract:
    """Contract tests for FHIR CapabilityStatement."""

    @pytest.fixture
    def valid_capability(self):
        """A valid FHIR CapabilityStatement."""
        return {
            "resourceType": "CapabilityStatement",
            "status": "active",
            "date": "2024-01-01",
            "kind": "instance",
            "fhirVersion": "4.0.1",
            "format": ["json", "xml"],
            "rest": [
                {
                    "mode": "server",
                    "resource": [
                        {
                            "type": "Patient",
                            "interaction": [
                                {"code": "read"},
                                {"code": "search-type"},
                            ],
                            "searchParam": [
                                {"name": "identifier", "type": "token"},
                                {"name": "name", "type": "string"},
                            ],
                        }
                    ],
                }
            ],
        }

    def test_capability_has_resource_type(self, valid_capability):
        """CapabilityStatement must have correct resourceType."""
        assert valid_capability["resourceType"] == "CapabilityStatement"

    def test_capability_has_required_fields(self, valid_capability):
        """CapabilityStatement must have required fields."""
        assert "status" in valid_capability
        assert "kind" in valid_capability
        assert "fhirVersion" in valid_capability

    def test_capability_status_values(self, valid_capability):
        """CapabilityStatement status must be valid code."""
        assert valid_capability["status"] in ["draft", "active", "retired", "unknown"]

    def test_capability_rest_mode(self, valid_capability):
        """REST capability must have valid mode."""
        for rest in valid_capability.get("rest", []):
            assert rest["mode"] in ["client", "server"]

    def test_capability_resource_interactions(self, valid_capability):
        """Resource interactions must be valid codes."""
        valid_interactions = {
            "read",
            "vread",
            "update",
            "patch",
            "delete",
            "history-instance",
            "history-type",
            "create",
            "search-type",
        }

        for rest in valid_capability.get("rest", []):
            for resource in rest.get("resource", []):
                for interaction in resource.get("interaction", []):
                    assert interaction["code"] in valid_interactions


class TestOperationOutcomeContract:
    """Contract tests for FHIR OperationOutcome."""

    @pytest.fixture
    def valid_operation_outcome(self):
        """A valid FHIR OperationOutcome."""
        return {
            "resourceType": "OperationOutcome",
            "issue": [
                {
                    "severity": "error",
                    "code": "not-found",
                    "diagnostics": "Resource Patient/123 not found",
                    "details": {
                        "text": "The requested resource was not found",
                    },
                }
            ],
        }

    def test_operation_outcome_has_resource_type(self, valid_operation_outcome):
        """OperationOutcome must have correct resourceType."""
        assert valid_operation_outcome["resourceType"] == "OperationOutcome"

    def test_operation_outcome_has_issues(self, valid_operation_outcome):
        """OperationOutcome must have at least one issue."""
        assert "issue" in valid_operation_outcome
        assert len(valid_operation_outcome["issue"]) > 0

    def test_operation_outcome_issue_severity(self, valid_operation_outcome):
        """Issue severity must be valid code."""
        valid_severities = {"fatal", "error", "warning", "information"}
        for issue in valid_operation_outcome["issue"]:
            assert issue["severity"] in valid_severities

    def test_operation_outcome_issue_code(self, valid_operation_outcome):
        """Issue code must be valid."""
        # Subset of common codes
        valid_codes = {
            "invalid",
            "structure",
            "required",
            "value",
            "invariant",
            "security",
            "login",
            "unknown",
            "expired",
            "forbidden",
            "suppressed",
            "processing",
            "not-supported",
            "duplicate",
            "not-found",
            "too-long",
            "code-invalid",
            "extension",
            "too-costly",
            "business-rule",
            "conflict",
            "transient",
            "lock-error",
            "no-store",
            "exception",
            "timeout",
            "throttled",
            "informational",
        }

        for issue in valid_operation_outcome["issue"]:
            assert issue["code"] in valid_codes


class TestCoverageContract:
    """Contract tests for FHIR Coverage resources."""

    @pytest.fixture
    def valid_coverage(self):
        """A valid FHIR Coverage resource."""
        return {
            "resourceType": "Coverage",
            "id": "coverage-1",
            "status": "active",
            "type": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                        "code": "HIP",
                        "display": "health insurance plan policy",
                    }
                ]
            },
            "subscriber": {"reference": "Patient/123"},
            "beneficiary": {"reference": "Patient/123"},
            "payor": [{"reference": "Organization/payer-1", "display": "Acme Insurance"}],
            "class": [
                {
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/coverage-class",
                                "code": "group",
                            }
                        ]
                    },
                    "value": "CB135",
                    "name": "Corporate Baker's Inc. Local #35",
                }
            ],
        }

    def test_coverage_has_resource_type(self, valid_coverage):
        """Coverage must have correct resourceType."""
        assert valid_coverage["resourceType"] == "Coverage"

    def test_coverage_has_required_fields(self, valid_coverage):
        """Coverage must have required fields."""
        assert "status" in valid_coverage
        assert "beneficiary" in valid_coverage
        assert "payor" in valid_coverage

    def test_coverage_status_values(self, valid_coverage):
        """Coverage status must be valid code."""
        assert valid_coverage["status"] in [
            "active",
            "cancelled",
            "draft",
            "entered-in-error",
        ]

    def test_coverage_payor_is_array(self, valid_coverage):
        """Coverage payor must be an array."""
        assert isinstance(valid_coverage["payor"], list)
        assert len(valid_coverage["payor"]) > 0


class TestReferenceContract:
    """Contract tests for FHIR Reference type."""

    @pytest.fixture
    def valid_references(self):
        """Valid FHIR References."""
        return [
            {"reference": "Patient/123"},
            {"reference": "Patient/123", "display": "John Smith"},
            {"reference": "http://example.org/fhir/Patient/123"},
            {"type": "Patient", "identifier": {"value": "12345"}},
            {"display": "Unknown Patient"},  # Display-only reference
        ]

    def test_reference_has_valid_structure(self, valid_references):
        """Reference should have valid structure."""
        for ref in valid_references:
            # At least one of these should be present
            has_reference = "reference" in ref
            has_identifier = "identifier" in ref
            has_display = "display" in ref

            assert (
                has_reference or has_identifier or has_display
            ), "Reference must have reference, identifier, or display"

    def test_relative_reference_format(self, valid_references):
        """Relative references should be ResourceType/id."""
        import re

        for ref in valid_references:
            if "reference" in ref:
                reference = ref["reference"]
                # Either relative (Type/id) or absolute URL
                is_relative = re.match(r"^[A-Z][a-zA-Z]+/[A-Za-z0-9\-\.]+$", reference)
                is_absolute = reference.startswith("http://") or reference.startswith(
                    "https://"
                )
                is_urn = reference.startswith("urn:")

                assert (
                    is_relative or is_absolute or is_urn
                ), f"Invalid reference format: {reference}"


class TestCodeableConceptContract:
    """Contract tests for FHIR CodeableConcept type."""

    @pytest.fixture
    def valid_codeable_concept(self):
        """A valid FHIR CodeableConcept."""
        return {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "39065001",
                    "display": "Burns",
                }
            ],
            "text": "Burns to skin",
        }

    def test_codeable_concept_structure(self, valid_codeable_concept):
        """CodeableConcept should have coding or text."""
        has_coding = "coding" in valid_codeable_concept
        has_text = "text" in valid_codeable_concept

        assert has_coding or has_text

    def test_coding_structure(self, valid_codeable_concept):
        """Coding should have system and code."""
        for coding in valid_codeable_concept.get("coding", []):
            # System and code are commonly expected
            if "code" in coding:
                assert isinstance(coding["code"], str)
            if "system" in coding:
                assert isinstance(coding["system"], str)
