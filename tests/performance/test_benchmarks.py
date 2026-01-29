"""
Performance benchmarks for critical code paths.

These tests measure execution time of key operations to detect regressions.

Run with: pytest tests/performance -v
Run benchmarks only: pytest tests/performance -v -m benchmark
"""

import asyncio
import time
from unittest.mock import MagicMock

import pytest

# Mark all tests in this module as performance benchmarks
pytestmark = [pytest.mark.performance, pytest.mark.benchmark]


class TestFHIRClientPerformance:
    """Performance benchmarks for FHIR client operations."""

    @pytest.fixture
    def mock_fhir_response(self):
        """Mock FHIR Bundle response."""
        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 100,
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": f"patient-{i}",
                        "name": [{"family": "Test", "given": ["Patient"]}],
                    }
                }
                for i in range(100)
            ],
        }

    @pytest.mark.asyncio
    async def test_search_response_parsing_performance(self, mock_fhir_response):
        """Benchmark FHIR Bundle parsing with 100 entries."""
        iterations = 100
        start = time.perf_counter()

        for _ in range(iterations):
            # Simulate parsing response
            bundle = mock_fhir_response
            entries = bundle.get("entry", [])
            resources = [e.get("resource") for e in entries]
            assert len(resources) == 100

        elapsed = time.perf_counter() - start
        avg_time = elapsed / iterations

        # Should complete in under 1ms per iteration
        assert avg_time < 0.001, f"Average parsing time {avg_time:.4f}s exceeds 1ms"

    @pytest.mark.asyncio
    async def test_large_bundle_processing(self):
        """Benchmark processing of large Bundle (1000 entries)."""
        large_bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 1000,
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "id": f"obs-{i}",
                        "status": "final",
                        "code": {"coding": [{"code": "12345-6"}]},
                    }
                }
                for i in range(1000)
            ],
        }

        start = time.perf_counter()

        # Process bundle
        entries = large_bundle.get("entry", [])
        resources = [e.get("resource") for e in entries]
        resource_ids = [r.get("id") for r in resources]

        elapsed = time.perf_counter() - start

        assert len(resource_ids) == 1000
        # Should complete in under 10ms
        assert elapsed < 0.01, f"Processing time {elapsed:.4f}s exceeds 10ms"


class TestValidationPerformance:
    """Performance benchmarks for input validation."""

    def test_resource_type_validation_performance(self):
        """Benchmark resource type validation."""
        from app.validation import validate_resource_type

        valid_types = [
            "Patient",
            "Observation",
            "Condition",
            "Procedure",
            "MedicationRequest",
            "DiagnosticReport",
            "Encounter",
            "AllergyIntolerance",
            "Immunization",
            "Coverage",
        ]

        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            for resource_type in valid_types:
                validate_resource_type(resource_type)

        elapsed = time.perf_counter() - start
        total_validations = iterations * len(valid_types)
        avg_time = elapsed / total_validations

        # Should complete in under 0.01ms per validation
        assert avg_time < 0.00001, f"Average validation time {avg_time:.6f}s too slow"

    def test_resource_id_validation_performance(self):
        """Benchmark resource ID validation."""
        from app.validation import validate_resource_id

        valid_ids = [
            "123",
            "abc-def-123",
            "patient-001",
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "simple",
        ]

        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            for resource_id in valid_ids:
                validate_resource_id(resource_id)

        elapsed = time.perf_counter() - start
        total_validations = iterations * len(valid_ids)
        avg_time = elapsed / total_validations

        # Should complete in under 0.01ms per validation
        assert avg_time < 0.00001, f"Average validation time {avg_time:.6f}s too slow"


