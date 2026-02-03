"""
FHIR Gateway - Main application entry point.

A standalone REST API gateway for FHIR operations with multi-platform routing.
"""

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.registry import PlatformAdapterRegistry
from app.auth.token_manager import cleanup_token_manager, get_token_manager
from app.config.logging import configure_logging, get_logger
from app.config.platform import load_config
from app.config.settings import get_settings
from app.mcp.server import mcp
from app.middleware.security import (
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.routers import auth_router, fhir_router, health_router, oauth_router, pages_router, platforms_router
from app.routers.coverage import router as coverage_router

logger = get_logger(__name__)

# Background task for session cleanup
_cleanup_task: asyncio.Task | None = None


async def _session_cleanup_loop():
    """Background task to clean up expired sessions periodically."""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            token_manager = get_token_manager()
            cleaned = await token_manager.cleanup_expired_sessions()
            if cleaned > 0:
                logger.info("Session cleanup completed", sessions_cleaned=cleaned)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Session cleanup failed", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global _cleanup_task

    # Startup
    settings = get_settings()
    configure_logging(level=settings.log_level, json_format=settings.log_json)
    logger.info("Starting FHIR Gateway", host=settings.host, port=settings.port)

    # Load platform configuration
    config = load_config()
    logger.info("Loaded platform configuration", platform_count=len(config.platforms))

    # Auto-register platform adapters
    count = PlatformAdapterRegistry.auto_register()
    logger.info("Registered platform adapters", count=count)

    # Start background cleanup task
    _cleanup_task = asyncio.create_task(_session_cleanup_loop())
    logger.info("Started session cleanup background task")

    # Initialize MCP session manager for streamable-http
    mcp.streamable_http_app()
    async with mcp._session_manager.run():
        logger.info("Started MCP session manager")
        yield

    # Shutdown
    logger.info("Shutting down FHIR Gateway")

    # Cancel cleanup task
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass

    # Cleanup token manager
    await cleanup_token_manager()
    logger.info("Cleaned up token manager")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="FHIR Gateway",
        description="REST API and MCP server for FHIR operations with multi-platform routing",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Add CORS middleware
    origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware, session_cookie_name=settings.session_cookie_name)

    # Add request size limit middleware
    app.add_middleware(RequestSizeLimitMiddleware, max_body_size=settings.max_request_body_size)

    # Register REST API routers
    app.include_router(pages_router)
    app.include_router(health_router)
    app.include_router(platforms_router)
    app.include_router(fhir_router)
    app.include_router(auth_router)
    app.include_router(oauth_router)
    app.include_router(coverage_router)

    # Mount MCP server at /mcp (streamable-http transport)
    mcp.settings.streamable_http_path = "/"
    mcp_app = mcp.streamable_http_app()
    app.mount("/mcp", mcp_app)
    logger.info("Mounted MCP server at /mcp")

    return app


# Create the application instance
app = create_app()


def run():
    """
    Run the FHIR Gateway server.

    Starts the REST API and MCP server on the same port via uvicorn.
    MCP is available at /mcp using streamable-http transport.
    """
    settings = get_settings()
    configure_logging(level=settings.log_level, json_format=settings.log_json)

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
