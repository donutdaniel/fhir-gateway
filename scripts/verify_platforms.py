#!/usr/bin/env python3
"""
Platform Endpoint Verification Script

This script tests connectivity and capabilities of all configured platform FHIR endpoints.
It generates both a markdown report and JSON results for CI/CD integration.

Usage:
    python scripts/verify_platforms.py
    python scripts/verify_platforms.py --timeout 15
    python scripts/verify_platforms.py --output-dir results/
    python scripts/verify_platforms.py --update-docs  # Update docs/PLATFORMS.md
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.platform import PlatformDefinition, load_config, reload_config


@dataclass
class EndpointResult:
    """Result of testing a single endpoint."""

    platform_id: str
    platform_name: str
    platform_type: str | None
    fhir_base_url: str | None
    sandbox_url: str | None
    developer_portal: str | None
    verification_status: str | None

    # Test results
    metadata_reachable: bool = False
    metadata_status_code: int | None = None
    metadata_response_time_ms: float | None = None
    smart_config_reachable: bool = False
    smart_config_status_code: int | None = None

    # Capability info
    fhir_version: str | None = None
    supported_resources: list[str] = field(default_factory=list)

    # OAuth
    has_oauth: bool = False

    # Errors
    error: str | None = None
    notes: str | None = None


@dataclass
class VerificationReport:
    """Complete verification report."""

    timestamp: str
    total_platforms: int
    verified_count: int
    partial_count: int
    needs_registration_count: int
    unreachable_count: int
    payer_count: int
    ehr_count: int
    sandbox_count: int
    results: list[EndpointResult] = field(default_factory=list)


async def test_endpoint(
    session: aiohttp.ClientSession,
    platform: PlatformDefinition,
    timeout: float = 10.0,
) -> EndpointResult:
    """Test a single platform's FHIR endpoint."""
    result = EndpointResult(
        platform_id=platform.id,
        platform_name=platform.name,
        platform_type=platform.type,
        fhir_base_url=platform.fhir_base_url,
        sandbox_url=platform.sandbox_url,
        developer_portal=platform.developer_portal,
        verification_status=platform.verification_status,
        has_oauth=bool(platform.oauth and platform.oauth.authorize_url),
    )

    if not platform.fhir_base_url:
        result.notes = "No FHIR base URL configured - developer registration required"
        return result

    base_url = platform.fhir_base_url.rstrip("/")

    # Test /metadata endpoint (CapabilityStatement)
    metadata_url = f"{base_url}/metadata"
    try:
        start_time = asyncio.get_event_loop().time()
        async with session.get(
            metadata_url,
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={
                "Accept": "application/fhir+json",
            },
        ) as response:
            end_time = asyncio.get_event_loop().time()
            result.metadata_status_code = response.status
            result.metadata_response_time_ms = (end_time - start_time) * 1000

            # 200 = success, 401/403 = auth required (still reachable)
            if response.status in (200, 401, 403):
                result.metadata_reachable = True

            if response.status == 200:
                try:
                    data = await response.json()
                    result.fhir_version = data.get("fhirVersion")
                    # Extract supported resources
                    rest = data.get("rest", [])
                    if rest:
                        resources = rest[0].get("resource", [])
                        result.supported_resources = [
                            r.get("type") for r in resources if r.get("type")
                        ][:10]  # Limit to first 10
                except Exception:
                    pass

    except TimeoutError:
        result.error = f"Timeout after {timeout}s"
    except aiohttp.ClientConnectorError as e:
        result.error = f"Connection error: {str(e)}"
    except Exception as e:
        result.error = f"Error: {str(e)}"

    # Test /.well-known/smart-configuration
    smart_url = f"{base_url}/.well-known/smart-configuration"
    try:
        async with session.get(
            smart_url,
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={
                "Accept": "application/json",
            },
        ) as response:
            result.smart_config_status_code = response.status
            if response.status in (200, 401, 403):
                result.smart_config_reachable = True
    except Exception:
        pass  # SMART config is optional

    return result


