"""
Signed auth handles for MCP session correlation.

Provides secure, opaque tokens that allow MCP clients to correlate
tool calls without exposing raw session IDs. This prevents session
enumeration attacks while supporting clients with unstable transport sessions.

The handle contains:
- session_id: The internal session identifier
- platform_id: The platform this auth is for
- timestamp: When the handle was issued
- signature: HMAC-SHA256 to prevent tampering
"""

import base64
import hashlib
import hmac
import json
import time

from app.config.settings import get_settings

# Handle validity period (24 hours)
HANDLE_TTL_SECONDS = 86400


def _get_signing_key() -> bytes:
    """Get the signing key from master key."""
    settings = get_settings()
    if not settings.master_key:
        raise ValueError("Master key not configured")
    # Derive a signing key from master key
    return hashlib.sha256(f"auth_handle:{settings.master_key}".encode()).digest()


def create_auth_handle(session_id: str, platform_id: str) -> str:
    """
    Create a signed auth handle for session correlation.

    Args:
        session_id: The internal session ID
        platform_id: The platform this auth is for

    Returns:
        Base64-encoded signed handle
    """
    payload = {
        "sid": session_id,
        "pid": platform_id,
        "ts": int(time.time()),
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_bytes = payload_json.encode()

    # Sign the payload
    key = _get_signing_key()
    signature = hmac.new(key, payload_bytes, hashlib.sha256).digest()

    # Combine payload + signature
    combined = payload_bytes + b"." + signature
    return base64.urlsafe_b64encode(combined).decode()


def verify_auth_handle(handle: str, platform_id: str | None = None) -> str | None:
    """
    Verify an auth handle and extract the session ID.

    Args:
        handle: The auth handle to verify
        platform_id: If provided, verify the handle matches this platform

    Returns:
        The session ID if valid, None if invalid or expired
    """
    try:
        # Decode
        combined = base64.urlsafe_b64decode(handle.encode())

        # Split payload and signature
        parts = combined.rsplit(b".", 1)
        if len(parts) != 2:
            return None

        payload_bytes, signature = parts

        # Verify signature
        key = _get_signing_key()
        expected_sig = hmac.new(key, payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Parse payload
        payload = json.loads(payload_bytes.decode())

        # Check expiry
        ts = payload.get("ts", 0)
        if time.time() - ts > HANDLE_TTL_SECONDS:
            return None

        # Verify platform if provided
        if platform_id and payload.get("pid") != platform_id:
            return None

        return payload.get("sid")

    except Exception:
        return None
