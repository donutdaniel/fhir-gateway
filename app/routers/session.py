"""
Shared session utilities for router endpoints.

Provides consistent session cookie handling across auth and OAuth endpoints.
"""

import ipaddress
import uuid

from fastapi import Request
from fastapi.responses import Response

from app.config.settings import get_settings
from app.constants import SESSION_COOKIE_NAME

# Default trusted proxy networks (loopback and RFC 1918 private ranges)
# These are commonly used by load balancers and reverse proxies
DEFAULT_TRUSTED_PROXIES = [
    "127.0.0.0/8",  # IPv4 loopback
    "::1/128",  # IPv6 loopback
    "10.0.0.0/8",  # Private network (Class A)
    "172.16.0.0/12",  # Private network (Class B)
    "192.168.0.0/16",  # Private network (Class C)
    "fc00::/7",  # IPv6 unique local addresses
]


def get_session_id(request: Request, create_if_missing: bool = True) -> str | None:
    """
    Get session ID from cookie.

    Args:
        request: FastAPI request
        create_if_missing: If True, create new UUID when no session cookie exists

    Returns:
        Session ID string, or None if not found and create_if_missing=False
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id and create_if_missing:
        session_id = str(uuid.uuid4())
    return session_id


def set_session_cookie(response: Response, session_id: str) -> None:
    """Set session cookie on response."""
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.session_max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


def _is_trusted_proxy(ip_str: str, trusted_cidrs: list[str]) -> bool:
    """
    Check if an IP address belongs to a trusted proxy network.

    Args:
        ip_str: IP address string to check
        trusted_cidrs: List of CIDR notation network ranges

    Returns:
        True if IP is in a trusted network, False otherwise
    """
    try:
        client_ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    for cidr in trusted_cidrs:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            if client_ip in network:
                return True
        except ValueError:
            continue

    return False


def _get_trusted_proxies() -> list[str]:
    """
    Get the list of trusted proxy CIDR ranges from settings.

    Returns:
        List of CIDR strings, or empty list if proxy trust is disabled
    """
    settings = get_settings()
    configured = settings.trusted_proxy_cidrs.strip()

    # "none" explicitly disables proxy header trust
    if configured.lower() == "none":
        return []

    # Empty string means use defaults
    if not configured:
        return DEFAULT_TRUSTED_PROXIES

    # Parse comma-separated CIDR list
    return [cidr.strip() for cidr in configured.split(",") if cidr.strip()]


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request with secure proxy header handling.

    Security: Only trusts X-Forwarded-For and X-Real-IP headers when the
    direct connection originates from a trusted proxy network. This prevents
    IP spoofing attacks where attackers forge these headers.

    Configure trusted proxies via FHIR_GATEWAY_TRUSTED_PROXY_CIDRS:
    - Empty string (default): Trust loopback and private network ranges
    - "none": Never trust proxy headers (use direct connection IP only)
    - CIDR list: "10.0.0.0/8,172.16.0.0/12" - custom trusted ranges

    Args:
        request: FastAPI request object

    Returns:
        Client IP address string
    """
    direct_ip = request.client.host if request.client else None

    # If we can't determine direct IP, return "unknown"
    if not direct_ip:
        return "unknown"

    # Get trusted proxy configuration
    trusted_proxies = _get_trusted_proxies()

    # If no trusted proxies configured, always use direct IP
    if not trusted_proxies:
        return direct_ip

    # Only trust forwarded headers if direct connection is from trusted proxy
    if not _is_trusted_proxy(direct_ip, trusted_proxies):
        return direct_ip

    # Connection is from trusted proxy - extract real client IP
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # X-Forwarded-For format: "client, proxy1, proxy2, ..."
        # First entry is the original client
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # Fallback to direct IP if no forwarded headers present
    return direct_ip
