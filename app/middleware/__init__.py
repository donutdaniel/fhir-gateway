"""
Middleware for FHIR Gateway.
"""

from app.middleware.security import SecurityHeadersMiddleware

__all__ = ["SecurityHeadersMiddleware"]
