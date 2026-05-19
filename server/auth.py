"""
API key authentication — resolves key → account + workspace.

Auth chain:
  Authorization: Bearer at_xxxx
    → lookup api_key record
    → extract account_id + workspace_id
    → return AuthContext

All routes get AuthContext via Depends(get_auth_context).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from fastapi import Header, HTTPException

from server.database import get_record, list_records


@dataclass
class AuthContext:
    """Resolved auth context from API key."""
    account_id: str
    workspace_id: str
    plan: str
    limits: Dict[str, int]


PLAN_LIMITS = {
    "free": {"max_calls": 1000, "max_connections": 10, "max_triggers": 5},
    "pro": {"max_calls": 100_000, "max_connections": 100, "max_triggers": 50},
    "enterprise": {"max_calls": -1, "max_connections": -1, "max_triggers": -1},
}


async def get_auth_context(authorization: str = Header(...)) -> AuthContext:
    """Extract and validate API key → return AuthContext.

    Usage:
        @router.post("/execute")
        async def execute(ctx: AuthContext = Depends(get_auth_context)):
            # ctx.account_id, ctx.workspace_id, ctx.plan, ctx.limits
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header. Use: Bearer at_xxxx")

    api_key = authorization[7:].strip()

    if not api_key.startswith("at_"):
        raise HTTPException(401, "Invalid API key format. Keys start with 'at_'")

    # Lookup API key → get account_id + workspace_id
    key_record = await get_record("api_key", api_key)
    if not key_record:
        raise HTTPException(401, "Invalid or inactive API key")

    key_data = key_record.custom_data or {}
    if not key_data.get("is_active", True) is True:
        raise HTTPException(401, "API key is deactivated")

    account_id = key_record.account_id or ""
    workspace_id = key_record.workspace_id or ""

    if not account_id:
        raise HTTPException(401, "API key not linked to an account")

    # Get plan from account
    account_record = await get_record("account", account_id)
    plan = (account_record.custom_data or {}).get("plan", "free") if account_record else "free"
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

    return AuthContext(
        account_id=account_id,
        workspace_id=workspace_id,
        plan=plan,
        limits=limits,
    )
