"""
Application constants.

These values are intentionally not configurable via environment variables.
"""

# Session
SESSION_COOKIE_NAME = "fhir_gateway_session"
SESSION_TTL_SECONDS = 3600  # 1 hour (also in secure_token_store.py)

# Rate limiting
RATE_LIMIT_MAX_REQUESTS = 100
RATE_LIMIT_WINDOW_SECONDS = 60
CALLBACK_RATE_LIMIT_MAX_REQUESTS = 20
CALLBACK_RATE_LIMIT_WINDOW_SECONDS = 60

# Request limits
REQUEST_TIMEOUT_SECONDS = 30
MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024  # 10 MB

# Token/auth
TOKEN_REFRESH_BUFFER_SECONDS = 60  # Refresh this many seconds before expiry
REFRESH_LOCK_TTL_SECONDS = 30  # Distributed lock TTL
AUTH_WAIT_TIMEOUT_SECONDS = 300  # OAuth wait timeout

# Encryption
PBKDF2_ITERATIONS = 100_000
