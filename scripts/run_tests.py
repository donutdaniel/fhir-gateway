#!/usr/bin/env python3
"""
Test runner script for FHIR Gateway.

Usage:
    python scripts/run_tests.py [--coverage] [--verbose] [pattern]

Examples:
    python scripts/run_tests.py                    # Run all tests
    python scripts/run_tests.py --coverage         # Run with coverage report
    python scripts/run_tests.py test_auth          # Run tests matching pattern
    python scripts/run_tests.py --verbose test_oauth  # Verbose output for oauth tests
"""

import subprocess
import sys
from pathlib import Path


def main():
    args = sys.argv[1:]

    # Base pytest command
    cmd = ["uv", "run", "pytest"]

    # Parse arguments
    coverage = False
    verbose = False
    patterns = []

    for arg in args:
        if arg == "--coverage":
            coverage = True
        elif arg == "--verbose" or arg == "-v":
            verbose = True
        elif not arg.startswith("-"):
            patterns.append(arg)

    # Add coverage if requested
    if coverage:
        cmd.extend(["--cov=app", "--cov-report=term-missing", "--cov-report=html"])

    # Add verbose if requested
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Add pattern filter if specified
    if patterns:
        cmd.extend(["-k", " or ".join(patterns)])

    # Change to project root
    project_root = Path(__file__).parent.parent

    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)

    result = subprocess.run(cmd, cwd=project_root)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
