"""
Tests for Pydantic models and types.
"""

from app.models.coverage import (
    AnswerOption,
    CoverageRequirement,
    CoverageRequirementStatus,
    PlatformReference,
    PlatformRulesResult,
    PolicyRule,
    QuestionnaireItem,
    QuestionnaireItemType,
    QuestionnairePackageResult,
    TransformedQuestionnaire,
)


class TestCoverageRequirementStatus:
    """Tests for CoverageRequirementStatus enum."""

    def test_all_statuses_defined(self):
        """Test all expected statuses exist."""
        assert CoverageRequirementStatus.REQUIRED == "required"
        assert CoverageRequirementStatus.NOT_REQUIRED == "not-required"
        assert CoverageRequirementStatus.CONDITIONAL == "conditional"
        assert CoverageRequirementStatus.UNKNOWN == "unknown"

    def test_status_is_string(self):
        """Test status values are strings."""
        assert isinstance(CoverageRequirementStatus.REQUIRED.value, str)


class TestPlatformReference:
    """Tests for PlatformReference model."""

    def test_create_minimal(self):
        """Test creating with minimal fields."""
        info = PlatformReference(id="cigna")
        assert info.id == "cigna"
        assert info.name is None
        assert info.endpoint is None

    def test_create_full(self):
        """Test creating with all fields."""
        info = PlatformReference(
            id="aetna",
            name="Aetna Health Insurance",
            endpoint="https://fhir.aetna.com",
        )
        assert info.id == "aetna"
        assert info.name == "Aetna Health Insurance"
        assert info.endpoint == "https://fhir.aetna.com"


class TestCoverageRequirement:
    """Tests for CoverageRequirement model."""

    def test_create_required(self):
        """Test required coverage requirement."""
        req = CoverageRequirement(
            status=CoverageRequirementStatus.REQUIRED,
            procedure_code="27447",
            code_system="http://www.ama-assn.org/go/cpt",
            coverage_id="cov-123",
            patient_id="pat-456",
            documentation_required=True,
            questionnaire_url="http://example.org/Questionnaire/pa-form",
        )

        assert req.status == CoverageRequirementStatus.REQUIRED
        assert req.documentation_required is True
        assert req.questionnaire_url is not None

    def test_create_not_required(self):
        """Test not-required coverage requirement."""
        req = CoverageRequirement(
            status=CoverageRequirementStatus.NOT_REQUIRED,
            procedure_code="99213",
            code_system="http://www.ama-assn.org/go/cpt",
            coverage_id="cov-123",
            patient_id="pat-456",
            reason="Routine office visit - no auth needed",
        )

        assert req.status == CoverageRequirementStatus.NOT_REQUIRED
        assert req.documentation_required is False
        assert "no auth" in req.reason.lower()

    def test_create_with_platform(self):
        """Test requirement with platform info."""
        req = CoverageRequirement(
            status=CoverageRequirementStatus.CONDITIONAL,
            platform=PlatformReference(id="uhc", name="UnitedHealthcare"),
            procedure_code="27447",
            code_system="http://www.ama-assn.org/go/cpt",
            coverage_id="cov-123",
            patient_id="pat-456",
            info_needed=["Clinical notes", "Imaging results"],
        )

        assert req.platform.id == "uhc"
        assert len(req.info_needed) == 2


class TestQuestionnaireItemType:
    """Tests for QuestionnaireItemType enum."""

    def test_all_types_defined(self):
        """Test all FHIR questionnaire types are defined."""
        types = [
            "group",
            "display",
            "boolean",
            "decimal",
            "integer",
            "date",
            "dateTime",
            "time",
            "string",
            "text",
            "url",
            "choice",
            "open-choice",
            "attachment",
            "reference",
            "quantity",
        ]

        for t in types:
            assert QuestionnaireItemType(t) is not None


class TestAnswerOption:
    """Tests for AnswerOption model."""

    def test_create_simple(self):
        """Test creating simple option."""
        opt = AnswerOption(value="yes")
        assert opt.value == "yes"
        assert opt.display is None

    def test_create_with_display(self):
        """Test creating with display text."""
        opt = AnswerOption(
            value="M79.3",
            display="Limb pain",
            system="http://hl7.org/fhir/sid/icd-10",
        )
        assert opt.value == "M79.3"
        assert opt.display == "Limb pain"
        assert opt.system is not None


