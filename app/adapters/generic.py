"""
Generic platform adapter.

This adapter dynamically handles any platform based on configuration loaded from
app/platforms/{platform_id}.json. It eliminates the need for individual adapter
files for each platform.
"""

from fhirpy import AsyncFHIRClient

from app.adapters.base import BasePayerAdapter
from app.config.logging import get_logger
from app.config.platform import get_platform
from app.models.platform import PlatformInfo

logger = get_logger(__name__)


class GenericPayerAdapter(BasePayerAdapter):
    """
    Generic adapter that works with any platform based on configuration.

    Instead of creating a separate adapter class for each platform, this adapter
    takes a platform_id at construction time and loads all configuration
    dynamically from the platform's JSON config file.
    """

    def __init__(
        self,
        platform_id: str,
        client: AsyncFHIRClient,
        platform_info: PlatformInfo | None = None,
    ) -> None:
        """
        Initialize the generic platform adapter.

        Args:
            platform_id: The platform identifier (e.g., "cigna", "aetna")
            client: AsyncFHIRClient instance for FHIR operations
            platform_info: Optional platform information
        """
        super().__init__(client, platform_info)
        self._platform_id = platform_id

    @property
    def _platform_config(self):
        """Get platform configuration from config file."""
        return get_platform(self._platform_id)

    @property
    def fhir_base_url(self) -> str | None:
        """Get FHIR base URL from config for multi-platform routing."""
        config = self._platform_config
        return config.fhir_base_url if config else None

    @property
    def adapter_name(self) -> str:
        """Return the name of this adapter for logging/identification."""
        return f"{self._platform_id.title()}Adapter"

    @property
    def developer_portal(self) -> str | None:
        """Get developer portal URL from config."""
        config = self._platform_config
        return config.developer_portal if config else None

    @property
    def sandbox_url(self) -> str | None:
        """Get sandbox URL from config."""
        config = self._platform_config
        return config.sandbox_url if config else None

    def get_endpoint(self, name: str) -> str | None:
        """Get a named endpoint from config."""
        config = self._platform_config
        return config.endpoints.get(name) if config else None

    def get_resource(self, name: str) -> str | None:
        """Get a named resource URL from config."""
        config = self._platform_config
        return config.resources.get(name) if config else None
