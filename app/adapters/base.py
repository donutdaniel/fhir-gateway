"""
Base class for platform adapters.

This module defines the base class with default implementations that all
platform adapters inherit from. Platform-specific adapters can override any
method to customize behavior.
"""

from abc import ABC, abstractmethod
from typing import Any

import aiohttp
from fhirpy import AsyncFHIRClient

from app.config.logging import get_logger
from app.models.coverage import (
    CoverageRequirement,
    CoverageRequirementStatus,
    PlatformReference,
    PlatformRulesResult,
)
from app.models.platform import PlatformInfo

logger = get_logger(__name__)


class BasePayerAdapter(ABC):
    """
    Base class for platform-specific implementations.

    Each platform adapter handles the specifics of communicating with a particular
    platform's endpoints. This base class provides default implementations for
    standard FHIR operations that work with any compliant server.
    """

    def __init__(
        self,
        client: AsyncFHIRClient,
        platform_info: PlatformInfo | None = None,
    ):
        """
        Initialize the platform adapter.

        Args:
            client: AsyncFHIRClient instance for FHIR operations
            platform_info: Optional platform information
        """
        self._default_client = client
        self._platform_client: AsyncFHIRClient | None = None
        self.platform_info = platform_info

    @property
    def client(self) -> AsyncFHIRClient:
        """Get the FHIR client to use for operations."""
        if self._platform_client is not None:
            return self._platform_client
        return self._default_client

    @property
    def fhir_base_url(self) -> str | None:
        """Get the platform-specific FHIR base URL."""
        return None

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Return the name of this adapter for logging/identification."""
        pass

    async def initialize_platform_client(
        self,
        access_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize a platform-specific FHIR client if a base URL is configured.

        Args:
            access_token: OAuth access token for the platform's API
            timeout: Request timeout in seconds
        """
        base_url = self.fhir_base_url
        if not base_url:
            logger.debug(f"{self.adapter_name}: No platform-specific URL, using default client")
            return

        logger.info(f"{self.adapter_name}: Creating platform-specific client for {base_url}")

        client_kwargs: dict[str, Any] = {
            "url": base_url,
            "aiohttp_config": {
                "timeout": aiohttp.ClientTimeout(total=timeout),
            },
            "extra_headers": {
                "Accept": "application/fhir+json",
                "Content-Type": "application/fhir+json",
            },
        }

        if access_token:
            client_kwargs["authorization"] = f"Bearer {access_token}"

        self._platform_client = AsyncFHIRClient(**client_kwargs)

    async def get_coverage(self, coverage_id: str) -> dict[str, Any]:
        """
        Fetch a Coverage resource by ID.

        Args:
            coverage_id: FHIR Coverage resource ID

        Returns:
            Coverage resource as dictionary
        """
        logger.debug(f"Fetching Coverage/{coverage_id}")
        return await self.client.get(
            resource_type_or_resource_or_ref="Coverage",
            id_or_ref=coverage_id,
        )

    async def get_patient(self, patient_id: str) -> dict[str, Any]:
        """
        Fetch a Patient resource by ID.

        Args:
            patient_id: FHIR Patient resource ID

        Returns:
            Patient resource as dictionary
        """
        logger.debug(f"Fetching Patient/{patient_id}")
        return await self.client.get(
            resource_type_or_resource_or_ref="Patient",
            id_or_ref=patient_id,
        )

    def extract_payer_from_coverage(self, coverage: dict[str, Any]) -> PlatformInfo | None:
        """
        Extract platform information from a Coverage resource.

        Args:
            coverage: FHIR Coverage resource

        Returns:
            PlatformInfo if platform can be identified, else None
        """
        payor = coverage.get("payor", [])
        if not payor:
            return None

        payor_ref = payor[0]
        if isinstance(payor_ref, dict):
            reference = payor_ref.get("reference", "")
            display = payor_ref.get("display")

            platform_id = reference.split("/")[-1] if "/" in reference else reference

            return PlatformInfo(
                id=platform_id,
                name=display,
            )

        return None

    async def check_coverage_requirements(
        self,
        patient_id: str,
        coverage_id: str,
        procedure_code: str,
        code_system: str = "http://www.ama-assn.org/go/cpt",
        coverage: dict[str, Any] | None = None,
    ) -> CoverageRequirement:
        """
        Check if prior authorization is required for a procedure.

        This default implementation simulates a CRD response. Platform-specific
        adapters can override this to integrate with actual CRD endpoints.

        Args:
            patient_id: FHIR Patient resource ID
            coverage_id: FHIR Coverage resource ID
            procedure_code: CPT/HCPCS procedure code
            code_system: Code system URL
            coverage: Pre-fetched Coverage resource (optional)

        Returns:
            CoverageRequirement with authorization status
        """
        logger.info(f"{self.adapter_name}: Checking coverage requirements for {procedure_code}")

        # Build platform info from coverage or payer_info
        platform_info = None
        if coverage:
            extracted = self.extract_payer_from_coverage(coverage)
            if extracted:
                platform_info = PlatformReference(
                    id=extracted.id,
                    name=extracted.name,
                )
        elif self.platform_info:
            platform_info = PlatformReference(
                id=self.platform_info.id,
                name=self.platform_info.name,
            )

        # Default implementation returns unknown status
        # Real platforms would call CRD endpoint here
        return CoverageRequirement(
            status=CoverageRequirementStatus.UNKNOWN,
            platform=platform_info,
            procedure_code=procedure_code,
            code_system=code_system,
            questionnaire_url=None,
            documentation_required=False,
            info_needed=None,
            reason="CRD endpoint not configured for this platform. Contact platform directly.",
            coverage_id=coverage_id,
            patient_id=patient_id,
        )

    async def fetch_questionnaire_package(
        self,
        coverage_id: str,
        questionnaire_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch a questionnaire package from the platform.

        Executes the DTR $questionnaire-package operation.

        Args:
            coverage_id: FHIR Coverage resource ID for context
            questionnaire_url: Optional specific questionnaire canonical URL

        Returns:
            FHIR Bundle with questionnaires
        """
        logger.info(
            f"{self.adapter_name}: Fetching questionnaire package for coverage {coverage_id}"
        )

        # Try to execute $questionnaire-package operation
        # This is a DTR operation that may not be supported by all platforms
        try:
            params = {}
            if questionnaire_url:
                params["questionnaire"] = questionnaire_url

            # Try to call the operation
            coverage_ref = f"Coverage/{coverage_id}"
            result = await self.client.execute(
                resource_type="Questionnaire",
                operation="$questionnaire-package",
                method="POST",
                data={
                    "resourceType": "Parameters",
                    "parameter": [
                        {"name": "coverage", "valueReference": {"reference": coverage_ref}},
                    ],
                },
            )
            return result
        except Exception as e:
            logger.warning(f"{self.adapter_name}: $questionnaire-package not supported: {e}")
            # Return empty bundle
            return {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [],
            }

    async def get_platform_rules(
        self,
        platform_id: str,
        procedure_code: str,
        code_system: str = "http://www.ama-assn.org/go/cpt",
    ) -> PlatformRulesResult:
        """
        Retrieve medical policy rules for a procedure.

        Args:
            platform_id: Platform identifier
            procedure_code: CPT/HCPCS procedure code
            code_system: Code system URL

        Returns:
            PlatformRulesResult with policy rules and markdown summary
        """
        logger.info(f"{self.adapter_name}: Getting platform rules for {procedure_code}")

        # Default implementation returns empty rules
        # Real platforms would search for policy documents, questionnaires, etc.
        return PlatformRulesResult(
            platform_id=platform_id,
            procedure_code=procedure_code,
            code_system=code_system,
            rules=[],
            markdown_summary=f"# Policy Rules for {procedure_code}\n\nNo policy rules found for this procedure code. Contact the platform directly for coverage information.",
            last_updated=None,
        )
