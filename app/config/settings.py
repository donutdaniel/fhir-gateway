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

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    # Request settings
    request_timeout: int = 30

    # Session settings
    session_cookie_name: str = "app_session"
    session_max_age: int = 3600  # 1 hour
    session_cookie_secure: bool = True  # Set to False for local development over HTTP

    # OAuth settings
    oauth_redirect_uri: str = "http://localhost:8000/oauth/callback"

    # CORS settings
    cors_origins: str = "*"  # Set specific origins in prod to enable credentials

    # Redis settings (for production token storage)
    redis_url: str | None = None  # e.g., redis://localhost:6379 or rediss://... for TLS
    require_redis_tls: bool = False  # Require rediss:// scheme

    # Encryption settings
    master_key: str | None = None  # Master key for encrypting session secrets at rest

    # Rate limiting
    rate_limit_max: int = 100  # Max requests per window per session
    rate_limit_window: int = 60  # Window duration in seconds
    callback_rate_limit_max: int = 20  # Max OAuth callback requests per window
    callback_rate_limit_window: int = 60  # Callback rate limit window in seconds

    # Request limits
    max_request_body_size: int = 10 * 1024 * 1024  # 10 MB default

    # Token/auth settings
    token_refresh_buffer_seconds: int = 60  # Refresh token this many seconds before expiry
    refresh_lock_ttl_seconds: int = 30  # Lock TTL for concurrent refresh prevention
    auth_wait_timeout_seconds: int = 300  # Default OAuth wait timeout

    # Encryption settings
    pbkdf2_iterations: int = 100_000  # PBKDF2 iteration count for key derivation

    # Proxy settings (for secure IP detection behind load balancers)
    # Comma-separated CIDR ranges. Empty string = use defaults (loopback + private ranges)
    # Set to "none" to disable proxy header trust entirely
    trusted_proxy_cidrs: str = ""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