class TestTokenStoragePerformance:
    """Performance benchmarks for token storage operations."""

    @pytest.mark.asyncio
    async def test_token_storage_get_set_performance(self):
        """Benchmark token storage get/set from in-memory store."""
        from app.auth.secure_token_store import InMemoryTokenStorage

        storage = InMemoryTokenStorage()

        # Pre-populate with 100 entries
        for i in range(100):
            key = f"session:{i}:platform:{i % 10}"
            await storage.set(key, f"token-value-{i}", ttl=3600)

        iterations = 1000
        start = time.perf_counter()

        for i in range(iterations):
            key = f"session:{i % 100}:platform:{i % 10}"
            await storage.get(key)

        elapsed = time.perf_counter() - start
        avg_time = elapsed / iterations

        # Should complete in under 0.1ms per lookup
        assert avg_time < 0.0001, f"Average lookup time {avg_time:.6f}s exceeds 0.1ms"

    @pytest.mark.asyncio
    async def test_storage_keys_pattern_performance(self):
        """Benchmark key pattern matching."""
        from app.auth.secure_token_store import InMemoryTokenStorage

        storage = InMemoryTokenStorage()

        # Store tokens for 10 platforms in 10 sessions
        for session in range(10):
            for platform in range(10):
                key = f"session:{session}:platform:{platform}"
                await storage.set(key, f"token-{session}-{platform}", ttl=3600)

        iterations = 1000
        start = time.perf_counter()

        for i in range(iterations):
            # Find all keys for a session
            await storage.keys(f"session:{i % 10}:*")

        elapsed = time.perf_counter() - start
        avg_time = elapsed / iterations

        # Should complete in under 0.5ms per pattern match
        assert avg_time < 0.0005, f"Average match time {avg_time:.6f}s exceeds 0.5ms"


class TestAdapterRegistryPerformance:
    """Performance benchmarks for adapter registry lookups."""

    def test_adapter_lookup_by_id_performance(self):
        """Benchmark adapter lookup by platform ID."""
        from app.adapters.registry import PlatformAdapterRegistry

        registry = PlatformAdapterRegistry()

        # Register some adapters
        for i in range(10):
            adapter_class = MagicMock()
            registry.register(f"platform-{i}", adapter_class)

        iterations = 10000
        start = time.perf_counter()

        for i in range(iterations):
            platform_id = f"platform-{i % 10}"
            # Use _resolve_platform_id which takes a string directly
            registry._resolve_platform_id(platform_id)

        elapsed = time.perf_counter() - start
        avg_time = elapsed / iterations

        # Should complete in under 0.01ms per lookup
        assert avg_time < 0.00001, f"Average lookup time {avg_time:.6f}s too slow"

    def test_pattern_matching_performance(self):
        """Benchmark pattern matching for platform resolution."""
        from app.adapters.registry import PlatformAdapterRegistry

        registry = PlatformAdapterRegistry()

        # Register patterns
        patterns = [
            r"bcbs-.*",
            r"united-.*",
            r"cigna-.*",
            r"aetna-.*",
            r"humana-.*",
        ]

        for pattern in patterns:
            registry.register_pattern(pattern, MagicMock())

        test_ids = [
            "bcbs-california",
            "united-health",
            "cigna-east",
            "aetna-national",
            "humana-gold",
            "unknown-platform",
        ]

        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            for platform_id in test_ids:
                registry._resolve_platform_id(platform_id)

        elapsed = time.perf_counter() - start
        total_lookups = iterations * len(test_ids)
        avg_time = elapsed / total_lookups

        # Pattern matching should complete in under 0.05ms per lookup
        assert avg_time < 0.00005, f"Average lookup time {avg_time:.6f}s too slow"


class TestAuditLoggingPerformance:
    """Performance benchmarks for audit logging."""

    def test_audit_log_performance(self):
        """Benchmark audit log calls."""
        from app.audit import AuditEvent, audit_log

        iterations = 1000
        start = time.perf_counter()

        for i in range(iterations):
            audit_log(
                event=AuditEvent.RESOURCE_READ,
                platform_id=f"platform-{i % 10}",
                resource_type="Patient",
                resource_id=f"patient-{i}",
                session_id=f"session-{i % 100}",
            )

        elapsed = time.perf_counter() - start
        avg_time = elapsed / iterations

        # Audit logging should be fast - under 0.5ms per call
        assert avg_time < 0.0005, f"Average audit log time {avg_time:.6f}s exceeds 0.5ms"


