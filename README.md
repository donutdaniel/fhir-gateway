# FHIR Gateway

A unified API gateway for healthcare data across 60+ payers and EHR systems. REST API with MCP support for AI agents.

## Why FHIR Gateway?

**The Problem**: Healthcare data is fragmented. Your medical records, claims, and coverage information are scattered across dozens of different systems—each payer (Aetna, Cigna, UnitedHealthcare) and EHR (Epic, Cerner) has its own FHIR API with different endpoints, authentication flows, and quirks.

**The Solution**: FHIR Gateway provides a single REST API that handles all of this complexity. Connect to any supported platform through one unified interface. Users authorize access via OAuth, and the gateway handles routing, token management, and refresh automatically.

For AI applications, the gateway also exposes an MCP (Model Context Protocol) interface so LLMs can access healthcare data directly.

### Demos

- [Epic MyChart integration demo](assets/epic-patient-demo.mp4) - Patient OAuth flow and FHIR data retrieval
- [SmartHealthIT clinician demo](assets/smarthealthit-clinician-demo.mp4) - Clinician access with SMART on FHIR

### How It Works

```
┌─────────────┐                               ┌─────────────────┐
│  Your App   │ ─── REST ───┐                 │  Aetna, Cigna,  │
└─────────────┘             │                 │  Epic, Cerner,  │
                            ▼                 │  UHC, Humana,   │
                   ┌──────────────────┐       │  60+ systems    │
                   │   FHIR Gateway   │ ───── └─────────────────┘
                   └──────────────────┘
                            ▲
┌─────────────┐             │                 ┌─────────────────┐
│  AI Agent   │ ─── MCP ────┘                 │      User       │
│  (Claude)   │                               │  (authorizes    │
└─────────────┘                               │   via OAuth)    │
                                              └─────────────────┘
```

**For apps and services (REST API):**
1. Your app calls the gateway's REST API with a platform ID
2. If user isn't authenticated, redirect them to OAuth
3. After auth, make FHIR requests through the gateway
4. Gateway handles routing, token refresh, and platform quirks

**For AI agents (MCP):**
1. AI agent requests health data (e.g., "get my Aetna claims")
2. Gateway checks auth status, provides OAuth link if needed
3. User clicks link, authorizes in browser
4. Agent calls `wait_for_auth`, then fetches data

### Who Is This For?

- **Patients** who want AI assistants to help manage their health data across multiple providers
- **Healthcare workers** using AI tools that need access to clinical systems
- **Developers** building AI-powered healthcare applications

### Key Benefits

| Benefit | Description |
|---------|-------------|
| **One integration** | Connect to 60+ payers/EHRs through a single API |
| **User-controlled** | Users authorize each platform via OAuth—they control their own data |
| **Two interfaces** | REST API for apps and services, MCP for AI agents |
| **Production-ready** | Token encryption, auto-refresh, rate limiting, audit logging |

## Technical Overview

FHIR Gateway provides two interfaces for accessing multiple FHIR servers (payers, EHRs, etc.):

**REST API** - Full FHIR operations (search, read, create, update, delete) via HTTP
**MCP Server** - Same capabilities exposed as tools for AI agents

Both interfaces share:
- **Multi-platform routing**: Route operations to platform-specific endpoints
- **OAuth 2.0 with PKCE**: Secure authentication flow for each platform
- **Session management**: Cookie-based sessions with secure token storage
- **Production-ready security**: Encryption at rest, audit logging, rate limiting, Redis support

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd fhir-gateway

# Install with uv
uv sync

# Or install with pip
pip install -e .
```

### Running the Server

```bash
# Start the server
fhir-gateway

# Or with uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Development mode with auto-reload
uvicorn app.main:app --reload
```

The server provides both REST API and MCP on the same port:
- REST API: http://localhost:8000
- MCP: http://localhost:8000/mcp (streamable-http transport)

### Docker

The easiest way to run the full stack (with Redis, HAPI FHIR server, and Keycloak for OAuth testing):

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f fhir-gateway

# Stop all services
docker compose down
```

This starts:
- **fhir-gateway** on http://localhost:8000
- **HAPI FHIR** server on http://localhost:8080/fhir
- **Keycloak** OAuth server on http://localhost:8180 (admin/admin)
- **Redis** for token storage on localhost:6379

