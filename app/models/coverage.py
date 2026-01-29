"""
Data types for coverage requirements and questionnaires.

This module contains pydantic models and enums for:
- Coverage Requirement Discovery (CRD)
- Documentation Templates and Rules (DTR)
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CoverageRequirementStatus(str, Enum):
    """Status of coverage requirement/prior authorization."""

    REQUIRED = "required"
    NOT_REQUIRED = "not-required"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class PlatformInfo(BaseModel):
    """Information about a platform (payer or EHR)."""

    id: str = Field(description="Platform identifier")
    name: str | None = Field(default=None, description="Platform display name")
    endpoint: str | None = Field(default=None, description="Platform's endpoint URL")


class CoverageRequirement(BaseModel):
    """Result of coverage requirement check (CRD simulation)."""

    status: CoverageRequirementStatus = Field(description="Whether prior authorization is required")
    platform: PlatformInfo | None = Field(default=None, description="Platform information if available")
    procedure_code: str = Field(description="The procedure code that was checked")
    code_system: str = Field(description="Code system URL (e.g., CPT, HCPCS)")
    questionnaire_url: str | None = Field(
        default=None,
        description="URL to DTR questionnaire if documentation is needed",
    )
    documentation_required: bool = Field(
        default=False, description="Whether additional documentation is required"
    )
    info_needed: list[str] | None = Field(
        default=None, description="List of information items needed for authorization"
    )
    reason: str | None = Field(
        default=None, description="Human-readable reason for the requirement status"
    )
    coverage_id: str = Field(description="Coverage resource ID that was checked")
    patient_id: str = Field(description="Patient resource ID")


class QuestionnaireItemType(str, Enum):
    """FHIR Questionnaire item types."""

    GROUP = "group"
    DISPLAY = "display"
    BOOLEAN = "boolean"
    DECIMAL = "decimal"
    INTEGER = "integer"
    DATE = "date"
    DATETIME = "dateTime"
    TIME = "time"
    STRING = "string"
    TEXT = "text"
    URL = "url"
    CHOICE = "choice"
    OPEN_CHOICE = "open-choice"
    ATTACHMENT = "attachment"
    REFERENCE = "reference"
    QUANTITY = "quantity"


class AnswerOption(BaseModel):
    """Answer option for choice-type questionnaire items."""

    value: str = Field(description="The answer value")
    display: str | None = Field(default=None, description="Display text for option")
    system: str | None = Field(default=None, description="Code system for coded options")


class QuestionnaireItem(BaseModel):
    """Simplified questionnaire item for LLM consumption."""

    link_id: str = Field(description="Unique identifier within the questionnaire")
    text: str | None = Field(default=None, description="Question text")
    type: QuestionnaireItemType = Field(description="Item type")
    required: bool = Field(default=False, description="Whether answer is required")
    repeats: bool = Field(default=False, description="Whether item can repeat")
    read_only: bool = Field(default=False, description="Whether item is read-only")
    max_length: int | None = Field(default=None, description="Max length for string answers")
    answer_options: list[AnswerOption] | None = Field(
        default=None, description="Available options for choice items"
    )
    initial_value: str | None = Field(default=None, description="Pre-populated initial value")
    items: list["QuestionnaireItem"] | None = Field(
        default=None, description="Nested items (for groups)"
    )
    enable_when: str | None = Field(
        default=None, description="Human-readable condition for display"
    )


# Enable forward references for nested items
QuestionnaireItem.model_rebuild()


class TransformedQuestionnaire(BaseModel):
    """Questionnaire transformed for LLM consumption."""

    id: str = Field(description="Questionnaire resource ID")
    url: str | None = Field(default=None, description="Canonical URL of the questionnaire")
    title: str | None = Field(default=None, description="Human-readable title")
    description: str | None = Field(default=None, description="Natural language description")
    status: str = Field(description="Publication status (draft, active, retired)")
    items: list[QuestionnaireItem] = Field(default_factory=list, description="Questionnaire items")
    markdown: str = Field(
        description="Markdown representation for LLM context",
    )
    item_count: int = Field(description="Total number of questions")
    required_count: int = Field(description="Number of required questions")


class QuestionnairePackageResult(BaseModel):
    """Result of $questionnaire-package operation."""

    questionnaires: list[TransformedQuestionnaire] = Field(
        default_factory=list, description="Transformed questionnaires"
    )
    value_sets: dict[str, Any] | None = Field(
        default=None, description="Referenced ValueSets for coded answers"
    )
    libraries: list[str] | None = Field(default=None, description="CQL library references")
    raw_bundle: dict[str, Any] | None = Field(
        default=None, description="Raw FHIR Bundle (when raw_format=true)"
    )


class PolicyRule(BaseModel):
    """Medical policy rule from platform."""

    id: str = Field(description="Rule identifier")
    title: str | None = Field(default=None, description="Rule title")
    description: str | None = Field(default=None, description="Rule description or summary")
    applies_to_codes: list[str] = Field(
        default_factory=list, description="Procedure codes this rule applies to"
    )
    criteria: str | None = Field(default=None, description="Human-readable criteria summary")
    documentation_requirements: list[str] | None = Field(
        default=None, description="List of required documentation"
    )
    effective_date: str | None = Field(default=None, description="When policy became effective")
    source_url: str | None = Field(default=None, description="URL to full policy document")


class PlatformRulesResult(BaseModel):
    """Result of platform rules lookup."""

    platform_id: str = Field(description="Platform identifier")
    procedure_code: str = Field(description="Procedure code queried")
    code_system: str = Field(description="Code system URL")
    rules: list[PolicyRule] = Field(default_factory=list, description="Matching policy rules")
    markdown_summary: str = Field(description="Markdown summary of rules for LLM context")
    last_updated: str | None = Field(default=None, description="When rules were last updated")