async def verify_all_platforms(timeout: float = 10.0) -> VerificationReport:
    """Verify all configured platform endpoints."""
    # Force reload to get fresh config
    config = reload_config()
    platforms = list(config.platforms.values())

    print(f"Testing {len(platforms)} platform endpoints...")

    results: list[EndpointResult] = []

    async with aiohttp.ClientSession() as session:
        tasks = [test_endpoint(session, platform, timeout) for platform in platforms]
        results = await asyncio.gather(*tasks)

    # Count results
    verified = sum(1 for r in results if r.metadata_reachable)
    partial = sum(
        1
        for r in results
        if r.verification_status == "partial" or (r.sandbox_url and not r.metadata_reachable)
    )
    needs_registration = sum(
        1 for r in results if r.verification_status == "needs_registration" or (not r.fhir_base_url)
    )
    unreachable = sum(
        1
        for r in results
        if r.fhir_base_url
        and not r.metadata_reachable
        and r.verification_status != "needs_registration"
    )

    # Count by type
    payer_count = sum(1 for r in results if r.platform_type == "payer")
    ehr_count = sum(1 for r in results if r.platform_type == "ehr")
    sandbox_count = sum(1 for r in results if r.platform_type == "sandbox")

    return VerificationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_platforms=len(platforms),
        verified_count=verified,
        partial_count=partial,
        needs_registration_count=needs_registration,
        unreachable_count=unreachable,
        payer_count=payer_count,
        ehr_count=ehr_count,
        sandbox_count=sandbox_count,
        results=results,
    )


def generate_markdown_report(report: VerificationReport) -> str:
    """Generate a markdown report from verification results."""
    lines = [
        "# FHIR Gateway - Platform Verification Report",
        "",
        f"**Generated:** {report.timestamp}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total Platforms | {report.total_platforms} |",
        f"| Verified (Reachable) | {report.verified_count} |",
        f"| Partial (Sandbox Only) | {report.partial_count} |",
        f"| Needs Registration | {report.needs_registration_count} |",
        f"| Unreachable | {report.unreachable_count} |",
        "",
        "### By Type",
        "",
        "| Type | Count |",
        "|------|-------|",
        f"| Payers | {report.payer_count} |",
        f"| EHRs | {report.ehr_count} |",
        f"| Sandboxes | {report.sandbox_count} |",
        "",
    ]

    # Group by status
    verified_results = [r for r in report.results if r.metadata_reachable]
    needs_reg_results = [
        r
        for r in report.results
        if r.verification_status == "needs_registration" or not r.fhir_base_url
    ]
    other_results = [
        r for r in report.results if not r.metadata_reachable and r not in needs_reg_results
    ]

    if verified_results:
        lines.append("## Verified (Reachable)")
        lines.append("")
        lines.append("| Platform | Type | Status | Response Time | FHIR Version | OAuth |")
        lines.append("|----------|------|--------|---------------|--------------|-------|")
        for r in sorted(verified_results, key=lambda x: x.platform_name):
            status = f"{r.metadata_status_code}" if r.metadata_status_code else "N/A"
            time_ms = (
                f"{r.metadata_response_time_ms:.0f}ms" if r.metadata_response_time_ms else "N/A"
            )
            version = r.fhir_version or "N/A"
            oauth = "Yes" if r.has_oauth else "No"
            ptype = r.platform_type or "unknown"
            lines.append(
                f"| {r.platform_name} | {ptype} | {status} | {time_ms} | {version} | {oauth} |"
            )
        lines.append("")

    if needs_reg_results:
        lines.append("## Needs Registration")
        lines.append("")
        lines.append("| Platform | Type | Developer Portal | Notes |")
        lines.append("|----------|------|------------------|-------|")
        for r in sorted(needs_reg_results, key=lambda x: x.platform_name):
            portal = r.developer_portal or "N/A"
            notes = r.notes or "Developer registration required"
            ptype = r.platform_type or "unknown"
            lines.append(f"| {r.platform_name} | {ptype} | {portal} | {notes} |")
        lines.append("")

    if other_results:
        lines.append("## Other/Unreachable")
        lines.append("")
        lines.append("| Platform | Type | URL | Error |")
        lines.append("|----------|------|-----|-------|")
        for r in sorted(other_results, key=lambda x: x.platform_name):
            url = r.fhir_base_url or "N/A"
            error = r.error or "Unknown"
            ptype = r.platform_type or "unknown"
            lines.append(f"| {r.platform_name} | {ptype} | {url} | {error} |")
        lines.append("")

    # Capability matrix
    lines.append("## Capability Matrix")
    lines.append("")
    lines.append("| Platform | Patient Access | Provider Dir | CRD | DTR | PAS | CDex |")
    lines.append("|----------|---------------|--------------|-----|-----|-----|------|")

    config = load_config()
    for r in sorted(report.results, key=lambda x: x.platform_name):
        platform = config.get_platform(r.platform_id)
        if platform and platform.capabilities:
            cap = platform.capabilities
            pa = "Yes" if cap.patient_access else "No"
            pd = "Yes" if cap.provider_directory else "No"
            crd = "Yes" if cap.crd else "No"
            dtr = "Yes" if cap.dtr else "No"
            pas = "Yes" if cap.pas else "No"
            cdex = "Yes" if cap.cdex else "No"
        else:
            pa = pd = crd = dtr = pas = cdex = "?"
        lines.append(f"| {r.platform_name} | {pa} | {pd} | {crd} | {dtr} | {pas} | {cdex} |")

    lines.append("")
    lines.append("---")
    lines.append("*Report generated by scripts/verify_platforms.py*")

    return "\n".join(lines)


