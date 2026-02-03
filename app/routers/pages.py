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
        .platform {{ padding: 0.5rem 0; border-bottom: 1px solid #eee; }}
        .platform:last-child {{ border-bottom: none; }}
        .platform-name {{ font-weight: 500; }}
        .platform-type {{ color: #666; font-size: 0.85rem; }}
        .platform-ready {{ font-size: 0.8rem; }}
        .loading {{ color: #666; font-style: italic; }}
        footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ddd; font-size: 0.85rem; color: #666; }}
        footer a {{ color: #666; }}
    </style>
</head>
<body>
    {content}
    <footer>
        <a href="/terms-conditions">Terms & Conditions</a> ·
        <a href="https://github.com/donutdaniel/fhir-gateway">GitHub</a>
    </footer>
    {scripts}
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def landing_page() -> str:
    """Landing page with MCP connection instructions and platform list."""
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
      "url": "{html.escape(mcp_url)}",
      "transport": "streamable-http"
    }}
  }}
}}</code></pre>
    <p>
        <strong>macOS:</strong> <code class="inline-code">~/Library/Application Support/Claude/claude_desktop_config.json</code><br>
        <strong>Windows:</strong> <code class="inline-code">%APPDATA%\\Claude\\claude_desktop_config.json</code>
    </p>

    <h2>Platforms</h2>
    <div id="platforms"><span class="loading">Loading platforms...</span></div>
    """

    scripts = """
    <script>
        async function loadPlatforms() {
            try {
                const res = await fetch('/api/platforms');
                const data = await res.json();
                const container = document.getElementById('platforms');

                if (!data.platforms || data.platforms.length === 0) {
                    container.innerHTML = '<p>No platforms configured.</p>';
                    return;
                }

                // Sort: ready platforms first, then by name
                const platforms = data.platforms.sort((a, b) => {
                    if (a.oauth_registered !== b.oauth_registered) {
                        return b.oauth_registered ? 1 : -1;
                    }
                    return (a.name || a.id).localeCompare(b.name || b.id);
                });

                container.innerHTML = platforms.map(p => `
                    <div class="platform">
                        <span class="platform-name">${p.name || p.id}</span>
                        <span class="platform-type">${p.type || ''}</span>
                        ${p.oauth_registered ? '<span class="platform-ready">· Ready</span>' : ''}
                    </div>
                `).join('');
            } catch (e) {
                document.getElementById('platforms').innerHTML = '<p>Failed to load platforms.</p>';
            }
        }
        loadPlatforms();
    </script>
    """

    return _base_html("FHIR Gateway", content, scripts)


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
