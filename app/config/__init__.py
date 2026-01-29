"""Configuration modules for FHIR Gateway."""

from app.config.logging import configure_logging, get_logger
from app.config.platform import (
    OAuthConfig,
    PlatformConfig,
    PlatformDefinition,
    get_all_platforms,
    get_config,
    get_platform,
    load_config,
    reload_config,
)
from app.config.settings import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
    "get_config",
    "get_platform",
    "get_all_platforms",
    "load_config",
    "reload_config",
    "PlatformConfig",
    "PlatformDefinition",
    "OAuthConfig",
    "configure_logging",
    "get_logger",
]