class TestQuestionnaireItem:
    """Tests for QuestionnaireItem model."""

    def test_create_simple(self):
        """Test creating simple item."""
        item = QuestionnaireItem(
            link_id="1",
            text="Patient name",
            type=QuestionnaireItemType.STRING,
            required=True,
        )

        assert item.link_id == "1"
        assert item.text == "Patient name"
        assert item.type == QuestionnaireItemType.STRING
        assert item.required is True

    def test_create_with_options(self):
        """Test creating item with options."""
        item = QuestionnaireItem(
            link_id="2",
            text="Gender",
            type=QuestionnaireItemType.CHOICE,
            required=True,
            answer_options=[
                AnswerOption(value="male", display="Male"),
                AnswerOption(value="female", display="Female"),
                AnswerOption(value="other", display="Other"),
            ],
        )

        assert len(item.answer_options) == 3
        assert item.answer_options[0].value == "male"

    def test_create_with_nested(self):
        """Test creating item with nested items."""
        item = QuestionnaireItem(
            link_id="group1",
            text="Patient Info",
            type=QuestionnaireItemType.GROUP,
            items=[
                QuestionnaireItem(
                    link_id="1.1",
                    text="Name",
                    type=QuestionnaireItemType.STRING,
                ),
                QuestionnaireItem(
                    link_id="1.2",
                    text="DOB",
                    type=QuestionnaireItemType.DATE,
                ),
            ],
        )

        assert len(item.items) == 2


class TestTransformedQuestionnaire:
    """Tests for TransformedQuestionnaire model."""

    def test_create(self):
        """Test creating transformed questionnaire."""
        q = TransformedQuestionnaire(
            id="test-q",
            url="http://example.org/Questionnaire/test",
            title="Test Questionnaire",
            status="active",
            items=[],
            markdown="# Test\n\nNo items.",
            item_count=0,
            required_count=0,
        )

        assert q.id == "test-q"
        assert q.title == "Test Questionnaire"
        assert q.status == "active"


class TestQuestionnairePackageResult:
    """Tests for QuestionnairePackageResult model."""

    def test_create_empty(self):
        """Test creating empty result."""
        result = QuestionnairePackageResult()

        assert len(result.questionnaires) == 0
        assert result.value_sets is None
        assert result.libraries is None
        assert result.raw_bundle is None

    def test_create_with_questionnaires(self):
        """Test creating with questionnaires."""
        result = QuestionnairePackageResult(
            questionnaires=[
                TransformedQuestionnaire(
                    id="q1",
                    status="active",
                    items=[],
                    markdown="# Q1",
                    item_count=0,
                    required_count=0,
                )
            ],
        )

        assert len(result.questionnaires) == 1


class TestPolicyRule:
    """Tests for PolicyRule model."""

    def test_create(self):
        """Test creating policy rule."""
        rule = PolicyRule(
            id="rule-123",
            title="Knee Replacement Policy",
            description="Requirements for total knee replacement",
            applies_to_codes=["27447", "27446"],
            criteria="BMI > 30, failed conservative treatment",
            documentation_requirements=[
                "Clinical notes",
                "X-ray results",
                "PT records",
            ],
            source_url="https://example.org/policies/knee",
        )

        assert rule.id == "rule-123"
        assert len(rule.applies_to_codes) == 2
        assert len(rule.documentation_requirements) == 3


class TestPlatformRulesResult:
    """Tests for PlatformRulesResult model."""

    def test_create(self):
        """Test creating platform rules result."""
        result = PlatformRulesResult(
            platform_id="cigna",
            procedure_code="27447",
            code_system="http://www.ama-assn.org/go/cpt",
            rules=[
                PolicyRule(
                    id="rule-1",
                    title="TKR Policy",
                    applies_to_codes=["27447"],
                )
            ],
            markdown_summary="# Policy Rules\n\n- TKR Policy",
        )

        assert result.platform_id == "cigna"
        assert len(result.rules) == 1