class TestEncryptionPerformance:
    """Performance benchmarks for encryption operations."""

    @pytest.mark.asyncio
    async def test_token_encryption_performance(self):
        """Benchmark token encryption/decryption."""
        from app.auth.secure_token_store import MasterKeyEncryption

        encryption = MasterKeyEncryption("test-master-key-for-benchmarks")

        token_data = '{"access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9", "token_type": "Bearer"}'
        session_id = "test-session-123"

        iterations = 100
        start = time.perf_counter()

        for _ in range(iterations):
            # Encrypt
            encrypted = encryption.encrypt(token_data, session_id)
            # Decrypt
            decrypted = encryption.decrypt(encrypted, session_id)
            assert decrypted == token_data

        elapsed = time.perf_counter() - start
        avg_time = elapsed / iterations

        # Encryption round-trip should complete in under 50ms (PBKDF2 is deliberately slow)
        assert avg_time < 0.05, f"Average encryption time {avg_time:.4f}s exceeds 50ms"


class TestConcurrentOperations:
    """Performance benchmarks for concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_token_lookups(self):
        """Benchmark concurrent token lookups."""
        from app.auth.secure_token_store import InMemoryTokenStorage

        storage = InMemoryTokenStorage()

        # Pre-populate
        for i in range(50):
            key = f"session:{i}:platform:{i % 5}"
            await storage.set(key, f"token-{i}", ttl=3600)

        async def lookup_tokens():
            for i in range(100):
                key = f"session:{i % 50}:platform:{i % 5}"
                await storage.get(key)

        # Run 10 concurrent lookup tasks
        start = time.perf_counter()
        await asyncio.gather(*[lookup_tokens() for _ in range(10)])
        elapsed = time.perf_counter() - start

        # 1000 total lookups should complete in under 100ms
        assert elapsed < 0.1, f"Concurrent lookups took {elapsed:.4f}s, exceeds 100ms"

    @pytest.mark.asyncio
    async def test_concurrent_validations(self):
        """Benchmark concurrent input validations."""
        from app.validation import validate_resource_id, validate_resource_type

        async def validate_batch():
            for i in range(100):
                validate_resource_type("Patient")
                validate_resource_id(f"patient-{i}")

        # Run 10 concurrent validation tasks
        start = time.perf_counter()
        await asyncio.gather(*[validate_batch() for _ in range(10)])
        elapsed = time.perf_counter() - start

        # 2000 total validations should complete in under 50ms
        assert elapsed < 0.05, f"Concurrent validations took {elapsed:.4f}s, exceeds 50ms"


class TestMemoryEfficiency:
    """Tests for memory efficiency of data structures."""

    def test_bundle_entry_extraction_efficiency(self):
        """Verify Bundle entry extraction is efficient."""
        # Create a moderately sized bundle
        bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 500,
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": f"patient-{i}",
                        "name": [{"family": f"Family{i}", "given": [f"Given{i}"]}],
                        "address": [
                            {
                                "line": [f"{i} Main St"],
                                "city": "Anytown",
                                "state": "CA",
                                "postalCode": "12345",
                            }
                        ],
                    }
                }
                for i in range(500)
            ],
        }

        # Time the extraction
        start = time.perf_counter()

        entries = bundle.get("entry", [])
        resources = [e.get("resource") for e in entries]
        patient_ids = [r.get("id") for r in resources]

        elapsed = time.perf_counter() - start

        assert len(patient_ids) == 500
        # Should complete in under 5ms
        assert elapsed < 0.005, f"Extraction took {elapsed:.4f}s, exceeds 5ms"

    def test_dict_iteration_performance(self):
        """Test dictionary iteration performance for token lookups."""
        # Simulate a token store with many entries
        store = {}
        for i in range(1000):
            store[f"session:{i}:platform:{i % 10}"] = f"token-{i}"

        iterations = 100
        start = time.perf_counter()

        for _ in range(iterations):
            # Find all keys matching a pattern (prefix)
            prefix = "session:50:"
            [k for k in store.keys() if k.startswith(prefix)]

        elapsed = time.perf_counter() - start
        avg_time = elapsed / iterations

        # Pattern matching should be fast
        assert avg_time < 0.001, f"Average iteration time {avg_time:.6f}s exceeds 1ms"
