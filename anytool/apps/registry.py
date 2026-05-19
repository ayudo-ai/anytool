"""
App Registry — provider-specific OAuth config and metadata extraction.

Each app has ONE entry here. No per-action wrappers. Just:
- OAuth URLs and params
- How to extract metadata from token response
- Scope separator
- Base URL for API calls

Adding a new app = adding one AppConfig entry. That's it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class AppConfig:
    """Configuration for an OAuth provider."""

    name: str  # Human name: "Google", "Slack"
    slug: str  # Machine name: "google", "slack"

    # OAuth endpoints
    authorize_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""  # Optional: fetch user email/name after auth

    # OAuth behavior
    scope_separator: str = " "  # Google/Microsoft use space, Slack uses comma
    extra_auth_params: Dict[str, str] = field(default_factory=dict)

    # API base URL (for constructing API calls)
    api_base_url: str = ""

    # Functions to extract metadata from token/userinfo responses
    _extract_metadata: Optional[Callable[[dict], dict]] = None
    _extract_userinfo: Optional[Callable[[dict], dict]] = None

    def extract_metadata(self, token_response: dict) -> dict:
        if self._extract_metadata:
            return self._extract_metadata(token_response)
        return {}

    def extract_userinfo(self, userinfo_response: dict) -> dict:
        if self._extract_userinfo:
            return self._extract_userinfo(userinfo_response)
        return {}


# ── Provider Configs ─────────────────────────────────────────────────


def _google_userinfo(resp: dict) -> dict:
    return {
        "email": resp.get("email", ""),
        "name": resp.get("name", ""),
        "picture": resp.get("picture", ""),
    }


def _docusign_metadata(token_resp: dict) -> dict:
    """DocuSign includes account info in token response or requires userinfo call."""
    return {}


def _docusign_userinfo(resp: dict) -> dict:
    accounts = resp.get("accounts", [])
    default = next((a for a in accounts if a.get("is_default")), accounts[0] if accounts else {})
    return {
        "account_id": default.get("account_id", ""),
        "account_name": default.get("account_name", ""),
        "base_uri": default.get("base_uri", ""),
    }


def _slack_metadata(token_resp: dict) -> dict:
    return {
        "team_id": token_resp.get("team", {}).get("id", ""),
        "team_name": token_resp.get("team", {}).get("name", ""),
        "bot_user_id": token_resp.get("bot_user_id", ""),
        "authed_user_id": token_resp.get("authed_user", {}).get("id", ""),
    }


# ── Registry ─────────────────────────────────────────────────────────

APPS: Dict[str, AppConfig] = {
    "google": AppConfig(
        name="Google",
        slug="google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://www.googleapis.com/oauth2/v2/userinfo",
        api_base_url="https://www.googleapis.com",
        extra_auth_params={
            "access_type": "offline",  # Gets refresh_token
            "prompt": "consent",  # Forces consent screen → ensures refresh_token
        },
        _extract_userinfo=_google_userinfo,
    ),
    "freshdesk": AppConfig(
        name="Freshdesk",
        slug="freshdesk",
        api_base_url="https://{domain}/api/v2",  # domain filled at runtime
        # No OAuth — uses API key auth
    ),
    "docusign": AppConfig(
        name="DocuSign",
        slug="docusign",
        authorize_url="https://account-d.docusign.com/oauth/auth",  # demo; prod is account.docusign.com
        token_url="https://account-d.docusign.com/oauth/token",
        userinfo_url="https://account-d.docusign.com/oauth/userinfo",
        api_base_url="https://demo.docusign.net",  # Nango needs base without /restapi/v2.1
        _extract_metadata=_docusign_metadata,
        _extract_userinfo=_docusign_userinfo,
    ),
    "slack": AppConfig(
        name="Slack",
        slug="slack",
        authorize_url="https://slack.com/oauth/v2/authorize",
        token_url="https://slack.com/api/oauth.v2.access",
        scope_separator=",",
        api_base_url="https://slack.com/api",
        _extract_metadata=_slack_metadata,
    ),
    "zendesk": AppConfig(
        name="Zendesk",
        slug="zendesk",
        authorize_url="https://{subdomain}.zendesk.com/oauth/authorizations/new",
        token_url="https://{subdomain}.zendesk.com/oauth/tokens",
        api_base_url="https://{subdomain}.zendesk.com",  # subdomain from connection config
        scope_separator=" ",
    ),
    "github": AppConfig(
        name="GitHub",
        slug="github",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        api_base_url="https://api.github.com",
        scope_separator=" ",
    ),
    "hubspot": AppConfig(
        name="HubSpot",
        slug="hubspot",
        authorize_url="https://app.hubspot.com/oauth/authorize",
        token_url="https://api.hubapi.com/oauth/v1/token",
        api_base_url="https://api.hubapi.com",
        scope_separator=" ",
    ),
    "microsoft": AppConfig(
        name="Microsoft",
        slug="microsoft",
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        userinfo_url="https://graph.microsoft.com/v1.0/me",
        api_base_url="https://graph.microsoft.com/v1.0",
        scope_separator=" ",
    ),
}


def get_app_config(app: str) -> AppConfig:
    """Get config for an app. Raises KeyError if not registered."""
    if app not in APPS:
        raise KeyError(
            f"Unknown app '{app}'. Available: {list(APPS.keys())}. "
            f"Register new apps in anytool/apps/registry.py"
        )
    return APPS[app]


def register_app(config: AppConfig) -> None:
    """Register a custom app at runtime."""
    APPS[config.slug] = config
