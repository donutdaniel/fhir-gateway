"""
Platform adapter registry for selecting appropriate adapters.

This module provides a registry pattern for managing platform-specific adapters.
It auto-registers all platforms found in app/platforms/*.json and uses the
GenericPlatformAdapter for all of them.
"""

import json
from pathlib import Path

from fhirpy import AsyncFHIRClient

from app.adapters.base import BasePayerAdapter
from app.config.logging import get_logger
from app.models.platform import PlatformInfo

logger = get_logger(__name__)

# Path to platforms directory (where platform config files live)
PLATFORMS_DIR = Path(__file__).parent.parent / "platforms"


class PlatformAdapterNotFoundError(Exception):
    """Raised when no adapter is found for a platform."""

    def __init__(self, platform_info: PlatformInfo | None = None, platform_id: str | None = None):
        self.platform_info = platform_info
        self.platform_id = platform_id
        if platform_info:
            message = (
                f"No adapter found for platform: id='{platform_info.id}', "
                f"name='{platform_info.name}'. "
                f"Please use a supported platform ID or register an adapter."
            )
        elif platform_id:
            message = (
                f"No adapter found for platform_id='{platform_id}'. "
                f"Please use a supported platform ID or register an adapter."
            )
        else:
            message = "No platform information provided and no adapter found."
        super().__init__(message)


class PlatformAdapterRegistry:
    """
    Registry for platform-specific adapters.

    This registry maintains a set of known platform IDs and their aliases.
    All platforms use the GenericPlatformAdapter, which loads configuration
    dynamically from app/platforms/{platform_id}.json.
    """

    _platform_ids: set[str] = set()
    _aliases: dict[str, str] = {}
    _patterns: dict[str, str] = {}

    @classmethod
    def register(cls, platform_id: str, aliases: list[str] | None = None) -> None:
        """
        Register a platform ID with optional aliases.

        Args:
            platform_id: Canonical platform identifier
            aliases: Optional list of alternative identifiers
        """
        platform_id_lower = platform_id.lower()
        cls._platform_ids.add(platform_id_lower)
        logger.debug(f"Registered platform: {platform_id}")

        if aliases:
            for alias in aliases:
                cls._aliases[alias.lower()] = platform_id_lower
                logger.debug(f"Registered alias '{alias}' -> {platform_id}")

    @classmethod
    def register_pattern(cls, pattern: str, platform_id: str) -> None:
        """
        Register a pattern that maps to a platform ID.

        Args:
            pattern: Substring pattern to match
            platform_id: Canonical platform ID to use when pattern matches
        """
        cls._patterns[pattern.lower()] = platform_id.lower()
        logger.debug(f"Registered pattern '{pattern}' -> {platform_id}")

    @classmethod
    def auto_register(cls, platforms_dir: Path | None = None) -> int:
        """
        Auto-register all platforms from the platforms directory.

        Args:
            platforms_dir: Optional path to platforms directory

        Returns:
            Number of platforms registered
        """
        dir_path = platforms_dir or PLATFORMS_DIR

        if not dir_path.exists():
            logger.warning(f"Platforms directory not found: {dir_path}")
            return 0

        count = 0
        for config_file in dir_path.glob("*.json"):
            try:
                with open(config_file, encoding="utf-8") as f:
                    data = json.load(f)

                platform_id = data.get("id", config_file.stem)
                aliases = data.get("aliases", [])
                patterns = data.get("patterns", [])

                cls.register(platform_id, aliases)

                for pattern in patterns:
                    cls.register_pattern(pattern, platform_id)

                count += 1

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in {config_file}: {e}")
            except Exception as e:
                logger.warning(f"Error loading {config_file}: {e}")

        logger.info(f"Auto-registered {count} platforms from {dir_path}")
        return count

    @classmethod
    def _resolve_platform_id(cls, platform_id: str) -> str | None:
        """Resolve a platform ID or alias to the canonical platform ID."""
        platform_id_lower = platform_id.lower()

        if platform_id_lower in cls._platform_ids:
            return platform_id_lower

        if platform_id_lower in cls._aliases:
            return cls._aliases[platform_id_lower]

        for pattern, canonical_id in cls._patterns.items():
            if pattern in platform_id_lower:
                return canonical_id

        return None

    @classmethod
    def get_adapter(
        cls,
        platform_info: PlatformInfo | None,
        client: AsyncFHIRClient,
    ) -> BasePayerAdapter:
        """
        Get the appropriate adapter for a platform.

        Args:
            platform_info: Platform information (required)
            client: AsyncFHIRClient for FHIR operations

        Returns:
            Instantiated GenericPlatformAdapter for the platform

        Raises:
            PlatformAdapterNotFoundError: If no adapter is found for the platform
        """
        from app.adapters.generic import GenericPayerAdapter

        if not platform_info:
            raise PlatformAdapterNotFoundError()

        canonical_id = cls._resolve_platform_id(platform_info.id)

        if not canonical_id:
            if platform_info.name:
                for pattern, pid in cls._patterns.items():
                    if pattern in platform_info.name.lower():
                        canonical_id = pid
                        break

        if not canonical_id:
            raise PlatformAdapterNotFoundError(platform_info)

        logger.info(f"Using GenericPlatformAdapter for platform {canonical_id}")
        return GenericPayerAdapter(
            platform_id=canonical_id,
            client=client,
            platform_info=platform_info,
        )

    @classmethod
    def get_adapter_by_id(
        cls,
        platform_id: str,
        client: AsyncFHIRClient,
    ) -> BasePayerAdapter:
        """
        Get an adapter directly by platform ID.

        Args:
            platform_id: Platform identifier
            client: AsyncFHIRClient for FHIR operations

        Returns:
            Instantiated GenericPlatformAdapter for the platform

        Raises:
            PlatformAdapterNotFoundError: If no adapter is found for the platform
        """
        from app.adapters.generic import GenericPayerAdapter

        canonical_id = cls._resolve_platform_id(platform_id)

        if not canonical_id:
            raise PlatformAdapterNotFoundError(platform_id=platform_id)

        logger.info(f"Using GenericPlatformAdapter for platform {canonical_id}")
        return GenericPayerAdapter(
            platform_id=canonical_id,
            client=client,
            platform_info=PlatformInfo(id=canonical_id),
        )

    @classmethod
    def has_adapter(cls, platform_info: PlatformInfo | None) -> bool:
        """Check if an adapter exists for the given platform."""
        if not platform_info:
            return False
        return cls._resolve_platform_id(platform_info.id) is not None

    @classmethod
    def list_registered(cls) -> list[str]:
        """List all registered platform IDs."""
        return sorted(cls._platform_ids)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered platforms (useful for testing)."""
        cls._platform_ids.clear()
        cls._aliases.clear()
        cls._patterns.clear()

    @classmethod
    def get_platform_count(cls) -> int:
        """Get the number of registered platforms."""
        return len(cls._platform_ids)

    @classmethod
    def get_platform_fhir_url(cls, platform_id: str) -> str | None:
        """Get the FHIR base URL for a platform."""
        from app.config.platform import get_platform

        canonical_id = cls._resolve_platform_id(platform_id)
        if not canonical_id:
            raise PlatformAdapterNotFoundError(platform_id=platform_id)

        platform_config = get_platform(canonical_id)
        if platform_config:
            return platform_config.fhir_base_url

        return None
