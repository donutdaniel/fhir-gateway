"""
Tests for FHIR resource transformers.
"""

import pytest

from app.models.coverage import (
    QuestionnaireItemType,
)
from app.transformers.questionnaire import (
    QuestionnaireTransformer,
    transform_questionnaire_bundle,
)


class TestQuestionnaireTransformer:
    """Tests for QuestionnaireTransformer."""

    @pytest.fixture
    def transformer(self):
        """Create a transformer instance."""
        return QuestionnaireTransformer()

    @pytest.fixture
    def simple_questionnaire(self):
        """Simple questionnaire for testing."""
        return {
            "resourceType": "Questionnaire",
            "id": "test-q",
            "url": "http://example.org/Questionnaire/test",
            "title": "Test Questionnaire",
            "description": "A test questionnaire",
            "status": "active",
            "item": [
                {
                    "linkId": "1",
                    "text": "Patient name",
                    "type": "string",
                    "required": True,
                },
                {
                    "linkId": "2",
                    "text": "Date of birth",
                    "type": "date",
                    "required": True,
                },
                {
                    "linkId": "3",
                    "text": "Comments",
                    "type": "text",
                    "required": False,
                },
            ],
        }

    def test_transform_basic(self, transformer, simple_questionnaire):
        """Test basic questionnaire transformation."""
        result = transformer.transform(simple_questionnaire)

        assert result.id == "test-q"
        assert result.url == "http://example.org/Questionnaire/test"
        assert result.title == "Test Questionnaire"
        assert result.status == "active"
        assert result.item_count == 3
        assert result.required_count == 2
        assert len(result.items) == 3

    def test_transform_item_types(self, transformer):
        """Test all item types are correctly mapped."""
        questionnaire = {
            "resourceType": "Questionnaire",
            "id": "types-test",
            "status": "active",
            "item": [
                {"linkId": "1", "type": "string", "text": "String"},
                {"linkId": "2", "type": "boolean", "text": "Boolean"},
                {"linkId": "3", "type": "integer", "text": "Integer"},
                {"linkId": "4", "type": "date", "text": "Date"},
                {"linkId": "5", "type": "choice", "text": "Choice"},
                {"linkId": "6", "type": "group", "text": "Group"},
                {"linkId": "7", "type": "display", "text": "Display"},
            ],
        }

        result = transformer.transform(questionnaire)

        assert result.items[0].type == QuestionnaireItemType.STRING
        assert result.items[1].type == QuestionnaireItemType.BOOLEAN
        assert result.items[2].type == QuestionnaireItemType.INTEGER
        assert result.items[3].type == QuestionnaireItemType.DATE
        assert result.items[4].type == QuestionnaireItemType.CHOICE
        assert result.items[5].type == QuestionnaireItemType.GROUP
        assert result.items[6].type == QuestionnaireItemType.DISPLAY

    def test_transform_answer_options(self, transformer):
        """Test answer options are extracted."""
        questionnaire = {
            "resourceType": "Questionnaire",
            "id": "options-test",
            "status": "active",
            "item": [
                {
                    "linkId": "1",
                    "text": "Choice question",
                    "type": "choice",
                    "answerOption": [
                        {
                            "valueCoding": {
                                "code": "A",
                                "display": "Option A",
                                "system": "http://example.org",
                            }
                        },
                        {
                            "valueCoding": {
                                "code": "B",
                                "display": "Option B",
                                "system": "http://example.org",
                            }
                        },
                        {"valueString": "Other"},
                    ],
                }
            ],
        }

        result = transformer.transform(questionnaire)
        options = result.items[0].answer_options

        assert len(options) == 3
        assert options[0].value == "A"
        assert options[0].display == "Option A"
        assert options[1].value == "B"
        assert options[2].value == "Other"

    def test_transform_nested_items(self, transformer):
        """Test nested items are transformed."""
        questionnaire = {
            "resourceType": "Questionnaire",
            "id": "nested-test",
            "status": "active",
            "item": [
                {
                    "linkId": "group1",
                    "text": "Patient Info",
                    "type": "group",
                    "item": [
                        {
                            "linkId": "group1.1",
                            "text": "Name",
                            "type": "string",
                            "required": True,
                        },
                        {
                            "linkId": "group1.2",
                            "text": "DOB",
                            "type": "date",
                            "required": True,
                        },
                    ],
                }
            ],
        }

        result = transformer.transform(questionnaire)

        assert len(result.items) == 1
        assert result.items[0].type == QuestionnaireItemType.GROUP
        assert len(result.items[0].items) == 2
        assert result.items[0].items[0].text == "Name"
        # Group + 2 nested items = 3 total, but group doesn't count
        assert result.required_count == 2

    def test_transform_enable_when(self, transformer):
        """Test enableWhen conditions are formatted."""
        questionnaire = {
            "resourceType": "Questionnaire",
            "id": "enable-test",
            "status": "active",
            "item": [
                {"linkId": "1", "text": "Is pregnant?", "type": "boolean"},
                {
                    "linkId": "2",
                    "text": "Due date",
                    "type": "date",
                    "enableWhen": [
                        {
                            "question": "1",
                            "operator": "=",
                            "answerBoolean": True,
                        }
                    ],
                },
            ],
        }

        result = transformer.transform(questionnaire)

        assert result.items[1].enable_when is not None
        assert "equals" in result.items[1].enable_when
        assert "True" in result.items[1].enable_when

    def test_generate_markdown(self, transformer, simple_questionnaire):
        """Test markdown generation."""
        result = transformer.transform(simple_questionnaire)

        assert "# Test Questionnaire" in result.markdown
        assert "**Required fields:** 2" in result.markdown
        assert "Patient name" in result.markdown
        assert "(required)" in result.markdown

    def test_transform_initial_values(self, transformer):
        """Test initial values are extracted."""
        questionnaire = {
            "resourceType": "Questionnaire",
            "id": "initial-test",
            "status": "active",
            "item": [
                {
                    "linkId": "1",
                    "text": "Default text",
                    "type": "string",
                    "initial": [{"valueString": "Hello World"}],
                },
            ],
        }

        result = transformer.transform(questionnaire)

        assert result.items[0].initial_value == "Hello World"


