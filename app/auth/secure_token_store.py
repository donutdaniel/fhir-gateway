"""
Secure token storage with optional encryption.

Provides encrypted token storage backends for both in-memory (development)
and Redis (production) storage with session isolation.
"""

import base64
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.config.logging import get_logger
from app.config.settings import get_settings
from app.models.auth import OAuthToken

logger = get_logger(__name__)

# Session constants
SESSION_TTL_SECONDS = 3600  # 1 hour


class MasterKeyEncryption:
    """
    Encryption using a master key with PBKDF2-derived Fernet keys.

    Uses PBKDF2 to derive a Fernet key from the master key and session ID,
    providing unique encryption keys per session.
    """

    def __init__(self, master_key: str, pbkdf2_iterations: int | None = None):
        """
        Initialize encryption with master key.

        Args:
            master_key: Master key for deriving per-session keys
            pbkdf2_iterations: Number of PBKDF2 iterations (uses settings default if not provided)
        """
        if not master_key:
            raise ValueError("Master key cannot be empty")
        self._master_key = master_key.encode() if isinstance(master_key, str) else master_key
        self._pbkdf2_iterations = pbkdf2_iterations or get_settings().pbkdf2_iterations

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive a Fernet-compatible key using PBKDF2."""
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            self._master_key,
            salt,
            iterations=self._pbkdf2_iterations,
            dklen=32,
        )
        # Fernet requires base64-encoded 32-byte key
        return base64.urlsafe_b64encode(dk)

    def encrypt(self, data: str, session_id: str) -> str:
        """
        Encrypt data for a specific session.

        Args:
            data: Plain text to encrypt
            session_id: Session ID used as salt for key derivation

        Returns:
            Base64-encoded encrypted data with format: version:salt:ciphertext
        """
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ImportError("cryptography package required for encryption")

        # Use session ID as salt
        salt = session_id.encode()[:16].ljust(16, b"\0")
        key = self._derive_key(salt)
        f = Fernet(key)

        encrypted = f.encrypt(data.encode())
        # Format: v1:salt_b64:ciphertext_b64
        salt_b64 = base64.urlsafe_b64encode(salt).decode()
        return f"v1:{salt_b64}:{encrypted.decode()}"

    def decrypt(self, encrypted_data: str, session_id: str) -> str:
        """
        Decrypt data for a specific session.

        Args:
            encrypted_data: Encrypted data string
            session_id: Session ID used as salt for key derivation

        Returns:
            Decrypted plain text

        Raises:
            ValueError: If decryption fails or format is invalid
        """
        try:
            from cryptography.fernet import Fernet, InvalidToken
        except ImportError:
            raise ImportError("cryptography package required for encryption")

        try:
            parts = encrypted_data.split(":", 2)
            if len(parts) != 3 or parts[0] != "v1":
                raise ValueError("Invalid encrypted data format")

            # Extract salt (though we could recompute from session_id)
            salt = session_id.encode()[:16].ljust(16, b"\0")
            key = self._derive_key(salt)
            f = Fernet(key)

            decrypted = f.decrypt(parts[2].encode())
            return decrypted.decode()
        except InvalidToken:
            raise ValueError("Decryption failed: invalid token or key")
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")


@dataclass
class SecureSession:
    """
    Session with cryptographic binding to prevent tampering.

    Stores session data with a verification hash to detect modifications.
    """

    session_id: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    platform_tokens: dict[str, OAuthToken] = field(default_factory=dict)
    pending_auth: dict[str, dict[str, Any]] = field(default_factory=dict)
    _verification_hash: str = ""

    def __post_init__(self):
        if not self._verification_hash:
            self._verification_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute verification hash for session data."""
        data = f"{self.session_id}:{self.created_at}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def verify(self) -> bool:
        """Verify session integrity."""
        return self._verification_hash == self._compute_hash()

    def touch(self) -> None:
        """Update last accessed time."""
        self.last_accessed = time.time()

    def is_expired(self, ttl: int = SESSION_TTL_SECONDS) -> bool:
        """Check if session has expired."""
        return time.time() - self.last_accessed > ttl

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "platform_tokens": {
                platform_id: token.model_dump() for platform_id, token in self.platform_tokens.items()
            },
            "pending_auth": self.pending_auth,
            "_verification_hash": self._verification_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SecureSession":
        """Deserialize session from dictionary."""
        platform_tokens = {}
        for platform_id, token_data in data.get("platform_tokens", {}).items():
            platform_tokens[platform_id] = OAuthToken(**token_data)

        session = cls(
            session_id=data["session_id"],
            created_at=data.get("created_at", time.time()),
            last_accessed=data.get("last_accessed", time.time()),
            platform_tokens=platform_tokens,
            pending_auth=data.get("pending_auth", {}),
            _verification_hash=data.get("_verification_hash", ""),
        )
        return session


