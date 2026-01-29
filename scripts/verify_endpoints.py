#!/usr/bin/env python3
"""
Verify FHIR Gateway endpoints are working.

Usage:
    python scripts/verify_endpoints.py [--base-url URL]

Requires the server to be running.
"""

import argparse
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


def check_endpoint(url: str, name: str) -> bool:
    """Check if an endpoint is responding."""
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as response:
            status = response.status
            if status == 200:
                print(f"  [OK] {name}: {url}")
                return True
            else:
                print(f"  [WARN] {name}: {url} (status {status})")
                return True
    except URLError as e:
        print(f"  [FAIL] {name}: {url} ({e.reason})")
        return False
    except Exception as e:
        print(f"  [FAIL] {name}: {url} ({e})")
        return False


def main():
    parser = argparse.ArgumentParser(description="Verify FHIR Gateway endpoints")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the FHIR Gateway (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    print(f"\nVerifying FHIR Gateway at {base_url}\n")
    print("=" * 60)

    endpoints = [
        (f"{base_url}/health", "Health Check"),
        (f"{base_url}/docs", "OpenAPI Docs"),
        (f"{base_url}/api/payers", "Payers List"),
        (f"{base_url}/auth/status", "Auth Status"),
    ]

    results = []
    for url, name in endpoints:
        results.append(check_endpoint(url, name))

    print("=" * 60)

    passed = sum(results)
    total = len(results)

    if all(results):
        print(f"\nAll {total} endpoints OK")
        return 0
    else:
        print(f"\n{passed}/{total} endpoints OK")
        return 1


if __name__ == "__main__":
    sys.exit(main())
