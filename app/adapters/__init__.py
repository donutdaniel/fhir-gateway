"""
Platform adapters for FHIR Gateway.

Adapters handle platform-specific behavior and customizations.
"""

from app.adapters.base import BasePayerAdapter
from app.adapters.generic import GenericPayerAdapter
from app.adapters.registry import (
    PlatformAdapterNotFoundError,
    PlatformAdapterRegistry,
)

__all__ = [
    "BasePayerAdapter",
    "PlatformAdapterRegistry",
    "PlatformAdapterNotFoundError",
    "GenericPayerAdapter",
]
