"""
Public pages - landing page and terms & conditions.
"""

import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config.settings import get_settings

router = APIRouter(tags=["pages"])


def _base_html(title: str, content: str, scripts: str = "") -> str:
    """Generate base HTML with minimal styling."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #222;
            max-width: 700px;
            margin: 0 auto;
            padding: 2rem 1rem;
        }}
        h1 {{ font-size: 1.75rem; margin-bottom: 0.25rem; }}
        h2 {{ font-size: 1.25rem; margin: 2rem 0 0.75rem; border-bottom: 1px solid #ddd; padding-bottom: 0.25rem; }}
        h3 {{ font-size: 1rem; margin: 1rem 0 0.5rem; }}
        p {{ margin-bottom: 1rem; color: #444; }}
        ul, ol {{ margin: 0.5rem 0 1rem 1.5rem; color: #444; }}
        li {{ margin-bottom: 0.25rem; }}
        a {{ color: #222; }}
        pre {{
            background: #f5f5f5;
            border: 1px solid #ddd;
            padding: 1rem;
            overflow-x: auto;
            font-size: 0.85rem;
            margin: 0.5rem 0 1rem;
        }}
        code {{ font-family: 'SF Mono', Consolas, monospace; }}
        .inline-code {{ background: #f5f5f5; padding: 0.1rem 0.3rem; font-size: 0.9rem; }}
        .subtitle {{ color: #666; margin-bottom: 1.5rem; }}
        .platform {{ padding: 0.4rem 0; display: flex; align-items: center; gap: 0.5rem; }}
        .platform-name {{ font-weight: 500; }}
        .platform-type {{ color: #666; font-size: 0.85rem; }}
        .status {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
        .status-ready {{ background: #22c55e; }}
        .status-pending {{ background: #d1d5db; }}
        .group {{ margin-bottom: 2rem; }}
        .group-title {{ font-size: 1rem; font-weight: 600; margin-bottom: 0.5rem; padding-bottom: 0.25rem; border-bottom: 1px solid #ddd; }}
        .loading {{ color: #666; font-style: italic; }}
        footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ddd; font-size: 0.85rem; color: #666; }}
        footer a {{ color: #666; }}
    </style>
</head>
<body>
    {content}
    <footer>
        <a href="/privacy-policy">Privacy Policy</a> ·
        <a href="/terms-conditions">Terms & Conditions</a> ·
        <a href="https://github.com/donutdaniel/fhir-gateway">GitHub</a>
    </footer>
    {scripts}
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def landing_page() -> str:
    """Landing page with MCP connection instructions."""
    settings = get_settings()
    public_url = settings.public_url.rstrip("/")
    mcp_url = f"{public_url}/mcp"

    content = f"""
    <h1>FHIR Gateway</h1>
    <p class="subtitle">A gateway for FHIR healthcare APIs with MCP integration for Claude.</p>

    <h2>Connect with Claude</h2>
    <p>
        <strong>MCP URL:</strong> <code class="inline-code">{html.escape(mcp_url)}</code>
    </p>

    <h3>Claude.ai / Claude Pro</h3>
    <p>Go to Settings → Connectors → Add Custom Connector, then enter:</p>
    <ul>
        <li><strong>Name:</strong> FHIR Gateway</li>
        <li><strong>Remote MCP URL:</strong> <code class="inline-code">{html.escape(mcp_url)}</code></li>
    </ul>

    <h3>Claude Desktop</h3>
    <p>Add to <code class="inline-code">claude_desktop_config.json</code>:</p>
    <pre><code>{{
  "mcpServers": {{
    "fhir-gateway": {{
      "command": "npx",
      "args": ["-y", "mcp-remote", "{html.escape(mcp_url)}"]
    }}
  }}
}}</code></pre>

    <p style="margin-top: 2rem;"><a href="/platforms">View supported platforms →</a></p>
    """

    return _base_html("FHIR Gateway", content)


@router.get("/platforms", response_class=HTMLResponse)
async def platforms_page() -> str:
    """Platforms listing page."""
    from app.config.platform import get_all_platforms

    all_platforms = get_all_platforms()

    # Build platform list grouped by type
    by_type: dict[str, list[dict]] = {}
    ready_count = 0

    for platform_id, platform in all_platforms.items():
        oauth_registered = bool(platform.oauth and platform.oauth.is_registered)
        if oauth_registered:
            ready_count += 1

        platform_type = platform.type or "other"
        if platform_type not in by_type:
            by_type[platform_type] = []

        by_type[platform_type].append(
            {
                "id": platform_id,
                "name": platform.display_name or platform.name,
                "ready": oauth_registered,
            }
        )

    # Sort platforms within each group: ready first, then by name
    for platforms in by_type.values():
        platforms.sort(key=lambda p: (not p["ready"], p["name"] or p["id"]))

    # Order of type groups
    type_order = ["sandbox", "ehr", "payer", "other"]
    type_labels = {
        "sandbox": "Sandboxes",
        "ehr": "EHR Systems",
        "payer": "Payers",
        "other": "Other",
    }

    groups_html = []
    for ptype in type_order:
        if ptype not in by_type:
            continue
        platforms = by_type[ptype]
        rows = []
        for p in platforms:
            status_class = "status-ready" if p["ready"] else "status-pending"
            rows.append(
                f'<div class="platform">'
                f'<span class="status {status_class}"></span>'
                f'<span class="platform-name">{html.escape(p["name"] or p["id"])}</span>'
                f"</div>"
            )
        groups_html.append(
            f'<div class="group">'
            f'<div class="group-title">{type_labels.get(ptype, ptype.title())}</div>'
            f"{''.join(rows)}"
            f"</div>"
        )

    total = len(all_platforms)
    content = f"""
    <h1>Platforms</h1>
    <p class="subtitle">{ready_count} ready · {total} total</p>
    {"".join(groups_html)}
    <p><a href="/">← Back</a></p>
    """

    return _base_html("Platforms - FHIR Gateway", content)


@router.get("/terms-conditions", response_class=HTMLResponse)
async def terms_conditions() -> str:
    """Terms and Conditions page."""
    content = """
    <h1>Terms & Conditions</h1>
    <p class="subtitle">Last updated: February 2025</p>

    <h2>1. Acceptance of Terms</h2>
    <p>
        By accessing or using the FHIR Gateway service ("Service"), you agree to be bound by these
        Terms and Conditions. If you do not agree to these terms, do not use the Service.
    </p>

    <h2>2. Description of Service</h2>
    <p>
        FHIR Gateway is an API gateway that facilitates connections to healthcare FHIR endpoints.
        The Service acts as an intermediary and does not store, process, or retain any protected
        health information (PHI) beyond what is necessary for real-time request routing.
    </p>

    <h2>3. User Responsibilities</h2>
    <ul>
        <li>You are responsible for maintaining the confidentiality of your authentication credentials</li>
        <li>You must comply with all applicable healthcare regulations including HIPAA when accessing PHI</li>
        <li>You agree not to use the Service for any unlawful purpose</li>
        <li>You are responsible for ensuring you have proper authorization to access any healthcare data</li>
    </ul>

    <h2>4. Healthcare Data</h2>
    <p>The Service facilitates access to healthcare data from third-party FHIR endpoints. You acknowledge that:</p>
    <ul>
        <li>Data accuracy depends on the source systems</li>
        <li>The Service does not verify or validate healthcare data</li>
        <li>You must not use retrieved data for clinical decisions without proper verification</li>
        <li>Access to data is subject to the terms of the underlying healthcare platforms</li>
    </ul>

    <h2>5. Privacy</h2>
    <p>
        The Service processes requests in real-time and does not persistently store PHI.
        Session tokens are encrypted and automatically expire. We collect minimal operational
        logs for service reliability which do not contain PHI.
    </p>

    <h2>6. Disclaimer of Warranties</h2>
    <p>
        THE SERVICE IS PROVIDED "AS IS" WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED.
        WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR SECURE.
    </p>

    <h2>7. Limitation of Liability</h2>
    <p>
        IN NO EVENT SHALL THE SERVICE PROVIDERS BE LIABLE FOR ANY INDIRECT, INCIDENTAL,
        SPECIAL, OR CONSEQUENTIAL DAMAGES ARISING FROM YOUR USE OF THE SERVICE.
    </p>

    <h2>8. Third-Party Services</h2>
    <p>
        The Service connects to third-party healthcare platforms. Your use of those platforms
        is subject to their respective terms of service. We are not responsible for the
        availability or accuracy of third-party services.
    </p>

    <h2>9. Changes to Terms</h2>
    <p>
        We reserve the right to modify these terms at any time. Continued use of the Service
        after changes constitutes acceptance of the new terms.
    </p>

    <h2>10. Contact</h2>
    <p>
        For questions about these terms, please open an issue on our
        <a href="https://github.com/donutdaniel/fhir-gateway">GitHub repository</a>.
    </p>
    """

    return _base_html("Terms & Conditions - FHIR Gateway", content)


@router.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy() -> str:
    """Privacy Policy page."""
    content = """
    <h1>Privacy Policy</h1>
    <p class="subtitle">Last updated: February 2026</p>

    <h2>1. Overview</h2>
    <p>
        FHIR Gateway ("Service") is an API gateway that connects users to healthcare FHIR endpoints.
        This policy explains what data we collect, how we use it, and your rights regarding that data.
    </p>

    <h2>2. Data We Collect</h2>
    <p>We collect the following data to operate the Service:</p>
    <ul>
        <li><strong>Session identifiers</strong> - Random tokens stored in cookies to maintain your session</li>
        <li><strong>OAuth tokens</strong> - Access and refresh tokens from healthcare platforms you authorize, stored temporarily in your session</li>
        <li><strong>Request logs</strong> - Timestamp, platform ID, resource type, and response status for operational monitoring (no PHI)</li>
    </ul>
    <p>
        We do <strong>not</strong> store, cache, or retain any Protected Health Information (PHI) or personal
        health data. All healthcare data flows through the Service in real-time and is not persisted.
    </p>

    <h2>3. How We Use Your Data</h2>
    <p>We use collected data solely to:</p>
    <ul>
        <li>Route your requests to the healthcare platforms you authorize</li>
        <li>Maintain your authenticated session</li>
        <li>Monitor service reliability and performance</li>
        <li>Troubleshoot technical issues</li>
    </ul>
    <p>
        We do <strong>not</strong> use your data for marketing, advertising, analytics profiling,
        or any purpose other than providing the Service.
    </p>

    <h2>4. Data Disclosure</h2>
    <p>We disclose data only in the following circumstances:</p>
    <ul>
        <li><strong>To healthcare platforms</strong> - When you authorize a connection, we transmit your OAuth tokens to that platform to retrieve your data</li>
        <li><strong>As required by law</strong> - If legally compelled by valid legal process</li>
    </ul>
    <p>
        We do <strong>not</strong> sell, rent, or share your personal data or health information with
        third parties for marketing or any other commercial purpose.
    </p>

    <h2>5. Consent</h2>
    <p>
        You explicitly consent to each healthcare platform connection through the OAuth authorization flow.
        Each platform requires separate authorization. We only access data from platforms you have authorized.
    </p>

    <h2>6. Withdrawing Consent</h2>
    <p>You can withdraw consent at any time by:</p>
    <ul>
        <li>Using the logout function to revoke platform access</li>
        <li>Clearing your browser cookies to end your session</li>
        <li>Revoking access through the healthcare platform's settings</li>
    </ul>
    <p>
        When you withdraw consent, your session tokens are immediately deleted. Since we do not
        persistently store PHI, there is no health data to delete.
    </p>

    <h2>7. Data Retention</h2>
    <ul>
        <li><strong>Session tokens</strong> - Automatically expire after 1 hour of inactivity</li>
        <li><strong>OAuth tokens</strong> - Deleted when you log out or your session expires</li>
        <li><strong>Request logs</strong> - Retained for up to 30 days for operational purposes, contain no PHI</li>
    </ul>

    <h2>8. Data Security</h2>
    <p>We protect your data through:</p>
    <ul>
        <li>Encryption of OAuth tokens at rest (when configured)</li>
        <li>TLS encryption for all data in transit</li>
        <li>Session isolation - your tokens are not accessible to other users</li>
        <li>No persistent storage of PHI</li>
    </ul>

    <h2>9. De-identified Information</h2>
    <p>
        We do not collect, use, or disclose de-identified health information. Request logs contain
        only operational metadata (timestamps, resource types, status codes) and cannot be used to
        identify individuals or their health conditions.
    </p>

    <h2>10. Third-Party Service Providers</h2>
    <p>
        Any third-party service providers (such as hosting providers) are contractually obligated
        to protect your data and may only use it to provide services to us.
    </p>

    <h2>11. Changes in Ownership</h2>
    <p>
        If the Service undergoes a change in ownership or ceases operation:
    </p>
    <ul>
        <li>All session data and OAuth tokens will be deleted</li>
        <li>Users will be notified if possible before any transfer</li>
        <li>Any successor would be bound by this privacy policy for existing data</li>
    </ul>

    <h2>12. Policy Updates</h2>
    <p>
        We may update this policy from time to time. Material changes will be noted with an updated
        "Last updated" date. Continued use of the Service after changes constitutes acceptance of
        the updated policy. For significant changes affecting data use, we will seek re-affirmation
        of consent where feasible.
    </p>

    <h2>13. Your Rights</h2>
    <p>You have the right to:</p>
    <ul>
        <li>Know what data we collect about you</li>
        <li>Withdraw consent and have your session data deleted</li>
        <li>Request information about our data practices</li>
    </ul>

    <h2>14. Contact</h2>
    <p>
        For questions about this privacy policy or to exercise your rights, please open an issue on our
        <a href="https://github.com/donutdaniel/fhir-gateway">GitHub repository</a> or contact the maintainers.
    </p>
    """

    return _base_html("Privacy Policy - FHIR Gateway", content)
