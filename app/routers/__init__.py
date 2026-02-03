"""
API routers for FHIR Gateway.
"""

from app.routers.auth import router as auth_router
from app.routers.fhir import router as fhir_router
from app.routers.health import router as health_router
from app.routers.oauth import router as oauth_router
from app.routers.pages import router as pages_router
from app.routers.platforms import router as platforms_router

__all__ = [
    "fhir_router",
    "auth_router",
    "health_router",
    "oauth_router",
    "pages_router",
    "platforms_router",
]
