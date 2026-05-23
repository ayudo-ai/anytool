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
class AuthField:
    """A field the user must fill to connect (for API key providers)."""
    name: str          # field key: "domain", "api_key"
    label: str         # display: "Subdomain", "API Key"
    placeholder: str   # hint: "yourcompany"
    type: str = "text"  # "text" | "password"
    required: bool = True
    help_text: str = ""  # extra hint shown below the field
    suffix: str = ""    # appended to display: ".freshdesk.com"


@dataclass
class AppConfig:
    """Configuration for an OAuth provider."""

    name: str  # Human name: "Google", "Slack"
    slug: str  # Machine name: "google", "slack"

    # Auth type: "oauth2" (default) or "api_key"
    auth_type: str = "oauth2"

    # Fields the user must fill to connect (for api_key auth)
    auth_fields: list = field(default_factory=list)  # List[AuthField]

    # OAuth endpoints
    authorize_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""  # Optional: fetch user email/name after auth

    # OAuth behavior
    scope_separator: str = " "  # Google/Microsoft use space, Slack uses comma
    extra_auth_params: Dict[str, str] = field(default_factory=dict)

    # User scopes (Slack-specific: sent as user_scope param, returns user token)
    user_scopes: list = field(default_factory=list)

    # Token extraction: which field to use as access_token from OAuth response
    # Default: "access_token". Slack user mode: "authed_user.access_token"
    token_path: str = "access_token"

    # API base URL (for constructing API calls)
    api_base_url: str = ""

    # Icon URL for UI display
    icon_url: str = ""

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
        icon_url="app_icons/app_OQYhq7.png",  # Gmail icon (primary Google icon)
        extra_auth_params={
            "access_type": "offline",  # Gets refresh_token
            "prompt": "consent",  # Forces consent screen → ensures refresh_token
        },
        _extract_userinfo=_google_userinfo,
    ),
    "freshdesk": AppConfig(
        name="Freshdesk",
        slug="freshdesk",
        auth_type="api_key",
        auth_fields=[
            AuthField(
                name="domain",
                label="Subdomain",
                placeholder="yourcompany",
                suffix=".freshdesk.com",
                help_text="Just the subdomain — not the full URL",
            ),
            AuthField(
                name="api_key",
                label="API Key",
                placeholder="Your Freshdesk API key",
                type="password",
                help_text="Profile Settings → Your API Key",
            ),
        ],
        api_base_url="https://{domain}.freshdesk.com",
        icon_url="app_icons/app_1Nohev.png",
    ),
    "docusign": AppConfig(
        name="DocuSign",
        slug="docusign",
        authorize_url="https://account-d.docusign.com/oauth/auth",
        token_url="https://account-d.docusign.com/oauth/token",
        userinfo_url="https://account-d.docusign.com/oauth/userinfo",
        api_base_url="https://demo.docusign.net",
        icon_url="app_icons/app_mE7hLb.png",
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
        # Request user scopes so we get a user token (messages appear as the user)
        user_scopes=[
            "channels:read", "channels:history", "chat:write",
            "users:read", "users:read.email", "reactions:write",
        ],
        token_path="authed_user.access_token",
        icon_url="app_icons/app_OkrhR1.png",
    ),
    "whatsapp": AppConfig(
        name="WhatsApp Business",
        slug="whatsapp",
        auth_type="api_key",
        auth_fields=[
            AuthField(
                name="api_key",
                label="Access Token",
                placeholder="Your WhatsApp Business API access token",
                type="password",
                help_text="Meta Business Suite → WhatsApp → API Setup",
            ),
            AuthField(
                name="domain",
                label="Phone Number ID",
                placeholder="1234567890",
                help_text="The phone number ID from your WhatsApp Business account",
            ),
        ],
        api_base_url="https://graph.facebook.com/v21.0",
        icon_url="app_icons/app_mWnhY4.png",
    ),
    "zendesk": AppConfig(
        name="Zendesk",
        slug="zendesk",
        auth_type="api_key",
        auth_fields=[
            AuthField(
                name="domain",
                label="Subdomain",
                placeholder="yourcompany",
                suffix=".zendesk.com",
                help_text="Just the subdomain — not the full URL",
            ),
            AuthField(
                name="api_key",
                label="API Key",
                placeholder="Your Zendesk API key",
                type="password",
                help_text="Admin → Channels → API → Add API Token",
            ),
        ],
        authorize_url="https://{subdomain}.zendesk.com/oauth/authorizations/new",
        token_url="https://{subdomain}.zendesk.com/oauth/tokens",
        api_base_url="https://{subdomain}.zendesk.com",
        scope_separator=" ",
        icon_url="app_icons/app_1pbhGX.png",
    ),
    "github": AppConfig(
        name="GitHub",
        slug="github",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        api_base_url="https://api.github.com",
        scope_separator=" ",
        icon_url="app_icons/app_OrZhaO.png",
    ),
    "hubspot": AppConfig(
        name="HubSpot",
        slug="hubspot",
        authorize_url="https://app.hubspot.com/oauth/authorize",
        token_url="https://api.hubapi.com/oauth/v1/token",
        api_base_url="https://api.hubapi.com",
        scope_separator=" ",
        icon_url="app_icons/app_OkrhlP.svg",
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


# Sub-app icons (Google services have separate icons)
SUB_APP_ICONS: Dict[str, str] = {
    "gmail": "app_icons/app_OQYhq7.png",
    "google_drive": "app_icons/app_1lxhk1.png",
    "google_sheets": "app_icons/app_168hvn.png",
    "google_calendar": "app_icons/app_13Gh2V.png",
    "google_docs": "app_icons/app_1pbh98.png",
}


def get_icon_path(app: str, sub_app: str = "") -> str:
    """Get the icon path for an app or sub-app.

    Args:
        app: Provider name (e.g. 'google', 'slack')
        sub_app: Optional sub-app (e.g. 'gmail', 'google_drive')

    Returns:
        Icon path relative to CDN root (e.g. 'app_icons/app_OQYhq7.png')
    """
    if sub_app and sub_app in SUB_APP_ICONS:
        return SUB_APP_ICONS[sub_app]
    config = APPS.get(app)
    return config.icon_url if config else ""


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
