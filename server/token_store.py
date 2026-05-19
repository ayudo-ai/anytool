"""
PostgresTokenStore — encrypted OAuth token storage using the platform's DB.

Tokens are encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256).
Uses the same meta_record table as everything else.

Object types used:
  - oauth_token: stores encrypted UserTokens (keyed by "app:user_id")
  - oauth_state: stores transient CSRF state (keyed by state string)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List, Optional

from cryptography.fernet import Fernet
from loguru import logger

from anytool.auth.models import UserTokens, OAuthState
from anytool.auth.token_store import TokenStore
from server.database import (
    put_record, get_record, delete_record, list_records,
    async_session, MetaRecord,
)
from sqlalchemy import select


def _get_fernet() -> Fernet:
    """Get the Fernet encryption key from env.

    If ANYTOOL_TOKEN_KEY is not set, generate one and warn.
    In production, set this to a stable 32-byte base64 key.
    Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    key = os.environ.get("ANYTOOL_TOKEN_KEY", "")
    if not key:
        # Auto-generate for dev — tokens won't survive server restart!
        key = Fernet.generate_key().decode()
        os.environ["ANYTOOL_TOKEN_KEY"] = key
        logger.warning(
            "[token_store] No ANYTOOL_TOKEN_KEY set — using ephemeral key. "
            "Tokens will be lost on restart. Set a stable key in .env for production."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


_fernet: Optional[Fernet] = None


def _get_cipher() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = _get_fernet()
    return _fernet


def _encrypt(data: str) -> str:
    return _get_cipher().encrypt(data.encode()).decode()


def _decrypt(data: str) -> str:
    return _get_cipher().decrypt(data.encode()).decode()


class PostgresTokenStore(TokenStore):
    """Encrypted token store backed by PostgreSQL meta_record table."""

    # ── Tokens ───────────────────────────────────────────────────────

    async def save_tokens(self, tokens: UserTokens) -> None:
        """Save tokens encrypted in DB. Keyed by 'app:user_id'."""
        key = f"{tokens.app}:{tokens.user_id}"

        # Serialize to JSON, then encrypt
        token_json = tokens.model_dump_json()
        encrypted = _encrypt(token_json)

        await put_record(
            object_slug="oauth_token",
            primary_key=key,
            data={"encrypted": encrypted},
        )

    async def get_tokens(self, app: str, user_id: str) -> Optional[UserTokens]:
        """Get decrypted tokens for a user+app."""
        key = f"{app}:{user_id}"
        record = await get_record("oauth_token", key)
        if not record:
            return None

        data = record.custom_data or {}
        encrypted = data.get("encrypted", "")
        if not encrypted:
            return None

        try:
            decrypted = _decrypt(encrypted)
            return UserTokens.model_validate_json(decrypted)
        except Exception as e:
            logger.error(f"[token_store] Decrypt failed for {key}: {e}")
            return None

    async def delete_tokens(self, app: str, user_id: str) -> None:
        """Delete tokens (disconnect)."""
        key = f"{app}:{user_id}"
        await delete_record("oauth_token", key)

    async def list_connected(self, user_id: str) -> list[UserTokens]:
        """List all connected apps for a user."""
        # Query all oauth_token records where primary_key ends with :user_id
        async with async_session() as session:
            result = await session.execute(
                select(MetaRecord).where(
                    MetaRecord.object_slug == "oauth_token",
                    MetaRecord.primary_field_value.like(f"%:{user_id}"),
                    MetaRecord.is_deleted.is_(False),
                )
            )
            records = result.scalars().all()

        tokens = []
        for record in records:
            data = record.custom_data or {}
            encrypted = data.get("encrypted", "")
            if not encrypted:
                continue
            try:
                decrypted = _decrypt(encrypted)
                tokens.append(UserTokens.model_validate_json(decrypted))
            except Exception:
                continue

        return tokens

    # ── OAuth State (transient CSRF) ─────────────────────────────────

    async def save_oauth_state(self, state: OAuthState) -> None:
        """Save OAuth state during authorization flow."""
        await put_record(
            object_slug="oauth_state",
            primary_key=state.state,
            data={
                "app": state.app,
                "user_id": state.user_id,
                "redirect_uri": state.redirect_uri,
                "scopes": state.scopes,
                "account_id": state.account_id,
                "workspace_id": state.workspace_id,
                "created_at": state.created_at.isoformat(),
            },
        )

    async def get_oauth_state(self, state_key: str) -> Optional[OAuthState]:
        """Retrieve and consume OAuth state (one-time use)."""
        record = await get_record("oauth_state", state_key)
        if not record:
            return None

        # Delete after reading (one-time use)
        await delete_record("oauth_state", state_key)

        data = record.custom_data or {}
        return OAuthState(
            app=data.get("app", ""),
            user_id=data.get("user_id", ""),
            state=state_key,
            redirect_uri=data.get("redirect_uri", ""),
            scopes=data.get("scopes", []),
            account_id=data.get("account_id", ""),
            workspace_id=data.get("workspace_id", ""),
        )
