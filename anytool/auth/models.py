"""
Auth data models — credentials, tokens, OAuth state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AppCredentials(BaseModel):
    """OAuth credentials for an app (set once by the developer).

    Example:
        AppCredentials(
            app="google",
            client_id="xxx.apps.googleusercontent.com",
            client_secret="GOCSPX-xxx",
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
    """

    app: str  # "google", "slack", "docusign", "freshdesk"
    auth_type: str = "oauth2"  # "oauth2" | "api_key"

    # OAuth2
    client_id: str = ""
    client_secret: str = ""
    scopes: List[str] = Field(default_factory=list)
    authorize_url: str = ""  # auto-filled from app registry if empty
    token_url: str = ""  # auto-filled from app registry if empty
    redirect_uri: str = "http://localhost:8000/oauth/callback"

    # API Key (e.g. Freshdesk)
    api_key: str = ""
    domain: str = ""  # e.g. "yourcompany.freshdesk.com"

    # Extra provider-specific config
    extra: Dict[str, Any] = Field(default_factory=dict)


class UserTokens(BaseModel):
    """OAuth tokens for a specific user/workspace.

    Stored encrypted in the token store. Auto-refreshed when expired.
    """

    app: str
    user_id: str  # workspace_id or user identifier

    # OAuth2 tokens
    access_token: str = ""
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scopes: List[str] = Field(default_factory=list)

    # API Key (for simple auth apps like Freshdesk)
    api_key: str = ""
    domain: str = ""

    # Provider-specific data (e.g. DocuSign account_id, Google user email)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Internal
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        # Expire 5 minutes early to avoid race conditions
        from datetime import timedelta

        buffer = timedelta(minutes=5)
        return datetime.now(timezone.utc) >= (self.expires_at - buffer)

    @property
    def auth_header(self) -> str:
        """Returns the Authorization header value."""
        if self.api_key:
            # Freshdesk/Zendesk use Basic auth: base64(api_key:X)
            import base64
            encoded = base64.b64encode(f"{self.api_key}:X".encode()).decode()
            return f"Basic {encoded}"
        # Always use "Bearer" — some providers return non-standard token_type
        # (e.g. Slack returns "bot") but all accept Bearer
        return f"Bearer {self.access_token}"


class OAuthState(BaseModel):
    """Transient state during OAuth flow."""

    app: str
    user_id: str
    state: str  # CSRF token
    redirect_uri: str
    scopes: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Platform context — set by server when initiating OAuth
    account_id: str = ""
    workspace_id: str = ""
