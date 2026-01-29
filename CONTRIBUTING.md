# Contributing to FHIR Gateway

Thank you for your interest in contributing!

## Development Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd fhir-gateway
   ```

2. Install dependencies:
   ```bash
   uv sync --all-extras
   ```

3. Run the development server:
   ```bash
   make dev
   ```

## Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific tests
uv run pytest tests/unit/test_oauth.py -v
```

## Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check for issues
make lint

# Auto-format code
make format
```

## Docker Development

Start the full development stack (Redis, HAPI FHIR, Keycloak):

```bash
make docker-up

# View logs
make docker-logs

# Stop
make docker-down
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Ensure tests pass: `make test`
4. Ensure linting passes: `make lint`
5. Submit a pull request

## Adding a New Payer

1. Create a JSON config file in `app/platforms/{payer_id}.json`
2. Include at minimum:
   - `id`: Unique identifier
   - `name`: Display name
   - `fhir_base_url`: FHIR server URL
   - `oauth`: OAuth configuration (if applicable)

See existing payer configs for examples.

## Questions?

Open an issue for questions or discussions.
