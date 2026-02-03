"""
Public pages - landing page and terms & conditions.
"""

import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config.settings import get_settings

router = APIRouter(tags=["pages"])


def _base_html(title: str, content: str) -> str:
    """Generate base HTML with consistent styling."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #1a1a2e;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 2.5rem;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
            margin-bottom: 1.5rem;
        }}
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        h2 {{
            font-size: 1.5rem;
            color: #333;
            margin: 1.5rem 0 1rem;
            padding-top: 1rem;
            border-top: 1px solid #eee;
        }}
        h2:first-of-type {{
            border-top: none;
            padding-top: 0;
        }}
        h3 {{
            font-size: 1.1rem;
            color: #555;
            margin: 1rem 0 0.5rem;
        }}
        .subtitle {{
            color: #666;
            font-size: 1.1rem;
            margin-bottom: 1.5rem;
        }}
        .badge {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.85rem;
            margin-bottom: 1rem;
        }}
        pre {{
            background: #1a1a2e;
            color: #a5d6ff;
            padding: 1.25rem;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 0.9rem;
            margin: 1rem 0;
        }}
        code {{
            font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
        }}
        .inline-code {{
            background: #f0f0f5;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.9rem;
        }}
        p {{
            margin-bottom: 1rem;
            color: #444;
        }}
        ul, ol {{
            margin: 1rem 0 1rem 1.5rem;
            color: #444;
        }}
        li {{
            margin-bottom: 0.5rem;
        }}
        a {{
            color: #667eea;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .features {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 1.5rem 0;
        }}
        .feature {{
            background: #f8f9ff;
            padding: 1rem;
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }}
        .feature-title {{
            font-weight: 600;
            color: #333;
            margin-bottom: 0.25rem;
        }}
        .feature-desc {{
            font-size: 0.9rem;
            color: #666;
        }}
        .links {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            margin-top: 1.5rem;
        }}
        .link {{
            display: inline-flex;
            align-items: center;
            padding: 0.5rem 1rem;
            background: #f0f0f5;
            border-radius: 8px;
            color: #333;
            font-size: 0.9rem;
            transition: background 0.2s;
        }}
        .link:hover {{
            background: #e0e0e8;
            text-decoration: none;
        }}
        footer {{
            text-align: center;
            padding: 2rem;
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.9rem;
        }}
        footer a {{
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
        <footer>
            <a href="/terms-conditions">Terms & Conditions</a> |
            <a href="/docs">API Docs</a> |
            <a href="https://github.com/anthropics/fhir-gateway">GitHub</a>
        </footer>
    </div>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def landing_page() -> str:
    """Landing page with MCP connection instructions."""
    settings = get_settings()
    public_url = settings.public_url.rstrip("/")
    mcp_url = f"{public_url}/mcp"

    content = f"""
        <div class="card">
            <span class="badge">v0.1.0</span>
            <h1>FHIR Gateway</h1>
            <p class="subtitle">
                A universal gateway for FHIR healthcare APIs with AI-native MCP integration
            </p>

            <div class="features">
                <div class="feature">
                    <div class="feature-title">Multi-Platform</div>
                    <div class="feature-desc">Route to 60+ payer FHIR endpoints</div>
                </div>
                <div class="feature">
                    <div class="feature-title">OAuth 2.0</div>
                    <div class="feature-desc">Session-scoped authentication with PKCE</div>
                </div>
                <div class="feature">
                    <div class="feature-title">MCP Native</div>
                    <div class="feature-desc">Built for AI assistants like Claude</div>
                </div>
                <div class="feature">
                    <div class="feature-title">REST API</div>
                    <div class="feature-desc">Standard FHIR REST endpoints</div>
                </div>
            </div>

            <div class="links">
                <a href="/docs" class="link">API Documentation</a>
                <a href="/api/platforms" class="link">View Platforms</a>
                <a href="/health" class="link">Health Check</a>
            </div>
        </div>

        <div class="card">
            <h2>Connect with Claude Desktop</h2>
            <p>
                Add this configuration to your <code class="inline-code">claude_desktop_config.json</code>:
            </p>
            <pre><code>{{
  "mcpServers": {{
    "fhir-gateway": {{
      "url": "{html.escape(mcp_url)}",
      "transport": "streamable-http"
    }}
  }}
}}</code></pre>

            <h3>Config file location</h3>
            <ul>
                <li><strong>macOS:</strong> <code class="inline-code">~/Library/Application Support/Claude/claude_desktop_config.json</code></li>
                <li><strong>Windows:</strong> <code class="inline-code">%APPDATA%\\Claude\\claude_desktop_config.json</code></li>
            </ul>

            <p style="margin-top: 1rem;">
                After adding the config, restart Claude Desktop. You can then ask Claude to search for patients,
                retrieve medical records, or explore coverage information from any supported payer.
            </p>
        </div>

        <div class="card">
            <h2>Quick Start with REST API</h2>
            <p>The gateway also provides a standard REST API for direct integration:</p>

            <h3>List available platforms</h3>
            <pre><code>curl {html.escape(public_url)}/api/platforms</code></pre>

            <h3>Get FHIR capability statement</h3>
            <pre><code>curl {html.escape(public_url)}/api/fhir/aetna/metadata</code></pre>

            <h3>Search for resources (requires auth)</h3>
            <pre><code>curl {html.escape(public_url)}/api/fhir/aetna/Patient?_count=10</code></pre>
        </div>
    """

    return _base_html("FHIR Gateway - Universal Healthcare API Gateway", content)


@router.get("/terms-conditions", response_class=HTMLResponse)
async def terms_conditions() -> str:
    """Terms and Conditions page."""
    content = """
        <div class="card">
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
            <p>
                The Service facilitates access to healthcare data from third-party FHIR endpoints.
                You acknowledge that:
            </p>
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
                <a href="https://github.com/anthropics/fhir-gateway">GitHub repository</a>.
            </p>
        </div>
    """

    return _base_html("Terms & Conditions - FHIR Gateway", content)
