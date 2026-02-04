# Security

FHIR Gateway implements multiple security layers for production deployments.

## Encryption at Rest

When `FHIR_GATEWAY_MASTER_KEY` is set, all session tokens are encrypted before storage using:
- PBKDF2-derived Fernet keys (100k iterations)
- Per-session unique encryption keys
- Backward compatible with unencrypted sessions

## Redis Storage

For production deployments, use Redis for token storage:
```bash
FHIR_GATEWAY_REDIS_URL=rediss://localhost:6379/0
FHIR_GATEWAY_REQUIRE_REDIS_TLS=true
```

Benefits:
- Persistent sessions across restarts
- Distributed deployments
- Automatic session cleanup

## Audit Logging

Security-relevant events are logged via the `fhir.audit` logger:
- Authentication events (start, success, failure, revoke)
- Token operations (refresh, expiry)
- Resource access (read, search, create, update, delete)
- Session lifecycle (create, destroy, cleanup)
- Security events (invalid state, invalid token)

## Input Validation

All inputs are validated before processing:
- Resource types: `^[A-Z][A-Za-z]+$`
- Resource IDs: `^[A-Za-z0-9\-\.]{1,64}$`
- Platform IDs: validated against registered platforms
- Operations: allowlist of supported FHIR operations

## Security Headers

Response headers include:
- `Content-Security-Policy`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security`

## Session Model

This gateway uses session-based authentication rather than user accounts:

- **Sessions are per-device**: OAuth tokens are tied to a session and cannot be transferred between devices
- **Automatic token refresh**: Tokens are refreshed automatically before expiration
- **Session isolation**: Each user's tokens are isolated from other users
- **Logout support**: Users can revoke tokens via `POST /auth/{platform_id}/logout`

This model is designed for the hosted MCP use case where users interact through AI agents and authorize access on-demand.

## Auth Handles (MCP Session Correlation)

MCP tools use signed auth handles instead of raw session IDs:

- **Opaque tokens**: Auth handles are HMAC-SHA256 signed, preventing session enumeration attacks
- **Platform-scoped**: Each handle is bound to a specific platform
- **Time-limited**: Handles expire after 24 hours
- **Tamper-proof**: Signature verification prevents forged handles

The handle contains the session ID, platform ID, and timestamp, but is cryptographically signed so clients cannot forge or modify them. This allows MCP clients with unstable transport sessions to correlate tool calls without exposing internal session identifiers.
