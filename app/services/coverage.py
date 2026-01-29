"""
High-level coverage operations.

This module provides the main entry points for coverage operations,
composing adapters and transformers to deliver complete functionality.

Multi-platform routing:
- Each operation can route to a platform-specific FHIR endpoint if the adapter
  has a configured fhir_base_url.
- The access token from the default client is passed to create platform-specific clients.
- If no platform-specific URL is configured, the default client is used.
"""

from typing import Any

from fhirpy import AsyncFHIRClient

from app.adapters.base import BasePayerAdapter
from app.adapters.registry import PlatformAdapterRegistry
from app.config.logging import get_logger
from app.config.platform import get_platform
from app.models.coverage import (
    CoverageRequirement,
    PlatformReference,
    PlatformRulesResult,
    QuestionnairePackageResult,
)
from app.transformers import transform_questionnaire_bundle

logger = get_logger(__name__)


async def _initialize_platform_client(
    adapter: BasePayerAdapter,
    default_client: AsyncFHIRClient,
) -> None:
    """
    Initialize a platform-specific client for the adapter if it has a configured URL.

    This enables multi-platform routing by creating a client that points to the
    platform's specific FHIR endpoint while reusing the access token from the
    default client.

    Args:
        adapter: The platform adapter to initialize
        default_client: The default FHIR client (used to extract access token)
    """
    if not adapter.fhir_base_url:
        return

    # Extract access token from the default client's authorization header
    # Note: fhirpy's AsyncFHIRClient stores auth in _authorization (private attribute)
    access_token = None
    if hasattr(default_client, "_authorization") and default_client._authorization:
        auth_header = str(default_client._authorization)
        # Handle "Bearer <token>" format (case-insensitive prefix check)
        if auth_header.lower().startswith("bearer "):
            # Extract token after "Bearer " (7 characters)
            token = auth_header[7:].strip()
            if token:  # Only set if we actually have a token
                access_token = token
            else:
                logger.warning("Authorization header contains 'Bearer' prefix but no token")
        else:
            logger.debug("Authorization header present but not Bearer format for platform routing")

    # Get timeout from default client config
    timeout = 30.0
    if hasattr(default_client, "_aiohttp_config"):
        aiohttp_config = default_client._aiohttp_config
        if "timeout" in aiohttp_config and hasattr(aiohttp_config["timeout"], "total"):
            timeout = aiohttp_config["timeout"].total or 30.0

    logger.debug(
        f"Initializing platform client: url={adapter.fhir_base_url}, "
        f"has_token={access_token is not None}, timeout={timeout}"
    )

    await adapter.initialize_platform_client(
        access_token=access_token,
        timeout=timeout,
    )


async def check_coverage_requirements(
    client: AsyncFHIRClient,
    patient_id: str,
    coverage_id: str,
    procedure_code: str,
    code_system: str = "http://www.ama-assn.org/go/cpt",
    platform_id: str | None = None,
) -> CoverageRequirement:
    """
    Check if prior authorization is required for a procedure.

    This operation simulates the CRD (Coverage Requirements Discovery)
    workflow to determine if a procedure requires prior authorization for a
    specific patient and coverage.

    Args:
        client: AsyncFHIRClient for FHIR operations
        patient_id: FHIR Patient resource ID
        coverage_id: FHIR Coverage resource ID
        procedure_code: CPT/HCPCS procedure code to check
        code_system: Code system URL (default: CPT)
        platform_id: Optional platform identifier for direct routing (e.g., 'aetna', 'anthem')

    Returns:
        CoverageRequirement with authorization status and details
    """
    logger.info(
        f"Checking coverage requirements: patient={patient_id}, "
        f"coverage={coverage_id}, procedure={procedure_code}, platform_id={platform_id}"
    )

    # Get platform info
    platform_info = None
    coverage = {}

    if platform_id:
        logger.debug(f"Using provided platform_id for routing: {platform_id}")
        platform_config = get_platform(platform_id)
        platform_info = PlatformReference(
            id=platform_id, name=platform_config.display_name if platform_config else None
        )
        # Still fetch coverage for other info
        try:
            coverage = await client.get(
                resource_type_or_resource_or_ref="Coverage",
                id_or_ref=coverage_id,
            )
        except Exception as e:
            logger.warning(f"Could not fetch coverage {coverage_id}: {e}")
    else:
        # Get coverage to determine platform
        try:
            coverage = await client.get(
                resource_type_or_resource_or_ref="Coverage",
                id_or_ref=coverage_id,
            )
            # Extract platform from coverage
            payor = coverage.get("payor", [])
            if payor:
                payor_ref = payor[0]
                if isinstance(payor_ref, dict):
                    reference = payor_ref.get("reference", "")
                    display = payor_ref.get("display")
                    pid = reference.split("/")[-1] if "/" in reference else reference
                    platform_info = PlatformReference(id=pid, name=display)
        except Exception as e:
            logger.warning(f"Could not fetch coverage {coverage_id}: {e}")

    # Get adapter
    adapter = PlatformAdapterRegistry.get_adapter(
        platform_info=platform_info,
        client=client,
    )

    # Initialize platform-specific client if the adapter has a configured URL
    await _initialize_platform_client(adapter, client)

    # Execute the coverage requirements check
    result = await adapter.check_coverage_requirements(
        patient_id=patient_id,
        coverage_id=coverage_id,
        procedure_code=procedure_code,
        code_system=code_system,
        coverage=coverage if coverage else None,
    )

    logger.info(f"Coverage requirements check complete: status={result.status.value}")

    return result


