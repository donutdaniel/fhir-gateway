# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

fhir-gateway is a standalone REST API gateway for FHIR operations with multi-platform routing. It provides both a REST API (FastAPI) and an MCP (Model Context Protocol) wrapper for AI tool integration.

## Build and Development Commands

```bash
# Install dependencies (using uv)
uv sync

# Install with dev dependencies
uv sync --all-extras

# Run the server (REST API + MCP)
fhir-gateway

# Or using uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Development mode with auto-reload
uvicorn app.main:app --reload

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=app

# Format code
ruff format .

# Lint
ruff check .
```

## Architecture

### Multi-Platform Routing

This gateway routes FHIR operations to platform-specific endpoints. Every operation requires:
- `platform_id` (required) - Identifies which platform's FHIR endpoint to use
- `access_token` (optional) - OAuth token for authenticated requests (auto-fetched from session if available)

### Session-Scoped OAuth

The gateway supports session-scoped OAuth token management:
- OAuth tokens are stored per session (cookie-based), isolated from other sessions
- Tokens can be stored in-memory (development) or Redis (production)
- Tokens are automatically refreshed when expired
- Session cleanup runs every 5 minutes

### Security Features

- **Input validation**: `app/validation.py` provides `validate_resource_type()`, `validate_resource_id()`, `validate_platform_id()`, and `validate_procedure_code()`. All endpoints validate inputs before processing.
- **Encryption at rest**: `app/auth/secure_token_store.py` provides `MasterKeyEncryption` using PBKDF2-derived Fernet keys when `FHIR_GATEWAY_MASTER_KEY` is set.
- **XSS protection**: OAuth callback HTML responses use `html.escape()` and include CSP headers.
- **Audit logging**: `app/audit.py` provides `audit_log()` for security-relevant events.
- **Redis TLS enforcement**: `token_manager.py` warns on non-TLS Redis URLs and can require `rediss://` via `FHIR_GATEWAY_REQUIRE_REDIS_TLS`.

### Core Components

- **`app/main.py`**: FastAPI app entry point. Creates app, registers routers, handles startup/shutdown with session cleanup background task.

- **`app/audit.py`**: Audit logging with `AuditEvent` constants and `audit_log()` function.

- **`app/validation.py`**: Input validation for platform IDs, resource types, resource IDs, and procedure codes.

- **`app/config/`**: Configuration modules.
  - `settings.py`: Settings class with `FHIR_GATEWAY_` env prefix
  - `platform.py`: Platform configuration loaded from platforms/*.json
  - `logging.py`: Structured logging using structlog

- **`app/auth/`**: Authentication and token storage.
  - `secure_token_store.py`: `SecureTokenStore`, `SecureSession`, `InMemoryTokenStorage`, `RedisTokenStorage`, `MasterKeyEncryption`
  - `token_manager.py`: `SessionTokenManager` with auto-refresh, distributed locking, auth completion signaling

- **`app/routers/`**: API endpoints.
  - `fhir.py`: FHIR REST endpoints (metadata, search, read, create, update, delete, operations)
  - `auth.py`: OAuth endpoints (login, status, logout, wait, token)
  - `oauth.py`: OAuth callback endpoint (/oauth/callback)
  - `platforms.py`: Platform information endpoints
  - `health.py`: Health check

- **`app/services/`**: Business logic.
  - `fhir_client.py`: FHIR client factory with platform routing
  - `oauth.py`: OAuth service with PKCE support

- **`app/mcp/`**: MCP wrapper.
  - `server.py`: MCP server with tools, prompts, and resources

- **`app/adapters/`**: Platform-specific adapters.
  - `base.py`: BasePayerAdapter
  - `registry.py`: Adapter registry with pattern matching
  - `generic.py`: Generic platform adapter

- **`app/platforms/`**: Platform JSON configuration files.

### REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/platforms` | GET | List all platforms |
| `/api/platforms/{platform_id}` | GET | Get platform details |
| `/api/fhir/{platform_id}/metadata` | GET | CapabilityStatement |
| `/api/fhir/{platform_id}/{resource_type}` | GET | Search resources |
| `/api/fhir/{platform_id}/{resource_type}/{id}` | GET | Read resource |
| `/api/fhir/{platform_id}/{resource_type}/{id}/{op}` | GET | Execute operation |
| `/api/fhir/{platform_id}/{resource_type}` | POST | Create resource |
| `/api/fhir/{platform_id}/{resource_type}/{id}` | PUT | Update resource |
| `/api/fhir/{platform_id}/{resource_type}/{id}` | DELETE | Delete resource |
| `/auth/{platform_id}/login` | GET | Start OAuth flow |
| `/oauth/callback` | GET | OAuth callback |
| `/auth/status` | GET | Auth status |
| `/auth/{platform_id}/wait` | GET | Wait for auth |
| `/auth/{platform_id}/logout` | POST | Logout |

### MCP Transport

The MCP server uses **streamable-http** transport only (no stdio support). This is required because OAuth callbacks need the HTTP server running.

**Claude Desktop configuration** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "fhir-gateway": {
      "url": "http://localhost:8000/mcp",
      "transport": "streamable-http"
    }
  }
}
```

Run `fhir-gateway` separately before starting Claude Desktop.

### MCP Tools

**FHIR Tools** (all require `platform_id`):
- `get_capabilities` - Fetch CapabilityStatement
- `search` - Search for resources
- `read` - Read resource (with optional operations)
- `create` - Create resource
- `update` - Update resource
- `delete` - Delete resource

**Auth Tools**:
- `start_auth` - Initiate OAuth flow
- `complete_auth` - Exchange code for tokens
- `get_auth_status` - Get authentication status
- `revoke_auth` - Revoke authentication
- `wait_for_auth` - Block until OAuth completes

### Configuration

**Environment Variables** (prefix: `FHIR_GATEWAY_`):

| Variable | Description | Default |
|----------|-------------|---------|
| `FHIR_GATEWAY_HOST` | Server host | `0.0.0.0` |
| `FHIR_GATEWAY_PORT` | Server port | `8000` |
| `FHIR_GATEWAY_LOG_LEVEL` | Log level | `INFO` |
| `FHIR_GATEWAY_LOG_JSON` | JSON logging | `true` |
| `FHIR_GATEWAY_DEBUG` | Debug mode | `false` |
| `FHIR_GATEWAY_SESSION_MAX_AGE` | Session TTL | `3600` |
| `FHIR_GATEWAY_OAUTH_REDIRECT_URI` | OAuth callback URL | `http://localhost:8000/auth/callback` |
| `FHIR_GATEWAY_REDIS_URL` | Redis URL | (optional) |
| `FHIR_GATEWAY_REQUIRE_REDIS_TLS` | Require rediss:// | `false` |
| `FHIR_GATEWAY_MASTER_KEY` | Encryption key | (optional) |

### Test Structure

Tests use pytest with pytest-asyncio.

```
tests/
└── test_fhir.py    # API tests with TestClient
```

## Key Dependencies

- **fastapi**: REST API framework
- **uvicorn**: ASGI server
- **fhirpy**: Async FHIR client
- **aiohttp**: HTTP client
- **pydantic-settings**: Configuration
- **structlog**: Structured logging
- **redis**: Redis client (optional)
- **cryptography**: Encryption (optional)
- **mcp**: Model Context Protocol
