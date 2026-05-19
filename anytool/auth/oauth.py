"""
OAuth2 flow manager — handles authorization URL generation,
token exchange, and token refresh.

Provider-specific quirks are handled by the app registry,
not by if/else chains here.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from loguru import logger

from anytool.auth.models import AppCredentials, OAuthState, UserTokens
from anytool.auth.token_store import TokenStore
from anytool.apps.registry import get_app_config


class OAuthManager:
    """Manages OAuth2 flows for all providers."""

    def __init__(self, token_store: TokenStore):
        self._store = token_store
        self._http = httpx.AsyncClient(timeout=30.0)

    async def get_auth_url(
        self,
        credentials: AppCredentials,
        user_id: str,
        extra_scopes: Optional[list[str]] = None,
        account_id: str = "",
        workspace_id: str = "",
    ) -> str:
        """Generate the OAuth authorization URL for a user to click.

        Returns the URL to redirect the user to for OAuth consent.
        """
        app_config = get_app_config(credentials.app)

        authorize_url = credentials.authorize_url or app_config.authorize_url
        scopes = list(set(credentials.scopes + (extra_scopes or [])))

        state = secrets.token_urlsafe(32)

        # Save state for CSRF verification on callback
        await self._store.save_oauth_state(OAuthState(
            app=credentials.app,
            user_id=user_id,
            state=state,
            redirect_uri=credentials.redirect_uri,
            scopes=scopes,
            account_id=account_id,
            workspace_id=workspace_id,
        ))

        params = {
            "client_id": credentials.client_id,
            "redirect_uri": credentials.redirect_uri,
            "response_type": "code",
            "scope": app_config.scope_separator.join(scopes),
            "state": state,
            **app_config.extra_auth_params,
        }

        url = f"{authorize_url}?{urlencode(params)}"
        logger.info(f"[anytool.oauth] Auth URL generated | app={credentials.app} user={user_id}")
        return url

    async def handle_callback(
        self,
        credentials: AppCredentials,
        code: str,
        state: str,
    ) -> UserTokens:
        """Exchange authorization code for tokens after OAuth callback.

        Call this when the user is redirected back to your callback URL.
        """
        # Verify state
        oauth_state = await self._store.get_oauth_state(state)
        if not oauth_state:
            raise ValueError("Invalid or expired OAuth state. Possible CSRF attack.")

        if oauth_state.app != credentials.app:
            raise ValueError(f"State app mismatch: expected {credentials.app}, got {oauth_state.app}")

        app_config = get_app_config(credentials.app)
        token_url = credentials.token_url or app_config.token_url

        # Exchange code for tokens
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": oauth_state.redirect_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
        }

        resp = await self._http.post(
            token_url,
            data=token_data,
            headers={"Accept": "application/json"},
        )

        if not resp.is_success:
            logger.error(f"[anytool.oauth] Token exchange failed | app={credentials.app} | {resp.status_code} | {resp.text[:300]}")
            raise ValueError(f"Token exchange failed: {resp.status_code} — {resp.text[:300]}")

        token_resp = resp.json()

        # Calculate expiry
        expires_in = token_resp.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Build tokens
        tokens = UserTokens(
            app=credentials.app,
            user_id=oauth_state.user_id,
            access_token=token_resp["access_token"],
            refresh_token=token_resp.get("refresh_token", ""),
            token_type=token_resp.get("token_type", "Bearer"),
            expires_at=expires_at,
            scopes=oauth_state.scopes,
            metadata=app_config.extract_metadata(token_resp),
        )

        # Fetch additional metadata if provider supports it (e.g. Google userinfo)
        if app_config.userinfo_url:
            try:
                userinfo = await self._http.get(
                    app_config.userinfo_url,
                    headers={"Authorization": f"Bearer {tokens.access_token}"},
                )
                if userinfo.is_success:
                    extra_meta = app_config.extract_userinfo(userinfo.json())
                    tokens.metadata.update(extra_meta)
            except Exception as e:
                logger.warning(f"[anytool.oauth] Userinfo fetch failed: {e}")

        # Save tokens
        await self._store.save_tokens(tokens)

        logger.info(
            f"[anytool.oauth] Tokens saved | app={credentials.app} "
            f"user={oauth_state.user_id} expires_in={expires_in}s"
        )
        return tokens

    async def refresh_if_needed(
        self,
        credentials: AppCredentials,
        tokens: UserTokens,
    ) -> UserTokens:
        """Refresh tokens if expired. Returns updated tokens (or original if still valid)."""
        if not tokens.is_expired:
            return tokens

        if not tokens.refresh_token:
            raise ValueError(
                f"Token expired for {tokens.app}:{tokens.user_id} and no refresh_token available. "
                f"User must re-authorize."
            )

        app_config = get_app_config(credentials.app)
        token_url = credentials.token_url or app_config.token_url

        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": tokens.refresh_token,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
        }

        resp = await self._http.post(
            token_url,
            data=refresh_data,
            headers={"Accept": "application/json"},
        )

        if not resp.is_success:
            logger.error(
                f"[anytool.oauth] Refresh failed | app={tokens.app} "
                f"user={tokens.user_id} | {resp.status_code}"
            )
            raise ValueError(f"Token refresh failed: {resp.status_code} — {resp.text[:300]}")

        token_resp = resp.json()
        expires_in = token_resp.get("expires_in", 3600)

        # Update tokens (keep existing refresh_token if new one not provided)
        tokens.access_token = token_resp["access_token"]
        tokens.refresh_token = token_resp.get("refresh_token", tokens.refresh_token)
        tokens.token_type = token_resp.get("token_type", tokens.token_type)
        tokens.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        tokens.updated_at = datetime.now(timezone.utc)

        await self._store.save_tokens(tokens)

        logger.info(
            f"[anytool.oauth] Refreshed | app={tokens.app} "
            f"user={tokens.user_id} expires_in={expires_in}s"
        )
        return tokens

    async def get_valid_tokens(
        self,
        credentials: AppCredentials,
        user_id: str,
    ) -> UserTokens:
        """Get valid (non-expired) tokens for a user. Auto-refreshes if needed."""
        tokens = await self._store.get_tokens(credentials.app, user_id)
        if not tokens:
            raise ValueError(
                f"No tokens found for {credentials.app}:{user_id}. "
                f"User must authorize first."
            )

        # API key auth — never expires
        if tokens.api_key:
            return tokens

        # OAuth — refresh if needed
        return await self.refresh_if_needed(credentials, tokens)

    async def disconnect(self, app: str, user_id: str) -> None:
        """Disconnect an app (delete tokens)."""
        await self._store.delete_tokens(app, user_id)
        logger.info(f"[anytool.oauth] Disconnected | app={app} user={user_id}")

    async def close(self):
        """Close the HTTP client."""
        await self._http.aclose()
