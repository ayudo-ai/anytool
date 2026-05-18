"""
Token Store — abstract interface + in-memory implementation.

Pluggable storage for OAuth tokens. Implement TokenStore for your DB.
Ships with MemoryTokenStore for testing.
"""

from __future__ import annotations

import abc
from typing import Dict, Optional, Tuple

from anyapi.auth.models import UserTokens, OAuthState


class TokenStore(abc.ABC):
    """Abstract token store. Implement this for your database.

    Example for SQLAlchemy / PostgreSQL:

        class PostgresTokenStore(TokenStore):
            async def save_tokens(self, tokens: UserTokens) -> None:
                record = await db.get(OAuthToken, (tokens.app, tokens.user_id))
                if record:
                    record.data = tokens.model_dump()
                else:
                    db.add(OAuthToken(app=tokens.app, user_id=tokens.user_id, data=tokens.model_dump()))
                await db.commit()

            async def get_tokens(self, app: str, user_id: str) -> Optional[UserTokens]:
                record = await db.get(OAuthToken, (app, user_id))
                return UserTokens(**record.data) if record else None
    """

    @abc.abstractmethod
    async def save_tokens(self, tokens: UserTokens) -> None:
        """Save or update tokens for a user+app."""
        ...

    @abc.abstractmethod
    async def get_tokens(self, app: str, user_id: str) -> Optional[UserTokens]:
        """Get tokens for a user+app. Returns None if not connected."""
        ...

    @abc.abstractmethod
    async def delete_tokens(self, app: str, user_id: str) -> None:
        """Delete tokens (disconnect an app)."""
        ...

    @abc.abstractmethod
    async def list_connected(self, user_id: str) -> list[UserTokens]:
        """List all connected apps for a user."""
        ...

    # OAuth state (transient, for CSRF protection during OAuth flow)

    @abc.abstractmethod
    async def save_oauth_state(self, state: OAuthState) -> None:
        """Save OAuth state during the authorization flow."""
        ...

    @abc.abstractmethod
    async def get_oauth_state(self, state_key: str) -> Optional[OAuthState]:
        """Retrieve and consume OAuth state (one-time use)."""
        ...


class MemoryTokenStore(TokenStore):
    """In-memory token store for testing and development."""

    def __init__(self):
        self._tokens: Dict[Tuple[str, str], UserTokens] = {}
        self._states: Dict[str, OAuthState] = {}

    async def save_tokens(self, tokens: UserTokens) -> None:
        self._tokens[(tokens.app, tokens.user_id)] = tokens

    async def get_tokens(self, app: str, user_id: str) -> Optional[UserTokens]:
        return self._tokens.get((app, user_id))

    async def delete_tokens(self, app: str, user_id: str) -> None:
        self._tokens.pop((app, user_id), None)

    async def list_connected(self, user_id: str) -> list[UserTokens]:
        return [t for t in self._tokens.values() if t.user_id == user_id]

    async def save_oauth_state(self, state: OAuthState) -> None:
        self._states[state.state] = state

    async def get_oauth_state(self, state_key: str) -> Optional[OAuthState]:
        return self._states.pop(state_key, None)
