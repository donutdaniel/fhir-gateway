.PHONY: install dev test lint format docker docker-up docker-down clean help

# Default target
help:
	@echo "FHIR Gateway - Available commands:"
	@echo ""
	@echo "  make install     Install dependencies"
	@echo "  make dev         Run development server with auto-reload"
	@echo "  make test        Run tests"
	@echo "  make test-cov    Run tests with coverage report"
	@echo "  make lint        Run linter"
	@echo "  make format      Format code"
	@echo "  make docker      Build Docker image"
	@echo "  make docker-up   Start full stack with docker compose"
	@echo "  make docker-down Stop docker compose stack"
	@echo "  make clean       Remove build artifacts"
	@echo ""

# Install dependencies
install:
	uv sync

# Run development server
dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run MCP server
mcp:
	uv run fhir-gateway-mcp

# Run tests
test:
	uv run pytest -q

# Run tests with coverage
test-cov:
	uv run pytest --cov=app --cov-report=term-missing --cov-report=html

# Run linter
lint:
	uv run ruff check .

# Format code
format:
	uv run ruff format .
	uv run ruff check --fix .

# Build Docker image
docker:
	docker build -t fhir-gateway .

# Start full stack
docker-up:
	docker compose up -d

# Stop full stack
docker-down:
	docker compose down

# View logs
docker-logs:
	docker compose logs -f fhir-gateway

# Clean build artifacts
clean:
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	rm -rf htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