Test user credentials for Keycloak: `testuser` / `password`

To build and run just the gateway:

```bash
# Build the image
docker build -t fhir-gateway .

# Run with environment variables
docker run -p 8000:8000 \
  -e FHIR_GATEWAY_SESSION_SECRET=your-secret \
  fhir-gateway
```

### Configuration

Environment variables (prefix: `FHIR_GATEWAY_`):

| Variable | Description | Default |
|----------|-------------|---------|
| `FHIR_GATEWAY_HOST` | Server host | `0.0.0.0` |
| `FHIR_GATEWAY_PORT` | Server port | `8000` |
| `FHIR_GATEWAY_LOG_LEVEL` | Log level (DEBUG, INFO, WARN, ERROR) | `INFO` |
| `FHIR_GATEWAY_LOG_JSON` | JSON log format | `true` |
| `FHIR_GATEWAY_DEBUG` | Debug mode with auto-reload | `false` |
| `FHIR_GATEWAY_SESSION_SECRET` | Session signing secret | (change in production) |
| `FHIR_GATEWAY_OAUTH_REDIRECT_URI` | OAuth callback URL | `http://localhost:8000/auth/callback` |
| `FHIR_GATEWAY_REDIS_URL` | Redis URL for token storage | (optional, in-memory fallback) |
| `FHIR_GATEWAY_REQUIRE_REDIS_TLS` | Require `rediss://` scheme | `false` |
| `FHIR_GATEWAY_MASTER_KEY` | Master key for encrypting session secrets at rest | (optional) |

Platform-specific OAuth credentials:
```bash
FHIR_GATEWAY_PLATFORM_AETNA_CLIENT_ID=your-client-id
FHIR_GATEWAY_PLATFORM_AETNA_CLIENT_SECRET=your-client-secret
```

## API Endpoints

### Health Check

```bash
GET /health
```

### Platform Information

```bash
# List all platforms
GET /api/platforms

# Get platform details
GET /api/platforms/{platform_id}
```

### FHIR Operations

```bash
# CapabilityStatement
GET /api/fhir/{platform_id}/metadata

# Search
GET /api/fhir/{platform_id}/{resource_type}?{search_params}

# Read
GET /api/fhir/{platform_id}/{resource_type}/{id}

# Operations (e.g., $everything)
GET /api/fhir/{platform_id}/{resource_type}/{id}/$operation

# Create
POST /api/fhir/{platform_id}/{resource_type}

# Update
PUT /api/fhir/{platform_id}/{resource_type}/{id}

# Delete
DELETE /api/fhir/{platform_id}/{resource_type}/{id}
```

### Authentication

```bash
# Start OAuth flow
GET /auth/{platform_id}/login

# OAuth callback (handled automatically)
GET /auth/callback/{platform_id}

# Check auth status
GET /auth/status

# Wait for auth to complete (for programmatic use)
GET /auth/{platform_id}/wait

# Logout
POST /auth/{platform_id}/logout
```

## MCP Integration

The gateway includes an MCP (Model Context Protocol) server for AI agents. MCP is mounted at `/mcp` on the same server as the REST API.

> **Note**: The gateway uses streamable-http transport only (no stdio). This is required because OAuth callbacks need the HTTP server running to receive authorization codes.

### Configuring MCP Clients

1. Start the gateway server:
```bash
fhir-gateway
```

2. Configure your MCP client to connect:

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "fhir-gateway": {
      "url": "http://localhost:8000/mcp/"
    }
  }
}
```

**Claude Code** (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "fhir-gateway": {
      "url": "http://localhost:8000/mcp/"
    }
  }
}
```

3. Restart your MCP client to apply the configuration.

### MCP Tools

**FHIR Tools:**
- `get_capabilities` - Fetch FHIR server CapabilityStatement
- `search` - Search for FHIR resources
- `read` - Read a specific resource (with optional operations)
- `create` - Create a new resource
- `update` - Update an existing resource
- `delete` - Delete a resource

**Auth Tools:**
- `start_auth` - Initiate OAuth flow (returns link for user to click)
- `complete_auth` - Exchange code for tokens
- `get_auth_status` - Check authentication status
- `revoke_auth` - Revoke authentication
- `wait_for_auth` - Block until OAuth completes

### MCP Resources

- `fhir://platforms` - List of available platforms
- `fhir://platform/{platform_id}` - Detailed platform information

