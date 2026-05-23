"""
Auth Bridge — connects the existing OAuth layer to the v2 executor.

The existing auth system (oauth.py, token_store.py) handles:
- OAuth flows (authorize URL, callback, token exchange)
- Token storage and encryption
- Token refresh

This bridge converts UserTokens → AuthTokens so the v2 executor can use them.

    from anytool.core.auth_bridge import AuthBridge

    bridge = AuthBridge(oauth_manager, credentials)
    auth = await bridge.get_auth("google", "user-123")
    result = await executor.execute(spec, body, auth)
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from anytool.core.executor import AuthTokens
from anytool.auth.models import AppCredentials, UserTokens
from anytool.auth.oauth import OAuthManager
from anytool.auth.token_store import TokenStore


class AuthBridge:
    """Bridges the existing OAuth system to v2 AuthTokens.

    Handles token retrieval, refresh, and conversion.
    """

    def __init__(
        self,
        oauth_manager: OAuthManager,
        credentials: dict[str, AppCredentials],
    ):
        self._oauth = oauth_manager
        self._credentials = credentials

    async def get_auth(self, app: str, user_id: str) -> AuthTokens:
        """Get valid auth tokens for a user, ready for the executor.

        Automatically refreshes expired OAuth tokens.
        Converts UserTokens → AuthTokens with metadata.
        """
        creds = self._credentials.get(app)
        if not creds:
            raise ValueError(
                f"No credentials for app '{app}'. "
                f"Registered: {list(self._credentials.keys())}"
            )

        # Get valid tokens (auto-refreshes if expired)
        tokens = await self._oauth.get_valid_tokens(creds, user_id)

        # Convert to v2 AuthTokens
        return self._convert(tokens)

    def _convert(self, tokens: UserTokens) -> AuthTokens:
        """Convert UserTokens (v1) → AuthTokens (v2)."""
        return AuthTokens(
            access_token=tokens.access_token,
            token_type=tokens.token_type,
            api_key=tokens.api_key,
            domain=tokens.domain,
            metadata={
                # Pass through all provider metadata
                # (DocuSign account_id, Slack team_id, user email, etc.)
                **tokens.metadata,
                # Also include domain for Freshdesk/Zendesk
                **({"domain": tokens.domain} if tokens.domain else {}),
                **({"subdomain": tokens.domain} if tokens.domain else {}),
            },
        )

    async def is_connected(self, app: str, user_id: str) -> bool:
        """Check if a user has valid tokens for an app."""
        store = self._oauth._store
        tokens = await store.get_tokens(app, user_id)
        return tokens is not None
