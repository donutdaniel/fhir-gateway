# FHIR Gateway

A unified API gateway for healthcare data across 60+ payers and EHR systems. REST API with MCP support for AI agents.

## Why FHIR Gateway?

**The Problem**: Healthcare data is fragmented. Your medical records, claims, and coverage information are scattered across dozens of different systems—each payer (Aetna, Cigna, UnitedHealthcare) and EHR (Epic, Cerner) has its own FHIR API with different endpoints, authentication flows, and quirks.

**The Solution**: FHIR Gateway provides a single REST API that handles all of this complexity. Connect to any supported platform through one unified interface. Users authorize access via OAuth, and the gateway handles routing, token management, and refresh automatically.

For AI applications, the gateway also exposes an MCP (Model Context Protocol) interface so LLMs can access healthcare data directly.

### Demos

**Epic MyChart** - Patient OAuth flow and FHIR data retrieval

<video src="https://github.com/user-attachments/assets/d7afda80-d04f-4f27-9c9f-e1ab0c652f49" controls autoplay muted loop width="600"></video>

**SmartHealthIT Clinician** - Clinician access with SMART on FHIR

<video src="https://github.com/user-attachments/assets/d3258a29-7c48-4db9-ad12-70a7dbc663ba" controls autoplay muted loop width="600"></video>

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

## Quick Start

```bash
# Clone and install
git clone git@github.com:donutdaniel/fhir-gateway.git
cd fhir-gateway
uv sync

# Run the server
fhir-gateway
```

The server provides both REST API and MCP on the same port:
- REST API: http://localhost:8000
- MCP: http://localhost:8000/mcp

<details>
<summary><strong>Docker</strong></summary>

Run the full stack with Redis, HAPI FHIR, and Keycloak:

```bash
docker compose up -d
```

This starts:
- **fhir-gateway** on http://localhost:8000
- **HAPI FHIR** server on http://localhost:8080/fhir
- **Keycloak** OAuth server on http://localhost:8180 (admin/admin)
- **Redis** for token storage

Test credentials: `testuser` / `password`

</details>

<details>
<summary><strong>Configuration</strong></summary>

Environment variables (prefix: `FHIR_GATEWAY_`):

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `REDIS_URL` | Redis URL for token storage | (optional) |
| `MASTER_KEY` | Encryption key for tokens at rest | (optional) |

Platform-specific OAuth credentials:
```bash
FHIR_GATEWAY_PLATFORM_AETNA_CLIENT_ID=your-client-id
FHIR_GATEWAY_PLATFORM_AETNA_CLIENT_SECRET=your-client-secret
```

</details>

## API Reference

<details>
<summary><strong>FHIR Operations</strong></summary>

```bash
GET  /api/fhir/{platform_id}/metadata              # CapabilityStatement
GET  /api/fhir/{platform_id}/{resource_type}       # Search
GET  /api/fhir/{platform_id}/{resource_type}/{id}  # Read
POST /api/fhir/{platform_id}/{resource_type}       # Create
PUT  /api/fhir/{platform_id}/{resource_type}/{id}  # Update
DELETE /api/fhir/{platform_id}/{resource_type}/{id} # Delete
```

Example:
```bash
curl http://localhost:8000/api/fhir/smarthealthit-sandbox-patient/Patient?family=Smith
```

</details>

<details>
<summary><strong>Authentication</strong></summary>

```bash
GET  /auth/{platform_id}/login   # Start OAuth flow
GET  /oauth/callback             # OAuth callback (automatic)
GET  /auth/status                # Check auth status
GET  /auth/{platform_id}/wait    # Wait for auth completion
POST /auth/{platform_id}/logout  # Logout
```

Example flow:
```bash
# 1. Start OAuth (opens browser)
open http://localhost:8000/auth/smarthealthit-sandbox-patient/login

# 2. After auth, make requests (session cookie handles token)
curl http://localhost:8000/api/fhir/smarthealthit-sandbox-patient/Patient
```

</details>

## MCP Integration

> **Note**: The gateway uses streamable-http transport (not stdio) because OAuth callbacks require an HTTP server to receive browser redirects. Run `fhir-gateway` before starting your MCP client.

Configure your MCP client to connect to the gateway:

<details open>
<summary><strong>Claude Desktop</strong></summary>

`~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "fhir-gateway": {
      "url": "http://localhost:8000/mcp/"
    }
  }
}
```

</details>

<details>
<summary><strong>Claude Code</strong></summary>

`~/.claude/settings.json`:
```json
{
  "mcpServers": {
    "fhir-gateway": {
      "url": "http://localhost:8000/mcp/"
    }
  }
}
```

</details>

<details>
<summary><strong>Cursor</strong></summary>

`~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "fhir-gateway": {
      "url": "http://localhost:8000/mcp/"
    }
  }
}
```

</details>

<details>
<summary><strong>Windsurf</strong></summary>

`~/.codeium/windsurf/mcp_config.json`:
```json
{
  "mcpServers": {
    "fhir-gateway": {
      "url": "http://localhost:8000/mcp/"
    }
  }
}
```

</details>

<details>
<summary><strong>Cline (VS Code)</strong></summary>

Open Cline settings → MCP Servers → Add:
```json
{
  "fhir-gateway": {
    "url": "http://localhost:8000/mcp/"
  }
}
```

</details>

<details>
<summary><strong>MCP Tools</strong></summary>

**FHIR**: `list_platforms`, `get_capabilities`, `search`, `read`, `create`, `update`, `delete`

**Auth**: `start_auth`, `wait_for_auth`, `get_auth_status`, `revoke_auth`

**Coverage**: `check_prior_auth`, `get_questionnaire_package`, `get_policy_rules`

**Example workflow**:
```
User: "Get my lab results from Epic"

Agent:
1. get_auth_status(platform_id="epic") → Not authenticated
2. start_auth(platform_id="epic") → Returns OAuth URL
3. Tell user to click link
4. wait_for_auth(platform_id="epic") → Blocks until complete
5. search(platform_id="epic", resource_type="Observation", params={"category": "laboratory"})
```

</details>

## Documentation

- [Supported Platforms](docs/PLATFORMS.md) - 64 payers, EHRs, and sandboxes
- [Security](docs/SECURITY.md) - Encryption, audit logging, session model
- [Contributing](CONTRIBUTING.md) - Adding new platforms

> **Note**: Most platforms require registering for a developer account on each platform's portal. This process is manual and can take days to weeks for approval. Only SmartHealthIT and HAPI sandboxes work without additional setup.

## License

[MIT](LICENSE)