def generate_platforms_doc(report: VerificationReport) -> str:
    """Generate the docs/PLATFORMS.md documentation file."""
    # Count by category
    verified = [r for r in report.results if r.metadata_reachable]
    partial = [
        r
        for r in report.results
        if r.verification_status == "partial" or (r.sandbox_url and not r.metadata_reachable)
    ]
    needs_reg = [
        r
        for r in report.results
        if r.verification_status == "needs_registration" or not r.fhir_base_url
    ]
    unverified = [
        r
        for r in report.results
        if r.fhir_base_url
        and not r.metadata_reachable
        and r.verification_status not in ("needs_registration", "partial")
    ]

    lines = [
        "# FHIR Gateway - Platform Directory",
        "",
        "This document tracks the health and configuration status of all platforms.",
        "",
        "## Architecture",
        "",
        "All platforms use the `GenericPayerAdapter` which loads configuration dynamically from JSON files in `app/platforms/`.",
        "",
        "```",
        "app/",
        "├── platforms/           # Platform configuration files",
        "│   ├── aetna.json",
        "│   ├── epic.json",
        "│   └── ...",
        "└── adapters/",
        "    ├── base.py          # BasePayerAdapter with full implementation",
        "    ├── generic.py       # GenericPayerAdapter (used for all platforms)",
        "    └── registry.py      # Auto-registration from platforms/*.json",
        "```",
        "",
        "## Overview",
        "",
        "| Category | Count | Percentage |",
        "|----------|-------|------------|",
        f"| **Working (verified + URL)** | {len(verified)} | {100 * len(verified) // report.total_platforms}% |",
        f"| **Partial (URL but unverified)** | {len(partial)} | {100 * len(partial) // report.total_platforms}% |",
        f"| **Needs Registration** | {len(needs_reg)} | {100 * len(needs_reg) // report.total_platforms}% |",
        f"| **Unverified (no URL)** | {len(unverified)} | {100 * len(unverified) // report.total_platforms}% |",
        f"| **Total** | {report.total_platforms} | 100% |",
        "",
        "### By Type",
        "",
        "| Type | Count |",
        "|------|-------|",
        f"| Payers | {report.payer_count} |",
        f"| EHRs | {report.ehr_count} |",
        f"| Sandboxes | {report.sandbox_count} |",
        "",
        "---",
        "",
    ]

    # Working platforms
    if verified:
        lines.extend(
            [
                f"## ✅ Working Platforms ({len(verified)})",
                "",
                "These platforms are verified and have FHIR URLs configured:",
                "",
                "| Platform | ID | Type | FHIR Version | OAuth |",
                "|----------|-----|------|--------------|-------|",
            ]
        )
        for r in sorted(verified, key=lambda x: x.platform_name):
            oauth = "Yes" if r.has_oauth else "No"
            version = r.fhir_version or "N/A"
            ptype = r.platform_type or "unknown"
            lines.append(
                f"| {r.platform_name} | `{r.platform_id}` | {ptype} | {version} | {oauth} |"
            )
        lines.extend(["", "---", ""])

    # Partial platforms
    if partial:
        lines.extend(
            [
                f"## ⚠️ Partial - Needs Verification ({len(partial)})",
                "",
                "These platforms have FHIR URLs configured but need verification:",
                "",
                "| Platform | ID | Status |",
                "|----------|-----|--------|",
            ]
        )
        for r in sorted(partial, key=lambda x: x.platform_name):
            lines.append(f"| {r.platform_name} | `{r.platform_id}` | Has URL, needs verification |")
        lines.extend(["", "---", ""])

    # Needs registration
    if needs_reg:
        lines.extend(
            [
                f"## 🔧 Needs Registration ({len(needs_reg)})",
                "",
                "These platforms require developer portal registration to obtain production FHIR URLs:",
                "",
                "| Platform | ID | Developer Portal | Notes |",
                "|----------|-----|------------------|-------|",
            ]
        )
        for r in sorted(needs_reg, key=lambda x: x.platform_name):
            portal = r.developer_portal if r.developer_portal else "-"
            notes = r.notes or "-"
            lines.append(f"| {r.platform_name} | `{r.platform_id}` | {portal} | {notes} |")
        lines.extend(["", "---", ""])

    # Unverified
    if unverified:
        lines.extend(
            [
                f"## ❌ Unverified - No URL ({len(unverified)})",
                "",
                "These platforms exist but have no working FHIR URL:",
                "",
                "| Platform | ID | Error |",
                "|----------|-----|-------|",
            ]
        )
        for r in sorted(unverified, key=lambda x: x.platform_name):
            error = r.error or "No URL configured"
            lines.append(f"| {r.platform_name} | `{r.platform_id}` | {error} |")
        lines.extend(["", "---", ""])

    # Configuration structure
    lines.extend(
        [
            "## Configuration Structure",
            "",
            "Each platform is defined in a JSON file at `app/platforms/{platform_id}.json`:",
            "",
            "```json",
            "{",
            '  "id": "platform_id",',
            '  "name": "Full Platform Name",',
            '  "display_name": "Display Name",',
            '  "type": "payer|ehr|sandbox",',
            '  "aliases": ["alias1", "alias2"],',
            '  "patterns": ["pattern1"],',
            '  "fhir_base_url": "https://api.platform.com/fhir/r4",',
            '  "verification_status": "verified|needs_registration|unverified",',
            '  "capabilities": {',
            '    "patient_access": true,',
            '    "crd": false,',
            '    "dtr": false,',
            '    "pas": false,',
            '    "cdex": false',
            "  },",
            '  "developer_portal": "https://developer.platform.com",',
            '  "oauth": {',
            '    "authorize_url": "https://auth.platform.com/authorize",',
            '    "token_url": "https://auth.platform.com/token"',
            "  }",
            "}",
            "```",
            "",
            "---",
            "",
            "## Adding a New Platform",
            "",
            "1. Create `app/platforms/{platform_id}.json` with platform details",
            "2. Restart the server - the platform will be auto-registered",
            "",
            "That's it! The `GenericPayerAdapter` handles everything dynamically.",
            "",
            "---",
            "",
            f"*Last updated: {datetime.now().strftime('%B %Y')}*",
            "",
        ]
    )

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Verify FHIR platform endpoints")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).parent / "reports"),
        help="Output directory for reports (default: scripts/reports/)",
    )
    parser.add_argument(
        "--update-docs",
        action="store_true",
        help="Update docs/PLATFORMS.md with current status",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("FHIR Platform Endpoint Verification")
    print(f"Timeout: {args.timeout}s")
    print(f"Output: {output_dir}")
    print()

    report = asyncio.run(verify_all_platforms(args.timeout))

    # Generate markdown report
    markdown = generate_markdown_report(report)
    md_path = output_dir / "verification_report.md"
    with open(md_path, "w") as f:
        f.write(markdown)
    print(f"Markdown report: {md_path}")

    # Generate JSON results
    json_results = {
        "timestamp": report.timestamp,
        "summary": {
            "total_platforms": report.total_platforms,
            "verified_count": report.verified_count,
            "partial_count": report.partial_count,
            "needs_registration_count": report.needs_registration_count,
            "unreachable_count": report.unreachable_count,
            "payer_count": report.payer_count,
            "ehr_count": report.ehr_count,
            "sandbox_count": report.sandbox_count,
        },
        "results": [asdict(r) for r in report.results],
    }
    json_path = output_dir / "verification_results.json"
    with open(json_path, "w") as f:
        json.dump(json_results, f, indent=2)
    print(f"JSON results: {json_path}")

    # Update docs if requested
    if args.update_docs:
        docs_dir = Path(__file__).parent.parent / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        platforms_doc = generate_platforms_doc(report)
        platforms_path = docs_dir / "PLATFORMS.md"
        with open(platforms_path, "w") as f:
            f.write(platforms_doc)
        print(f"Updated docs: {platforms_path}")

    print()
    print("Summary:")
    print(f"  Total: {report.total_platforms}")
    print(f"  Verified: {report.verified_count}")
    print(f"  Needs Registration: {report.needs_registration_count}")
    print(f"  Unreachable: {report.unreachable_count}")
    print()
    print(f"  Payers: {report.payer_count}")
    print(f"  EHRs: {report.ehr_count}")
    print(f"  Sandboxes: {report.sandbox_count}")

    # Return non-zero if any configured endpoints are unreachable
    if report.unreachable_count > 0:
        print()
        print(f"WARNING: {report.unreachable_count} configured endpoint(s) unreachable")
        sys.exit(1)


if __name__ == "__main__":
    main()
