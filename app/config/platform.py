"""
Platform configuration loader for FHIR Gateway.

This module loads platform configuration from JSON files in the platforms directory.
Each platform has its own config file (e.g., platforms/aetna.json).
Shared defaults are defined in config/defaults.py.

The config is loaded once at startup and cached for the lifetime of the process.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.config.defaults import (
    CODE_SYSTEMS,
    DEFAULT_CODE_SYSTEM,
    DEFAULT_DOCUMENT_TYPE_CODES,
    DOCUMENT_TYPES,
)
from app.config.defaults import (
    SEARCH_PARAMS as DEFAULT_SEARCH_PARAMS,
)
from app.config.logging import get_logger

logger = get_logger(__name__)

# Path to platforms directory (where platform config files live)
PLATFORMS_DIR = Path(__file__).parent.parent / "platforms"

# Module-level cache for loaded config
_config_cache: Optional["PlatformConfig"] = None


@dataclass
class SearchParams:
    """Default search parameters."""

    questionnaire_count: int = 10
    eligibility_count: int = 1
    default_sort: str = "-created"
    status_filter: str = "active"


@dataclass
class PlatformEndpoints:
    """Platform API endpoints."""

    data: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.data.get(key, default)


@dataclass
class PlatformResources:
    """Platform resource links."""

    data: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.data.get(key, default)

    def items(self):
        return self.data.items()


@dataclass
class RegionalPlan:
    """Regional plan configuration (for federated platforms like BCBS)."""

    id: str
    name: str
    states: list[str]
    developer_portal: str | None = None
    fhir_base_url: str | None = None
    support_email: str | None = None


@dataclass
class OAuthConfig:
    """OAuth configuration for a platform."""

    authorize_url: str | None = None
    token_url: str | None = None
    revoke_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scopes: list[str] | None = None
    redirect_uri: str | None = None
    # Extended OAuth config
    scopes_supported: list[str] | None = None
    code_challenge_methods: list[str] | None = None
    token_endpoint_auth_methods: list[str] | None = None
    confidential: bool = False
    cors_relay_required: bool = False

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None, platform_id: str | None = None
    ) -> Optional["OAuthConfig"]:
        """Create OAuthConfig from a dictionary.

        If platform_id is provided, environment variables are checked for overrides:
        - FHIR_GATEWAY_PLATFORM_{PLATFORM_ID}_CLIENT_ID overrides client_id
        - FHIR_GATEWAY_PLATFORM_{PLATFORM_ID}_CLIENT_SECRET sets client_secret

        Platform ID is uppercased and hyphens are replaced with underscores.
        """
        if not data:
            return None

        config = cls(
            authorize_url=data.get("authorize_url"),
            token_url=data.get("token_url"),
            revoke_url=data.get("revoke_url"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes"),
            redirect_uri=data.get("redirect_uri"),
            scopes_supported=data.get("scopes_supported"),
            code_challenge_methods=data.get("code_challenge_methods"),
            token_endpoint_auth_methods=data.get("token_endpoint_auth_methods"),
            confidential=data.get("confidential", False),
            cors_relay_required=data.get("cors_relay_required", False),
        )

        if platform_id:
            config._apply_env_overrides(platform_id)

        return config

    def _apply_env_overrides(self, platform_id: str) -> None:
        """Apply environment variable overrides for OAuth credentials.

        Convention:
        - FHIR_GATEWAY_PLATFORM_{PLATFORM_ID}_CLIENT_ID
        - FHIR_GATEWAY_PLATFORM_{PLATFORM_ID}_CLIENT_SECRET
        """
        env_key = platform_id.upper().replace("-", "_")

        client_id_env = os.environ.get(f"FHIR_GATEWAY_PLATFORM_{env_key}_CLIENT_ID")
        if client_id_env:
            self.client_id = client_id_env
            logger.info(
                "OAuth client_id overridden by environment variable for platform '%s'",
                platform_id,
            )

        client_secret_env = os.environ.get(f"FHIR_GATEWAY_PLATFORM_{env_key}_CLIENT_SECRET")
        if client_secret_env:
            self.client_secret = client_secret_env
            logger.info(
                "OAuth client_secret set from environment variable for platform '%s'",
                platform_id,
            )


@dataclass
class PlatformCapabilities:
    """FHIR capabilities supported by a platform."""

    patient_access: bool = False
    provider_directory: bool = False
    crd: bool = False
    dtr: bool = False
    pas: bool = False
    cdex: bool = False
    patient_everything: bool = False
    bulk_data: bool = False
    claims_data: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PlatformCapabilities":
        """Create PlatformCapabilities from a dictionary."""
        if not data:
            return cls()
        return cls(
            patient_access=data.get("patient_access", False),
            provider_directory=data.get("provider_directory", False),
            crd=data.get("crd", False),
            dtr=data.get("dtr", False),
            pas=data.get("pas", False),
            cdex=data.get("cdex", False),
            patient_everything=data.get("patient_everything", False),
            bulk_data=data.get("bulk_data", False),
            claims_data=data.get("claims_data", False),
        )


@dataclass
class PlatformDefinition:
    """Definition of a platform from configuration."""

    id: str
    name: str
    display_name: str
    type: str | None = None
    aliases: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    developer_portal: str | None = None
    support_email: str | None = None
    fhir_base_url: str | None = None
    endpoints: PlatformEndpoints = field(default_factory=PlatformEndpoints)
    crd_hooks: list[str] | None = None
    document_type_codes: list[str] | None = None
    resources: PlatformResources = field(default_factory=PlatformResources)
    is_federation: bool = False
    regional_plans: dict[str, RegionalPlan] = field(default_factory=dict)

    # UHC-specific
    flex_domain: str | None = None
    known_plan_subdomains: list[str] | None = None

    # Capability tracking and verification
    sandbox_url: str | None = None
    oauth: OAuthConfig | None = None
    capabilities: PlatformCapabilities = field(default_factory=PlatformCapabilities)
    verification_status: str | None = None
    last_verified: str | None = None
    states: list[str] | None = None
    platform_ids: list[str] | None = None

    # Extended fields (for EHR platforms)
    fhir_version: str | None = None
    implementation_guides: list[str] | None = None
    api_products: list[str] | None = None
    supported_resources: list[str] | None = None
    client_headers: dict[str, str] | None = None
    rate_limited: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlatformDefinition":
        """Create a PlatformDefinition from a dictionary."""
        regional_plans = {}
        if "regional_plans" in data:
            for plan_id, plan_data in data["regional_plans"].items():
                regional_plans[plan_id] = RegionalPlan(
                    id=plan_data.get("id", plan_id),
                    name=plan_data.get("name", ""),
                    states=plan_data.get("states", []),
                    developer_portal=plan_data.get("developer_portal"),
                    fhir_base_url=plan_data.get("fhir_base_url"),
                    support_email=plan_data.get("support_email"),
                )

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            display_name=data.get("display_name", data.get("name", "")),
            type=data.get("type"),
            aliases=data.get("aliases", []),
            patterns=data.get("patterns", []),
            developer_portal=data.get("developer_portal"),
            support_email=data.get("support_email"),
            fhir_base_url=data.get("fhir_base_url"),
            endpoints=PlatformEndpoints(data.get("endpoints", {})),
            crd_hooks=data.get("crd_hooks"),
            document_type_codes=data.get("document_type_codes"),
            resources=PlatformResources(data.get("resources", {})),
            is_federation=data.get("is_federation", False),
            regional_plans=regional_plans,
            flex_domain=data.get("flex_domain"),
            known_plan_subdomains=data.get("known_plan_subdomains"),
            sandbox_url=data.get("sandbox_url"),
            oauth=OAuthConfig.from_dict(data.get("oauth"), platform_id=data.get("id")),
            capabilities=PlatformCapabilities.from_dict(data.get("capabilities")),
            verification_status=data.get("verification_status"),
            last_verified=data.get("last_verified"),
            states=data.get("states"),
            platform_ids=data.get(
                "payer_ids"
            ),  # Keep reading payer_ids from JSON for compatibility
            fhir_version=data.get("fhir_version"),
            implementation_guides=data.get("implementation_guides"),
            api_products=data.get("api_products"),
            supported_resources=data.get("supported_resources"),
            client_headers=data.get("client_headers"),
            rate_limited=data.get("rate_limited", False),
        )


@dataclass
class PlatformConfig:
    """Main configuration container loaded from config files."""

    default_code_system: str = "http://www.ama-assn.org/go/cpt"
    default_document_type_codes: list[str] = field(default_factory=list)
    search_params: SearchParams = field(default_factory=SearchParams)
    code_systems: dict[str, str] = field(default_factory=dict)
    document_type_codes: dict[str, str] = field(default_factory=dict)
    platforms: dict[str, PlatformDefinition] = field(default_factory=dict)

    def get_platform(self, platform_id: str) -> PlatformDefinition | None:
        """Get a platform definition by ID."""
        return self.platforms.get(platform_id)

    def get_code_system(self, name: str) -> str | None:
        """Get a code system URI by name (e.g., 'cpt', 'loinc')."""
        return self.code_systems.get(name)

    def get_document_type_code(self, name: str) -> str | None:
        """Get a document type LOINC code by name."""
        return self.document_type_codes.get(name)


def _scan_platform_configs(platforms_dir: Path) -> dict[str, PlatformDefinition]:
    """
    Scan the platforms directory for platform config files.

    Each platform has its own JSON file:
        platforms/aetna.json
        platforms/cigna.json
        etc.

    The filename (without .json) is used as the platform ID unless 'id' is specified in config.
    """
    platforms = {}

    if not platforms_dir.exists():
        logger.warning(f"Platforms directory not found at {platforms_dir}")
        return platforms

    # Scan for .json files
    for config_file in platforms_dir.glob("*.json"):
        try:
            with open(config_file, encoding="utf-8") as f:
                data = json.load(f)

            # Use the 'id' field from the config, or fall back to filename
            platform_id = data.get("id", config_file.stem)

            # Skip files that don't look like platform configs (no 'name' field)
            if "name" not in data:
                logger.debug(f"Skipping {config_file}: no 'name' field")
                continue

            platforms[platform_id] = PlatformDefinition.from_dict(data)
            logger.debug(f"Loaded platform config: {platform_id} from {config_file.name}")

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {config_file}: {e}")
        except Exception as e:
            logger.warning(f"Error loading {config_file}: {e}")

    return platforms


def load_config(platforms_dir: Path | None = None) -> PlatformConfig:
    """
    Load platform configuration from JSON files.

    This function scans the platforms directory for:
    - *.json files - individual platform configurations

    Defaults are loaded from config/defaults.py module.
    The config is loaded once and cached for the lifetime of the process.

    Args:
        platforms_dir: Optional path to platforms directory. Defaults to app/platforms.

    Returns:
        PlatformConfig instance with loaded configuration.
    """
    global _config_cache

    if _config_cache is not None:
        return _config_cache

    dir_path = platforms_dir or PLATFORMS_DIR

    logger.info(f"Loading platform configuration from {dir_path}")

    # Scan for individual platform configs
    platforms = _scan_platform_configs(dir_path)

    # Build code systems dict from defaults module
    code_systems = {
        "cpt": CODE_SYSTEMS.CPT,
        "hcpcs": CODE_SYSTEMS.HCPCS,
        "icd10cm": CODE_SYSTEMS.ICD10_CM,
        "icd10pcs": CODE_SYSTEMS.ICD10_PCS,
        "snomed": CODE_SYSTEMS.SNOMED,
        "loinc": CODE_SYSTEMS.LOINC,
        "rxnorm": CODE_SYSTEMS.RXNORM,
        "ndc": CODE_SYSTEMS.NDC,
    }

    # Build document types dict from defaults module
    document_types = {
        "consultation_note": DOCUMENT_TYPES.CONSULTATION_NOTE,
        "history_physical": DOCUMENT_TYPES.HISTORY_PHYSICAL,
        "evaluation_plan": DOCUMENT_TYPES.EVALUATION_PLAN,
        "discharge_summary": DOCUMENT_TYPES.DISCHARGE_SUMMARY,
        "progress_note": DOCUMENT_TYPES.PROGRESS_NOTE,
        "referral_note": DOCUMENT_TYPES.REFERRAL_NOTE,
        "home_health_pa": DOCUMENT_TYPES.HOME_HEALTH_PA,
    }

    _config_cache = PlatformConfig(
        default_code_system=DEFAULT_CODE_SYSTEM,
        default_document_type_codes=list(DEFAULT_DOCUMENT_TYPE_CODES),
        search_params=SearchParams(
            questionnaire_count=DEFAULT_SEARCH_PARAMS.QUESTIONNAIRE_COUNT,
            eligibility_count=DEFAULT_SEARCH_PARAMS.ELIGIBILITY_COUNT,
            default_sort=DEFAULT_SEARCH_PARAMS.DEFAULT_SORT,
            status_filter=DEFAULT_SEARCH_PARAMS.STATUS_FILTER,
        ),
        code_systems=code_systems,
        document_type_codes=document_types,
        platforms=platforms,
    )

    logger.info(
        f"Loaded configuration with {len(_config_cache.platforms)} platforms, "
        f"{len(_config_cache.code_systems)} code systems"
    )

    return _config_cache


def get_config() -> PlatformConfig:
    """
    Get the current platform configuration.

    Loads the config if not already loaded.

    Returns:
        PlatformConfig instance.
    """
    if _config_cache is None:
        return load_config()
    return _config_cache


def reload_config(platforms_dir: Path | None = None) -> PlatformConfig:
    """
    Force reload of platform configuration.

    Use this for testing or if config files have changed.

    Args:
        platforms_dir: Optional path to platforms directory.

    Returns:
        Newly loaded PlatformConfig instance.
    """
    global _config_cache
    _config_cache = None
    return load_config(platforms_dir)


# Convenience functions for common lookups


def get_default_code_system() -> str:
    """Get the default code system URI (CPT)."""
    return get_config().default_code_system


def get_default_document_type_codes() -> list[str]:
    """Get the default document type codes for platform rule searches."""
    return get_config().default_document_type_codes


def get_search_params() -> SearchParams:
    """Get default search parameters."""
    return get_config().search_params


def get_platform(platform_id: str) -> PlatformDefinition | None:
    """Get a platform definition by ID."""
    return get_config().get_platform(platform_id)


def get_all_platforms() -> dict[str, PlatformDefinition]:
    """Get all platform definitions as a dictionary."""
    return get_config().platforms


def get_code_system_uri(name: str) -> str | None:
    """Get a code system URI by name."""
    return get_config().get_code_system(name)
