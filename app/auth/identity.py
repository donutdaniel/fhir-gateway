"""
User identity extraction from OAuth tokens.

Provides JWT id_token decoding and user identity extraction for
audit logging and access control.
"""

import base64
import json
from dataclasses import dataclass
from typing import Any

from app.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UserIdentity:
    """
    User identity extracted from OAuth tokens.

    Attributes:
        sub: OIDC subject claim (unique user identifier)
        fhir_user: SMART fhirUser claim (e.g., "Practitioner/123")
        patient_id: SMART patient context from launch
        display_name: Human-readable name from profile claims
    """

    sub: str
    fhir_user: str | None = None
    patient_id: str | None = None
    display_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize identity to dictionary."""
        return {
            "sub": self.sub,
            "fhir_user": self.fhir_user,
            "patient_id": self.patient_id,
            "display_name": self.display_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserIdentity":
        """Deserialize identity from dictionary."""
        return cls(
            sub=data["sub"],
            fhir_user=data.get("fhir_user"),
            patient_id=data.get("patient_id"),
            display_name=data.get("display_name"),
        )

    @property
    def user_id(self) -> str:
        """
        Get the primary user identifier for audit logging.

        Returns fhir_user if available (more meaningful), otherwise sub.
        """
        return self.fhir_user or self.sub


def decode_id_token(id_token: str) -> dict[str, Any]:
    """
    Decode a JWT id_token without signature verification.

    We skip signature verification because:
    1. The token was received directly from the authorization server via HTTPS
    2. We're only extracting claims for audit/display purposes, not for authorization
    3. The access_token (which we use for API calls) is validated by the FHIR server

    Args:
        id_token: JWT id_token string

    Returns:
        Dictionary of claims from the token payload

    Raises:
        ValueError: If token format is invalid or cannot be decoded
    """
    try:
        # JWT format: header.payload.signature
        parts = id_token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format: expected 3 parts")

        # Decode payload (middle part)
        payload = parts[1]

        # Add padding if needed (JWT base64url encoding omits padding)
        padding_needed = 4 - (len(payload) % 4)
        if padding_needed != 4:
            payload += "=" * padding_needed

        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)

        return claims

    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to decode id_token: {e}") from e
    except Exception as e:
        raise ValueError(f"Unexpected error decoding id_token: {e}") from e


def extract_user_identity(
    token_response: dict[str, Any],
    id_token_claims: dict[str, Any] | None = None,
) -> UserIdentity | None:
    """
    Extract user identity from OAuth token response.

    Extracts identity information from:
    1. id_token claims (if present and decoded)
    2. Token response fields (patient, fhirUser)

    Args:
        token_response: Raw token endpoint response dict
        id_token_claims: Pre-decoded id_token claims (optional)

    Returns:
        UserIdentity if sub claim is available, None otherwise
    """
    claims = id_token_claims or {}

    # Try to decode id_token if claims not provided
    if not claims and token_response.get("id_token"):
        try:
            claims = decode_id_token(token_response["id_token"])
        except ValueError as e:
            logger.warning("Failed to decode id_token for identity extraction", error=str(e))
            claims = {}

    # Sub claim is required
    sub = claims.get("sub")
    if not sub:
        logger.debug("No sub claim in token response, cannot extract identity")
        return None

    # Extract fhirUser from claims or token response
    fhir_user = claims.get("fhirUser") or token_response.get("fhirUser")

    # Extract patient context from claims or token response
    patient_id = claims.get("patient") or token_response.get("patient")

    # Build display name from profile claims
    display_name = _build_display_name(claims)

    identity = UserIdentity(
        sub=sub,
        fhir_user=fhir_user,
        patient_id=patient_id,
        display_name=display_name,
    )

    logger.debug(
        "Extracted user identity",
        sub=sub[:8] + "..." if len(sub) > 8 else sub,
        fhir_user=fhir_user,
        has_patient_context=patient_id is not None,
    )

    return identity


def _build_display_name(claims: dict[str, Any]) -> str | None:
    """
    Build display name from OIDC profile claims.

    Tries in order:
    1. name claim
    2. given_name + family_name
    3. preferred_username
    4. email
    """
    if claims.get("name"):
        return claims["name"]

    given = claims.get("given_name", "")
    family = claims.get("family_name", "")
    if given or family:
        return f"{given} {family}".strip()

    if claims.get("preferred_username"):
        return claims["preferred_username"]

    if claims.get("email"):
        return claims["email"]

    return None