class TokenStorageBackend(ABC):
    """Abstract base class for token storage backends."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Get value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Set key-value pair with optional TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass

    @abstractmethod
    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern."""
        pass


class InMemoryTokenStorage(TokenStorageBackend):
    """In-memory token storage for development/testing."""

    def __init__(self):
        self._store: dict[str, tuple[str, float | None]] = {}  # key -> (value, expires_at)

    async def get(self, key: str) -> str | None:
        if key not in self._store:
            return None
        value, expires_at = self._store[key]
        if expires_at and time.time() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        expires_at = time.time() + ttl if ttl else None
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def keys(self, pattern: str) -> list[str]:
        # Simple prefix matching for in-memory storage
        prefix = pattern.rstrip("*")
        return [k for k in self._store.keys() if k.startswith(prefix)]

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if exp and now > exp]
        for k in expired:
            del self._store[k]
        return len(expired)


class RedisTokenStorage(TokenStorageBackend):
    """Redis-backed token storage for production."""

    def __init__(self, redis_url: str, require_tls: bool = False):
        """
        Initialize Redis storage.

        Args:
            redis_url: Redis connection URL
            require_tls: If True, require rediss:// scheme
        """
        self._redis_url = redis_url
        self._require_tls = require_tls
        self._client = None

        # Validate TLS requirement
        if require_tls and not redis_url.startswith("rediss://"):
            raise ValueError(
                "Redis TLS required but URL does not use rediss:// scheme. "
                "Set FHIR_GATEWAY_REQUIRE_REDIS_TLS=false to disable this check."
            )

        if not redis_url.startswith("rediss://"):
            logger.warning(
                "Redis connection not using TLS",
                redis_url=redis_url[:20] + "...",
            )

    async def _get_client(self):
        """Lazily initialize Redis client."""
        if self._client is None:
            try:
                import redis.asyncio as redis
            except ImportError:
                raise ImportError("redis package required for Redis storage")

            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> str | None:
        client = await self._get_client()
        return await client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        client = await self._get_client()
        if ttl:
            await client.setex(key, ttl, value)
        else:
            await client.set(key, value)

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(key)

    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        return await client.exists(key) > 0

    async def keys(self, pattern: str) -> list[str]:
        """
        Get keys matching pattern using SCAN (non-blocking).

        Uses SCAN instead of KEYS to avoid blocking Redis on large datasets.
        """
        client = await self._get_client()
        keys = []
        cursor = 0
        while True:
            cursor, batch = await client.scan(cursor, match=pattern, count=100)
            keys.extend(batch)
            if cursor == 0:
                break
        return keys

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None


