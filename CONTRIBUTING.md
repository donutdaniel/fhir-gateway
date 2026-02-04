# Contributing

The main way to contribute is by adding new platforms. There are hundreds of payers and EHRs with FHIR APIs—help us expand coverage.

## Adding a Platform

1. Create `app/platforms/{platform_id}.json`:

```json
{
  "id": "platform-id",
  "name": "Full Platform Name",
  "display_name": "Display Name",
  "type": "payer|ehr|sandbox",
  "fhir_base_url": "https://api.platform.com/fhir/r4",
  "developer_portal": "https://developer.platform.com",
  "oauth": {
    "authorize_url": "https://auth.platform.com/authorize",
    "token_url": "https://auth.platform.com/token",
    "scopes": ["launch/patient", "patient/*.read"]
  }
}
```

2. Submit a PR with the new platform file.

That's it—the platform will be auto-registered on restart.

## Finding Platform Information

Most platforms publish their FHIR endpoints in one of these places:

- **Developer portal** - Search for "{platform name} FHIR API" or "{platform name} developer portal"
- **CMS Interoperability Rule** - Payers are required to publish patient access APIs
- **ONC CHPL** - EHRs certified for 21st Century Cures list their FHIR endpoints

## What We Need

If you have access to a platform not listed in [docs/PLATFORMS.md](docs/PLATFORMS.md):

1. **FHIR base URL** - The endpoint for FHIR requests
2. **OAuth URLs** - Authorization and token endpoints
3. **Developer portal link** - Where to register for API access
4. **Scopes** - Required OAuth scopes (if known)

Even partial information helps—submit what you have and note what's missing.

## Testing Your Platform

```bash
# Start the server
fhir-gateway

# Test the metadata endpoint (doesn't require auth)
curl http://localhost:8000/api/fhir/{platform_id}/metadata

# Test OAuth flow
open http://localhost:8000/auth/{platform_id}/login
```

## Code Contributions

For code changes:

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Format and lint
ruff format .
ruff check .
```