### MCP Prompts

- `check_prior_auth` - Prior authorization workflow
- `patient_summary` - Patient data retrieval
- `discover_capabilities` - FHIR capability discovery

### Example: AI Agent Workflow

```
User: "Can you get my recent lab results from Epic?"

AI Agent:
1. Calls get_auth_status(platform_id="epic")
   → Not authenticated

2. Calls start_auth(platform_id="epic")
   → Returns OAuth URL: "https://fhir-gateway.example/auth/epic/login?session=abc123"

3. Tells user: "Please click this link to authorize access to your Epic account: [link]"

4. Calls wait_for_auth(platform_id="epic")
   → Blocks until user completes OAuth

5. Calls search(platform_id="epic", resource_type="Observation", params={"category": "laboratory"})
   → Returns lab results

6. Summarizes results for user
```

## Examples

### Search for Patients

```bash
# Search for patients named Smith
curl http://localhost:8000/api/fhir/smarthealthit-sandbox/Patient?family=Smith

# With authorization
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/fhir/aetna/Patient?family=Smith
```

### Patient $everything

```bash
curl http://localhost:8000/api/fhir/smarthealthit-sandbox/Patient/123/\$everything
```

### OAuth Flow

```bash
# 1. Start OAuth flow (redirects to platform)
open http://localhost:8000/auth/smarthealthit-sandbox/login

# 2. After callback, check status
curl http://localhost:8000/auth/status

# 3. Use token for FHIR requests (automatically handled via session cookie)
```

## Security Features

### Encryption at Rest

When `FHIR_GATEWAY_MASTER_KEY` is set, all session tokens are encrypted before storage using:
- PBKDF2-derived Fernet keys (100k iterations)
- Per-session unique encryption keys
- Backward compatible with unencrypted sessions

### Redis Storage

For production deployments, use Redis for token storage:
```bash
FHIR_GATEWAY_REDIS_URL=rediss://localhost:6379/0
FHIR_GATEWAY_REQUIRE_REDIS_TLS=true
```

Benefits:
- Persistent sessions across restarts
- Distributed deployments
- Automatic session cleanup

### Audit Logging

Security-relevant events are logged via the `fhir.audit` logger:
- Authentication events (start, success, failure, revoke)
- Token operations (refresh, expiry)
- Resource access (read, search, create, update, delete)
- Session lifecycle (create, destroy, cleanup)
- Security events (invalid state, invalid token)

### Input Validation

All inputs are validated before processing:
- Resource types: `^[A-Z][A-Za-z]+$`
- Resource IDs: `^[A-Za-z0-9\-\.]{1,64}$`
- Platform IDs: validated against registered platforms
- Operations: allowlist of supported FHIR operations

### Security Headers

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

## Project Structure

```
fhir-gateway/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, entry point
│   ├── audit.py             # Audit logging
│   ├── validation.py        # Input validation
│   ├── config/
│   │   ├── settings.py      # Pydantic settings
│   │   ├── platform.py      # Platform configuration loader
│   │   ├── defaults.py      # Default values
│   │   └── logging.py       # Structured logging
│   ├── auth/
│   │   ├── secure_token_store.py  # Encrypted storage
│   │   └── token_manager.py       # Session management
│   ├── routers/
│   │   ├── fhir.py          # FHIR REST endpoints
│   │   ├── auth.py          # OAuth endpoints
│   │   ├── platforms.py     # Platform info endpoints
│   │   └── health.py        # Health check
│   ├── services/
│   │   ├── fhir_client.py   # FHIR client factory
│   │   └── oauth.py         # OAuth service
│   ├── adapters/
│   │   ├── base.py          # Base adapter
│   │   ├── registry.py      # Adapter registry
│   │   └── generic.py       # Generic platform adapter
│   ├── models/
│   │   ├── platform.py      # Platform models
│   │   ├── fhir.py          # FHIR models
│   │   └── auth.py          # Auth models
│   ├── middleware/
│   │   └── security.py      # Security headers
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── server.py        # MCP server with tools
│   └── platforms/           # Platform JSON configs
│       ├── aetna.json
│       ├── cigna.json
│       └── ...
├── tests/
├── pyproject.toml
└── README.md
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=app

# Format code
ruff format .

# Lint
ruff check .
```

## License

MIT
