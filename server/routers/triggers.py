"""
Trigger management — per user_id, each with its own webhook_url.

A user can have multiple triggers, each pointing to a different webhook.
Triggers poll for events and POST to the specified webhook_url.

POST   /v1/triggers       → deploy trigger for a user
GET    /v1/triggers       → list triggers (filter by user_id)
DELETE /v1/triggers/{id}  → remove a trigger
GET    /v1/triggers/types → list available trigger types
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_auth_context, AuthContext
from server.database import (
    put_record, get_record, list_records, delete_record, new_id,
)
from server.trigger_engine import get_trigger_engine

router = APIRouter(prefix="/triggers", tags=["triggers"])


# ── Supported triggers ───────────────────────────────────────────────

TRIGGER_MAP = {
    "gmail_new_message": {"trigger_type": "gmail_new_message", "provider": "google"},
    "gmail_new_email": {"trigger_type": "gmail_new_message", "provider": "google"},
}


class DeployTriggerRequest(BaseModel):
    trigger_type: str                   # gmail_new_message
    user_id: str                        # end-user whose connection to poll
    webhook_url: str                    # where to POST events (unique per trigger)
    filters: Dict[str, Any] = {}       # from_contains, subject_contains, etc.
    poll_interval_seconds: int = 90


# ── Routes ───────────────────────────────────────────────────────────

@router.post("")
async def deploy_trigger(body: DeployTriggerRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Deploy a trigger for a user with a specific webhook URL.

    Each trigger polls independently and delivers events to its own webhook_url.
    A single user can have multiple triggers — e.g., one for inbox alerts,
    another for invoice detection, each going to different webhooks.

    Example:
        POST /v1/triggers
        {
            "trigger_type": "gmail_new_message",
            "user_id": "customer-123",
            "webhook_url": "https://myapp.com/webhooks/inbox-alerts",
            "filters": {"from_contains": "vendor@example.com"},
            "poll_interval_seconds": 60
        }
    """
    # Check trigger limit per workspace
    existing = await list_records("trigger", account_id=ctx.account_id, workspace_id=ctx.workspace_id)
    max_triggers = ctx.limits.get("max_triggers", 5)
    if max_triggers > 0 and len(existing) >= max_triggers:
        raise HTTPException(
            429,
            f"Trigger limit reached ({max_triggers}). Upgrade at anytool.dev"
        )

    # Validate trigger type
    trigger_info = TRIGGER_MAP.get(body.trigger_type.lower())
    if not trigger_info:
        raise HTTPException(
            400,
            f"Unknown trigger type: {body.trigger_type}. "
            f"Available: {list(TRIGGER_MAP.keys())}"
        )

    trigger_id = new_id()

    # Save to DB — scoped to account + workspace, keyed on trigger_id
    await put_record(
        object_slug="trigger",
        primary_key=trigger_id,
        account_id=ctx.account_id,
        workspace_id=ctx.workspace_id,
        data={
            "trigger_type": trigger_info["trigger_type"],
            "provider": trigger_info["provider"],
            "user_id": body.user_id,
            "webhook_url": body.webhook_url,
            "filters": body.filters,
            "poll_interval_seconds": body.poll_interval_seconds,
            "enabled": True,
            "last_seen_id": "",
            "last_poll_at": None,
        },
    )

    # Register with the live trigger engine
    engine = await get_trigger_engine()
    from anytool.triggers.base import TriggerConfig

    await engine.register(TriggerConfig(
        id=trigger_id,
        trigger_type=trigger_info["trigger_type"],
        provider=trigger_info["provider"],
        connection_id=body.user_id,
        webhook_url=body.webhook_url,
        filters=body.filters,
        poll_interval_seconds=body.poll_interval_seconds,
    ))

    return {
        "trigger_id": trigger_id,
        "trigger_type": body.trigger_type,
        "user_id": body.user_id,
        "webhook_url": body.webhook_url,
        "status": "active",
    }


@router.get("")
async def list_triggers(
    user_id: Optional[str] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """List triggers, optionally filtered by user_id.

    Without user_id: returns all triggers in this workspace.
    With user_id: returns only that user's triggers.
    """
    records = await list_records(
        "trigger",
        account_id=ctx.account_id,
        workspace_id=ctx.workspace_id,
    )

    triggers = []
    for r in records:
        data = r.custom_data or {}

        # Filter by user_id if provided
        if user_id and data.get("user_id") != user_id:
            continue

        triggers.append({
            "trigger_id": r.primary_field_value,
            "trigger_type": data.get("trigger_type", ""),
            "provider": data.get("provider", ""),
            "user_id": data.get("user_id", ""),
            "webhook_url": data.get("webhook_url", ""),
            "filters": data.get("filters", {}),
            "poll_interval_seconds": data.get("poll_interval_seconds", 90),
            "enabled": data.get("enabled", True),
            "last_poll_at": data.get("last_poll_at"),
            "created_at": str(r.created_at) if r.created_at else "",
        })

    return {"triggers": triggers, "total": len(triggers)}


@router.delete("/{trigger_id}")
async def remove_trigger(trigger_id: str, ctx: AuthContext = Depends(get_auth_context)):
    """Remove a trigger — stops polling and deletes config."""
    record = await get_record("trigger", trigger_id)
    if not record or record.account_id != ctx.account_id:
        raise HTTPException(404, "Trigger not found")

    # Remove from live engine
    engine = await get_trigger_engine()
    await engine.unregister(trigger_id)

    # Soft delete from DB
    await delete_record("trigger", trigger_id)

    return {"removed": True, "trigger_id": trigger_id}


@router.get("/types")
async def list_trigger_types(ctx: AuthContext = Depends(get_auth_context)):
    """List available trigger types."""
    return {
        "trigger_types": [
            {
                "type": k,
                "provider": v["provider"],
                "description": f"Polls for new events via {v['provider']}",
            }
            for k, v in TRIGGER_MAP.items()
        ]
    }
