"""
Shared pytest fixtures for FHIR Gateway tests.
"""

import asyncio
import os
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fhirpy import AsyncFHIRClient

# Set test environment variables before importing app modules
# This ensures Settings validation passes during test collection
os.environ.setdefault("FHIR_GATEWAY_DEBUG", "true")
os.environ.setdefault("FHIR_GATEWAY_CORS_ALLOW_CREDENTIALS", "false")
# Ensure no Redis in tests - use in-memory storage
# Set to empty string to override any .env file value
os.environ["FHIR_GATEWAY_REDIS_URL"] = ""


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons between tests to avoid state leakage."""
    # Reset before test
    from app.auth.token_manager import reset_token_manager
    from app.config.settings import reset_settings
    reset_settings()
    reset_token_manager()
    yield
    # Reset after test
    reset_token_manager()
    reset_settings()


@pytest.fixture
def mock_fhir_client() -> AsyncMock:
    """Create a mock FHIR client."""
    client = AsyncMock(spec=AsyncFHIRClient)
    client.resources = MagicMock()
    client.resource = MagicMock()
    client.get = AsyncMock()
    client.execute = AsyncMock()
    return client


@pytest.fixture
def sample_patient() -> dict[str, Any]:
    """Sample FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": "test-patient-123",
        "meta": {
            "versionId": "1",
            "lastUpdated": "2024-01-15T10:30:00Z",
        },
        "identifier": [
            {
                "system": "http://example.org/mrn",
                "value": "MRN-12345",
            }
        ],
        "active": True,
        "name": [
            {
                "use": "official",
                "family": "Smith",
                "given": ["John", "William"],
            }
        ],
        "gender": "male",
        "birthDate": "1970-05-15",
        "address": [
            {
                "use": "home",
                "line": ["123 Main St"],
                "city": "Boston",
                "state": "MA",
                "postalCode": "02115",
            }
        ],
    }


@pytest.fixture
def sample_coverage() -> dict[str, Any]:
    """Sample FHIR Coverage resource."""
    return {
        "resourceType": "Coverage",
        "id": "test-coverage-456",
        "status": "active",
        "type": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                    "code": "HIP",
                    "display": "Health Insurance",
                }
            ]
        },
        "subscriber": {
            "reference": "Patient/test-patient-123",
        },
        "beneficiary": {
            "reference": "Patient/test-patient-123",
        },
        "payor": [
            {
                "reference": "Organization/test-payer",
                "display": "Test Insurance Company",
            }
        ],
        "class": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/coverage-class",
                            "code": "plan",
                        }
                    ]
                },
                "value": "PPO-Gold",
            }
        ],
    }


@pytest.fixture
def sample_questionnaire() -> dict[str, Any]:
    """Sample FHIR Questionnaire resource."""
    return {
        "resourceType": "Questionnaire",
        "id": "test-questionnaire",
        "url": "http://example.org/Questionnaire/test",
        "title": "Prior Authorization Questionnaire",
        "status": "active",
        "item": [
            {
                "linkId": "1",
                "text": "Patient Information",
                "type": "group",
                "item": [
                    {
                        "linkId": "1.1",
                        "text": "Patient name",
                        "type": "string",
                        "required": True,
                    },
                    {
                        "linkId": "1.2",
                        "text": "Date of birth",
                        "type": "date",
                        "required": True,
                    },
                ],
            },
            {
                "linkId": "2",
                "text": "Is this an emergency?",
                "type": "boolean",
                "required": True,
            },
            {
                "linkId": "3",
                "text": "Diagnosis",
                "type": "choice",
                "required": True,
                "answerOption": [
                    {"valueCoding": {"code": "M79.3", "display": "Limb pain"}},
                    {"valueCoding": {"code": "R10.9", "display": "Abdominal pain"}},
                ],
            },
        ],
    }


@pytest.fixture
def sample_bundle() -> dict[str, Any]:
    """Sample FHIR Bundle resource."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 2,
        "entry": [
            {
                "fullUrl": "Patient/test-patient-123",
                "resource": {
                    "resourceType": "Patient",
                    "id": "test-patient-123",
                    "name": [{"family": "Smith", "given": ["John"]}],
                },
                "search": {"mode": "match"},
            },
            {
                "fullUrl": "Patient/test-patient-456",
                "resource": {
                    "resourceType": "Patient",
                    "id": "test-patient-456",
                    "name": [{"family": "Doe", "given": ["Jane"]}],
                },
                "search": {"mode": "match"},
            },
        ],
    }


@pytest.fixture
def mock_payer_config():
    """Mock payer configuration."""
    return {
        "id": "test-payer",
        "name": "Test Payer",
        "display_name": "Test Insurance Co",
        "type": "payer",
        "fhir_base_url": "https://fhir.testpayer.com/r4",
        "oauth": {
            "authorize_url": "https://auth.testpayer.com/authorize",
            "token_url": "https://auth.testpayer.com/token",
            "client_id": "test-client",
            "scopes": ["openid", "fhirUser", "patient/*.read"],
        },
        "capabilities": {
            "patient_access": True,
            "provider_directory": True,
            "crd": True,
            "dtr": True,
        },
    }


@pytest.fixture
def mock_token():
    """Mock OAuth token."""
    return MagicMock(
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        token_type="Bearer",
        expires_in=3600,
        scope="openid fhirUser patient/*.read",
        is_expired=False,
    )
