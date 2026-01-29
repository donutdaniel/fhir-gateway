"""
Default configuration values shared across all payers.

This module provides default code systems, document types, and search
parameters used by payer adapters when no payer-specific config exists.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CodeSystems:
    """Standard healthcare code system URLs."""

    CPT: str = "http://www.ama-assn.org/go/cpt"
    HCPCS: str = "https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"
    ICD10_CM: str = "http://hl7.org/fhir/sid/icd-10-cm"
    ICD10_PCS: str = "http://www.cms.gov/Medicare/Coding/ICD10"
    SNOMED: str = "http://snomed.info/sct"
    LOINC: str = "http://loinc.org"
    RXNORM: str = "http://www.nlm.nih.gov/research/umls/rxnorm"
    NDC: str = "http://hl7.org/fhir/sid/ndc"


@dataclass(frozen=True)
class DocumentTypes:
    """
    LOINC codes for clinical document types.

    These codes are used in payer rule searches and document references.
    Format: "http://loinc.org|{code}"

    References:
    - https://loinc.org/document-ontology/
    - https://build.fhir.org/ig/HL7/davinci-pas/ValueSet-pas-loinc-attachment-codes.html
    """

    CONSULTATION_NOTE: str = "http://loinc.org|11488-4"
    HISTORY_PHYSICAL: str = "http://loinc.org|34117-2"
    EVALUATION_PLAN: str = "http://loinc.org|51847-2"  # Evaluation + Plan note
    DISCHARGE_SUMMARY: str = "http://loinc.org|18842-5"
    PROGRESS_NOTE: str = "http://loinc.org|11506-3"
    REFERRAL_NOTE: str = "http://loinc.org|57133-1"
    # Service-specific prior auth attachments (no generic PA note code exists)
    HOME_HEALTH_PA: str = "http://loinc.org|52036-1"


@dataclass(frozen=True)
class SearchParams:
    """Default search parameters for FHIR queries."""

    QUESTIONNAIRE_COUNT: int = 10
    ELIGIBILITY_COUNT: int = 1
    DEFAULT_SORT: str = "-_lastUpdated"
    STATUS_FILTER: str = "active"


# Singleton instances
CODE_SYSTEMS = CodeSystems()
DOCUMENT_TYPES = DocumentTypes()
SEARCH_PARAMS = SearchParams()

# Default code system for procedure codes
DEFAULT_CODE_SYSTEM = CODE_SYSTEMS.CPT

# Document type codes commonly used in searches
DEFAULT_DOCUMENT_TYPE_CODES: list[str] = [
    DOCUMENT_TYPES.CONSULTATION_NOTE,
    DOCUMENT_TYPES.HISTORY_PHYSICAL,
    DOCUMENT_TYPES.EVALUATION_PLAN,
]


def get_code_system_url(name: str) -> str:
    """
    Get code system URL by common name.

    Args:
        name: Common name like 'cpt', 'snomed', 'loinc'

    Returns:
        Code system URL or empty string if not found
    """
    name_upper = name.upper().replace("-", "_")
    return getattr(CODE_SYSTEMS, name_upper, "")


def get_document_type_code(name: str) -> str:
    """
    Get document type LOINC code by name.

    Args:
        name: Document type name like 'progress_note', 'discharge_summary'

    Returns:
        LOINC code string or empty string if not found
    """
    name_upper = name.upper()
    return getattr(DOCUMENT_TYPES, name_upper, "")