class TestTransformQuestionnaireBundle:
    """Tests for transform_questionnaire_bundle function."""

    def test_transform_empty_bundle(self):
        """Test transforming an empty bundle."""
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [],
        }

        result = transform_questionnaire_bundle(bundle)

        assert len(result.questionnaires) == 0
        assert result.value_sets is None

    def test_transform_with_questionnaire(self):
        """Test transforming a bundle with questionnaires."""
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Questionnaire",
                        "id": "q1",
                        "status": "active",
                        "title": "Test Q",
                        "item": [{"linkId": "1", "text": "Q1", "type": "string"}],
                    }
                }
            ],
        }

        result = transform_questionnaire_bundle(bundle)

        assert len(result.questionnaires) == 1
        assert result.questionnaires[0].id == "q1"
        assert result.questionnaires[0].title == "Test Q"

    def test_transform_with_valuesets(self):
        """Test ValueSets are extracted."""
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "ValueSet",
                        "url": "http://example.org/ValueSet/test",
                        "expansion": {
                            "contains": [
                                {"code": "A", "display": "Option A"},
                            ]
                        },
                    }
                }
            ],
        }

        result = transform_questionnaire_bundle(bundle)

        assert result.value_sets is not None
        assert "http://example.org/ValueSet/test" in result.value_sets

    def test_raw_format(self):
        """Test raw format returns bundle as-is."""
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [],
        }

        result = transform_questionnaire_bundle(bundle, raw_format=True)

        assert result.raw_bundle == bundle
        assert len(result.questionnaires) == 0

    def test_operation_outcome(self):
        """Test OperationOutcome is returned as raw."""
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "code": "not-found"}],
        }

        result = transform_questionnaire_bundle(outcome)

        assert result.raw_bundle == outcome
