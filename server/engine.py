"""
Singleton AnyTool instance for the platform.

Standalone mode — no Nango. OAuth tokens stored encrypted in PostgreSQL.
All API calls go direct to providers (Gmail, Slack, etc).

App credentials loaded from environment variables.
"""

from __future__ import annotations

import os
from typing import Optional

from loguru import logger

from anytool import AnyTool
from anytool.auth.models import AppCredentials
from server.config import config

_api: Optional[AnyTool] = None


# ── App Credentials from env ─────────────────────────────────────────

# Default scopes per provider (covers all actions in our specs)
_DEFAULT_SCOPES = {
    "google": [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/documents",
        "https://mail.google.com/",
    ],
    "slack": [
        "channels:read",
        "channels:history",
        "chat:write",
        "users:read",
        "users:read.email",
        "reactions:write",
    ],
    "hubspot": [
        "crm.objects.contacts.read",
        "crm.objects.contacts.write",
        "crm.objects.companies.read",
        "crm.objects.companies.write",
        "crm.objects.deals.read",
        "crm.objects.deals.write",
        "crm.objects.owners.read",
    ],
    "github": [
        "repo",
        "read:org",
        "workflow",
    ],
    "docusign": [
        "signature",
        "impersonation",
    ],
}


def _load_app_credentials() -> list[AppCredentials]:
    """Load OAuth credentials from environment variables.

    Pattern:  {APP}_CLIENT_ID, {APP}_CLIENT_SECRET, {APP}_SCOPES (optional)
    Example:  GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET
              SLACK_CLIENT_ID, SLACK_CLIENT_SECRET

    The platform's OAuth callback URL is: {BASE_URL}/v1/connections/callback
    """
    callback_url = f"{config.base_url}{config.api_prefix}/connections/callback"

    credentials = []

    # Google
    google_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    google_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    if google_id and google_secret:
        credentials.append(AppCredentials(
            app="google",
            client_id=google_id,
            client_secret=google_secret,
            scopes=_DEFAULT_SCOPES.get("google", []),
            redirect_uri=callback_url,
        ))

    # Slack
    slack_id = os.environ.get("SLACK_CLIENT_ID", "")
    slack_secret = os.environ.get("SLACK_CLIENT_SECRET", "")
    if slack_id and slack_secret:
        credentials.append(AppCredentials(
            app="slack",
            client_id=slack_id,
            client_secret=slack_secret,
            scopes=_DEFAULT_SCOPES.get("slack", []),
            redirect_uri=callback_url,
        ))

    # HubSpot
    hubspot_id = os.environ.get("HUBSPOT_CLIENT_ID", "")
    hubspot_secret = os.environ.get("HUBSPOT_CLIENT_SECRET", "")
    if hubspot_id and hubspot_secret:
        credentials.append(AppCredentials(
            app="hubspot",
            client_id=hubspot_id,
            client_secret=hubspot_secret,
            scopes=_DEFAULT_SCOPES.get("hubspot", []),
            redirect_uri=callback_url,
        ))

    # GitHub
    github_id = os.environ.get("GITHUB_CLIENT_ID", "")
    github_secret = os.environ.get("GITHUB_CLIENT_SECRET", "")
    if github_id and github_secret:
        credentials.append(AppCredentials(
            app="github",
            client_id=github_id,
            client_secret=github_secret,
            scopes=_DEFAULT_SCOPES.get("github", []),
            redirect_uri=callback_url,
        ))

    # DocuSign
    docusign_id = os.environ.get("DOCUSIGN_CLIENT_ID", "")
    docusign_secret = os.environ.get("DOCUSIGN_CLIENT_SECRET", "")
    if docusign_id and docusign_secret:
        credentials.append(AppCredentials(
            app="docusign",
            client_id=docusign_id,
            client_secret=docusign_secret,
            scopes=_DEFAULT_SCOPES.get("docusign", []),
            redirect_uri=callback_url,
        ))

    # Zendesk (needs subdomain — loaded per-connection)
    # WhatsApp (uses Bearer token, not OAuth — loaded per-connection)
    # Freshdesk (uses API key, not OAuth — loaded per-connection)

    return credentials


def get_api() -> AnyTool:
    """Get the shared AnyTool instance — standalone mode (no Nango)."""
    global _api
    if _api is None:
        from server.token_store import PostgresTokenStore

        store = PostgresTokenStore()
        _api = AnyTool(token_store=store)

        # Register all app credentials from env
        creds = _load_app_credentials()
        for c in creds:
            _api.register_app(c)
            logger.info(f"[engine] Registered app: {c.app} (scopes: {len(c.scopes)})")

        if not creds:
            logger.warning(
                "[engine] No OAuth app credentials found in env. "
                "Set GOOGLE_OAUTH_CLIENT_ID + GOOGLE_OAUTH_CLIENT_SECRET etc."
            )

        logger.info(f"[engine] AnyTool initialized in standalone mode | apps={len(creds)}")

    return _api


async def close_api():
    """Cleanup on shutdown."""
    global _api
    if _api:
        await _api.close()
        _api = None