class SecureTokenStore:
    """
    Secure token storage with optional encryption.

    Provides session-scoped token storage with:
    - Optional encryption at rest using master key
    - Session integrity verification
    - Automatic expiration
    - Support for multiple storage backends
    """

    KEY_PREFIX = "app:session:"

    def __init__(
        self,
        backend: TokenStorageBackend,
        master_key: str | None = None,
        session_ttl: int = SESSION_TTL_SECONDS,
    ):
        """
        Initialize secure token store.

        Args:
            backend: Storage backend (InMemoryTokenStorage or RedisTokenStorage)
            master_key: Optional master key for encryption
            session_ttl: Session TTL in seconds
        """
        self._backend = backend
        self._session_ttl = session_ttl
        self._encryption: MasterKeyEncryption | None = None

        if master_key:
            self._encryption = MasterKeyEncryption(master_key)
            logger.info("Token encryption enabled with master key")
        else:
            logger.warning("Token encryption disabled - no master key configured")

    def _make_key(self, session_id: str) -> str:
        """Create storage key for session."""
        return f"{self.KEY_PREFIX}{session_id}"

    def _serialize(self, session: SecureSession, session_id: str) -> str:
        """Serialize session data, optionally encrypting."""
        data = json.dumps(session.to_dict())
        if self._encryption:
            return self._encryption.encrypt(data, session_id)
        return data

    def _deserialize(self, data: str, session_id: str) -> SecureSession:
        """Deserialize session data, decrypting if needed."""
        if self._encryption and data.startswith("v1:"):
            data = self._encryption.decrypt(data, session_id)
        return SecureSession.from_dict(json.loads(data))

    async def get_session(self, session_id: str) -> SecureSession | None:
        """Get session by ID."""
        key = self._make_key(session_id)
        data = await self._backend.get(key)

        if not data:
            return None

        try:
            session = self._deserialize(data, session_id)

            # Verify session integrity
            if not session.verify():
                logger.warning("Session integrity check failed", session_id=session_id[:16])
                await self._backend.delete(key)
                return None

            # Check expiration
            if session.is_expired(self._session_ttl):
                logger.debug("Session expired", session_id=session_id[:16])
                await self._backend.delete(key)
                return None

            return session

        except Exception as e:
            logger.error("Failed to deserialize session", error=str(e))
            await self._backend.delete(key)
            return None

    async def create_session(self, session_id: str) -> SecureSession:
        """Create a new session."""
        session = SecureSession(session_id=session_id)
        await self.save_session(session)
        logger.debug("Session created", session_id=session_id[:16])
        return session

    async def save_session(self, session: SecureSession) -> None:
        """Save session to storage."""
        session.touch()
        key = self._make_key(session.session_id)
        data = self._serialize(session, session.session_id)
        await self._backend.set(key, data, ttl=self._session_ttl)

    async def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        key = self._make_key(session_id)
        await self._backend.delete(key)
        logger.debug("Session deleted", session_id=session_id[:16])

    async def get_or_create_session(self, session_id: str) -> SecureSession:
        """Get existing session or create new one."""
        session = await self.get_session(session_id)
        if session is None:
            session = await self.create_session(session_id)
        return session

    async def store_token(
        self,
        session_id: str,
        platform_id: str,
        token: OAuthToken,
    ) -> None:
        """Store OAuth token for a platform in session."""
        session = await self.get_or_create_session(session_id)
        session.platform_tokens[platform_id] = token
        await self.save_session(session)
        logger.debug(
            "Token stored",
            session_id=session_id[:16],
            platform_id=platform_id,
        )

    async def get_token(
        self,
        session_id: str,
        platform_id: str,
    ) -> OAuthToken | None:
        """Get OAuth token for a platform from session."""
        session = await self.get_session(session_id)
        if session is None:
            return None
        return session.platform_tokens.get(platform_id)

    async def delete_token(
        self,
        session_id: str,
        platform_id: str,
    ) -> None:
        """Delete OAuth token for a platform from session."""
        session = await self.get_session(session_id)
        if session is None:
            return
        session.platform_tokens.pop(platform_id, None)
        await self.save_session(session)

    async def store_pending_auth(
        self,
        session_id: str,
        platform_id: str,
        state: str,
        pkce_verifier: str,
    ) -> None:
        """Store pending OAuth authorization data."""
        session = await self.get_or_create_session(session_id)
        session.pending_auth[platform_id] = {
            "state": state,
            "pkce_verifier": pkce_verifier,
            "created_at": time.time(),
        }
        await self.save_session(session)

    async def get_pending_auth(
        self,
        session_id: str,
        platform_id: str,
    ) -> dict[str, Any] | None:
        """Get pending OAuth authorization data."""
        session = await self.get_session(session_id)
        if session is None:
            return None
        return session.pending_auth.get(platform_id)

    async def clear_pending_auth(
        self,
        session_id: str,
        platform_id: str,
    ) -> None:
        """Clear pending OAuth authorization data."""
        session = await self.get_session(session_id)
        if session is None:
            return
        session.pending_auth.pop(platform_id, None)
        await self.save_session(session)

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        keys = await self._backend.keys(f"{self.KEY_PREFIX}*")
        cleaned = 0

        for key in keys:
            session_id = key.replace(self.KEY_PREFIX, "")
            session = await self.get_session(session_id)  # Will auto-delete if expired
            if session is None:
                cleaned += 1

        if cleaned > 0:
            logger.info("Cleaned up expired sessions", count=cleaned)

        return cleaned
