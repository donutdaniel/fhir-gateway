# Build stage
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY app ./app

ENV VIRTUAL_ENV=/opt/venv
RUN uv venv $VIRTUAL_ENV && uv sync --frozen --no-dev

# Runtime stage
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FHIR_GATEWAY_HOST=0.0.0.0 \
    FHIR_GATEWAY_PORT=8000 \
    FHIR_GATEWAY_LOG_LEVEL=INFO

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

RUN useradd -m -u 10001 appuser
USER 10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
