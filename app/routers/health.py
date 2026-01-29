"""
Health check endpoints.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.adapters.registry import PlatformAdapterRegistry

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str
    platforms_registered: int


@router.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns the service status and basic information.
    """
    return {
        "status": "healthy",
        "service": "fhir-gateway",
        "version": "0.1.0",
        "platforms_registered": PlatformAdapterRegistry.get_platform_count(),
    }
