"""
Application settings using pydantic-settings.

Environment variables are prefixed with FHIR_GATEWAY_.
"""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ so platform config can read dynamic credentials
# (e.g., FHIR_GATEWAY_PLATFORM_EPIC_SANDBOX_PATIENT_CLIENT_ID)
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="FHIR_GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allow_credentials(self) -> bool:
        """Allow credentials only when specific origins are configured (not wildcard)."""
        return self.cors_origins != "*"

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    public_url: str = "http://localhost:8000"  # Public endpoint URL for MCP connection instructions

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    # Session settings
    session_max_age: int = 3600  # 1 hour
    session_cookie_secure: bool = True  # Set to False for local development over HTTP

    # OAuth settings
    oauth_redirect_uri: str = "http://localhost:8000/oauth/callback"

    # CORS settings
    cors_origins: str = "*"  # Set specific origins in prod to enable credentials

    # Redis settings (for production token storage)
    redis_url: str | None = None  # e.g., redis://localhost:6379 or rediss://... for TLS
    require_redis_tls: bool = False  # Require rediss:// scheme

    # Encryption settings (required)
    master_key: str | None = None  # Master key for encrypting session secrets at rest

    # Multi-key configuration for key rotation (JSON array)
    # Format: [{"id": "key1", "key": "...", "primary": true}, {"id": "key2", "key": "..."}]
    # When set, this takes precedence over master_key
    master_keys: str | None = None

    # Proxy settings (for secure IP detection behind load balancers)
    # Comma-separated CIDR ranges. Empty string = use defaults (loopback + private ranges)
    # Set to "none" to disable proxy header trust entirely
    trusted_proxy_cidrs: str = ""

    # MCP allowed hosts (comma-separated) for DNS rebinding protection
    # Auto-derived from public_url if not set. Use "*" to disable protection.
    mcp_allowed_hosts: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
