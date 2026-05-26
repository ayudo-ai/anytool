"""
API authentication — resolves Bearer token → account + workspace.

Supports two token types:
  - API key (at_xxxx):     for SDK/API access
  - Session token (sess_xxxx): for dashboard access

Both resolve to the same AuthContext.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict

from fastapi import Header, HTTPException

from server.database import get_record, list_records


@dataclass
class AuthContext:
    """Resolved auth context from API key or session token."""
    account_id: str
    workspace_id: str
    plan: str
    limits: Dict[str, int]


PLAN_LIMITS = {
    "free": {"max_calls": -1, "max_connections": -1, "max_triggers": -1},
    "pro": {"max_calls": -1, "max_connections": -1, "max_triggers": -1},
    "enterprise": {"max_calls": -1, "max_connections": -1, "max_triggers": -1},
}


async def get_auth_context(authorization: str = Header(...)) -> AuthContext:
    """Extract and validate token → return AuthContext.

    Accepts both API keys (at_xxxx) and session tokens (sess_xxxx).
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header. Use: Bearer <token>")

    token = authorization[7:].strip()

    if token.startswith("sess_"):
        return await _resolve_session(token)
    elif token.startswith("at_"):
        return await _resolve_api_key(token)
    else:
        raise HTTPException(401, "Invalid token format. Use API key (at_xxx) or session (sess_xxx)")


async def _resolve_api_key(api_key: str) -> AuthContext:
    """Resolve an API key to AuthContext."""
    key_record = await get_record("api_key", api_key)
    if not key_record:
        raise HTTPException(401, "Invalid or inactive API key")

    key_data = key_record.custom_data or {}
    if not key_data.get("is_active", True):
        raise HTTPException(401, "API key is deactivated")

    account_id = key_record.account_id or ""
    workspace_id = key_record.workspace_id or ""

    if not account_id:
        raise HTTPException(401, "API key not linked to an account")

    plan, limits = await _get_plan(account_id)

    return AuthContext(
        account_id=account_id,
        workspace_id=workspace_id,
        plan=plan,
        limits=limits,
    )


async def _resolve_session(session_token: str) -> AuthContext:
    """Resolve a session token to AuthContext."""
    session = await get_record("session", session_token)
    if not session:
        raise HTTPException(401, "Invalid or expired session")

    session_data = session.custom_data or {}

    # Check expiry
    expires_at = session_data.get("expires_at", "")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if datetime.now(timezone.utc) > exp:
                raise HTTPException(401, "Session expired. Please sign in again.")
        except (ValueError, TypeError):
            pass

    account_id = session.account_id or ""
    workspace_id = session.workspace_id or ""

    if not account_id:
        raise HTTPException(401, "Session not linked to an account")

    plan, limits = await _get_plan(account_id)

    return AuthContext(
        account_id=account_id,
        workspace_id=workspace_id,
        plan=plan,
        limits=limits,
    )


async def _get_plan(account_id: str) -> tuple[str, Dict[str, int]]:
    """Get plan and limits for an account."""
    account_record = await get_record("account", account_id)
    plan = (account_record.custom_data or {}).get("plan", "free") if account_record else "free"
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    return plan, limits
