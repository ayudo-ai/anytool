"""
API key authentication — validates Bearer token against records table.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import Header, HTTPException

from server.database import get_record


async def get_account(authorization: str = Header(...)) -> Dict[str, Any]:
    """Extract and validate API key from Authorization header.

    Returns the account data dict.

    Usage in routes:
        @router.post("/execute")
        async def execute(account: dict = Depends(get_account)):
            account_id = account["id"]
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header. Use: Bearer at_xxxx")

    api_key = authorization[7:].strip()

    if not api_key.startswith("at_"):
        raise HTTPException(401, "Invalid API key format. Keys start with 'at_'")

    record = await get_record("account", api_key)

    if not record:
        raise HTTPException(401, "Invalid or inactive API key")

    data = record.data or {}
    data["id"] = record.id
    data["api_key"] = record.key

    # Check usage limits
    plan_limits = {
        "free": {"max_calls": 1000, "max_connections": 10, "max_triggers": 5},
        "pro": {"max_calls": 100_000, "max_connections": 100, "max_triggers": 50},
        "enterprise": {"max_calls": -1, "max_connections": -1, "max_triggers": -1},
    }
    plan = data.get("plan", "free")
    limits = plan_limits.get(plan, plan_limits["free"])
    data["limits"] = limits

    return data