async def fetch_questionnaire_package(
    client: AsyncFHIRClient,
    coverage_id: str,
    questionnaire_url: str | None = None,
    raw_format: bool = False,
    platform_id: str | None = None,
) -> QuestionnairePackageResult | dict[str, Any]:
    """
    Fetch and transform a questionnaire package from the platform.

    This operation executes the DTR $questionnaire-package operation
    to retrieve questionnaires needed for prior authorization documentation.

    Args:
        client: AsyncFHIRClient for FHIR operations
        coverage_id: FHIR Coverage resource ID for context
        questionnaire_url: Optional specific questionnaire canonical URL
        raw_format: If True, return raw FHIR Bundle instead of transformed result
        platform_id: Optional platform identifier for direct routing (e.g., 'aetna', 'anthem')

    Returns:
        QuestionnairePackageResult with transformed questionnaires, or
        raw FHIR Bundle if raw_format=True
    """
    logger.info(
        f"Fetching questionnaire package: coverage={coverage_id}, "
        f"questionnaire={questionnaire_url}, raw={raw_format}, platform_id={platform_id}"
    )

    # Get platform info
    platform_info = None

    if platform_id:
        logger.debug(f"Using provided platform_id for routing: {platform_id}")
        platform_config = get_platform(platform_id)
        platform_info = PlatformReference(
            id=platform_id, name=platform_config.display_name if platform_config else None
        )
    else:
        # Get coverage to determine platform
        try:
            coverage = await client.get(
                resource_type_or_resource_or_ref="Coverage",
                id_or_ref=coverage_id,
            )
            payor = coverage.get("payor", [])
            if payor:
                payor_ref = payor[0]
                if isinstance(payor_ref, dict):
                    reference = payor_ref.get("reference", "")
                    display = payor_ref.get("display")
                    pid = reference.split("/")[-1] if "/" in reference else reference
                    platform_info = PlatformReference(id=pid, name=display)
        except Exception as e:
            logger.warning(f"Could not fetch coverage {coverage_id}: {e}")

    # Get appropriate adapter
    adapter = PlatformAdapterRegistry.get_adapter(
        platform_info=platform_info,
        client=client,
    )

    # Initialize platform-specific client if the adapter has a configured URL
    await _initialize_platform_client(adapter, client)

    # Fetch the questionnaire package
    bundle = await adapter.fetch_questionnaire_package(
        coverage_id=coverage_id,
        questionnaire_url=questionnaire_url,
    )

    # Return raw if requested
    if raw_format:
        return {"raw_bundle": bundle}

    # Transform the bundle
    result = transform_questionnaire_bundle(bundle, raw_format=False)

    logger.info(
        f"Questionnaire package fetch complete: {len(result.questionnaires)} questionnaires"
    )

    return result


async def get_platform_rules(
    client: AsyncFHIRClient,
    platform_id: str,
    procedure_code: str,
    code_system: str = "http://www.ama-assn.org/go/cpt",
) -> PlatformRulesResult:
    """
    Retrieve medical policy rules for a procedure from a platform.

    This operation searches for policy documentation, questionnaires, and
    other resources that define the requirements for a procedure.

    Args:
        client: AsyncFHIRClient for FHIR operations
        platform_id: Platform identifier
        procedure_code: CPT/HCPCS procedure code to look up
        code_system: Code system URL (default: CPT)

    Returns:
        PlatformRulesResult with matching policy rules and markdown summary
    """
    logger.info(f"Getting platform rules: platform={platform_id}, procedure={procedure_code}")

    # Try to get platform name from config
    platform_config = get_platform(platform_id)
    platform_name = platform_config.display_name if platform_config else None

    # Create platform info for adapter selection
    platform_info = PlatformReference(id=platform_id, name=platform_name)

    # Get appropriate adapter
    adapter = PlatformAdapterRegistry.get_adapter(
        platform_info=platform_info,
        client=client,
    )

    # Initialize platform-specific client if the adapter has a configured URL
    await _initialize_platform_client(adapter, client)

    # Get the rules
    result = await adapter.get_platform_rules(
        platform_id=platform_id,
        procedure_code=procedure_code,
        code_system=code_system,
    )

    logger.info(f"Platform rules lookup complete: {len(result.rules)} rules found")

    return result
