"""
Trigger management — deploy, list, remove triggers.

POST   /v1/triggers       → deploy a trigger
GET    /v1/triggers       → list active triggers
DELETE /v1/triggers/{id}  → remove a trigger
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_account
from server.database import (
    put_record, get_record, list_records, delete_record,
    update_record_fields, new_id, now,
)
from server.engine import get_api
from server.trigger_engine import get_trigger_engine

router = APIRouter(prefix="/triggers", tags=["triggers"])


# ── Supported triggers ───────────────────────────────────────────────

TRIGGER_MAP = {
    "gmail_new_message": {"trigger_type": "gmail_new_message", "provider": "google"},
    "gmail_new_email": {"trigger_type": "gmail_new_message", "provider": "google"},
}


class DeployTriggerRequest(BaseModel):
    trigger_type: str  # gmail_new_message, etc.
    user_id: str  # end-user whose connection to poll
    webhook_url: str  # where to POST events
    filters: Dict[str, Any] = {}  # from_contains, subject_contains, etc.
    poll_interval_seconds: int = 90


class TriggerResponse(BaseModel):
    trigger_id: str
    trigger_type: str
    user_id: str
    webhook_url: str
    status: str


# ── Routes ───────────────────────────────────────────────────────────

@router.post("", response_model=TriggerResponse)
async def deploy_trigger(body: DeployTriggerRequest, account: dict = Depends(get_account)):
    """Deploy a trigger — starts polling for events.

    When a new event is detected (e.g., new email), anytool POSTs
    to your webhook_url with the event data.

    Example:
        POST /v1/triggers
        {
            "trigger_type": "gmail_new_message",
            "user_id": "customer-123",
            "webhook_url": "https://myapp.com/webhook",
            "filters": {"from_contains": "vendor@example.com"},
            "poll_interval_seconds": 60
        }
    """
    # Check limits
    limits = account.get("limits", {})
    max_triggers = limits.get("max_triggers", 5)
    existing = await list_records("trigger", account_id=account["id"])
    if max_triggers > 0 and len(existing) >= max_triggers:
        raise HTTPException(
            429,
            f"Trigger limit reached ({max_triggers}). Upgrade your plan at anytool.dev"
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

    # Save to DB
    await put_record(
        object_type="trigger",
        key=trigger_id,
        account_id=account["id"],
        data={
            "trigger_type": trigger_info["trigger_type"],
            "provider": trigger_info["provider"],
            "connection_id": body.user_id,
            "webhook_url": body.webhook_url,
            "filters": body.filters,
            "poll_interval_seconds": body.poll_interval_seconds,
            "enabled": True,
            "last_seen_id": "",
            "last_poll_at": None,
        },
    )

    # Register with the trigger engine
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

    return TriggerResponse(
        trigger_id=trigger_id,
        trigger_type=body.trigger_type,
        user_id=body.user_id,
        webhook_url=body.webhook_url,
        status="active",
    )


@router.get("")
async def list_triggers(account: dict = Depends(get_account)):
    """List all active triggers for this account."""
    records = await list_records("trigger", account_id=account["id"])
    triggers = []
    for r in records:
        data = r.data or {}
        triggers.append({
            "trigger_id": r.key,
            "trigger_type": data.get("trigger_type", ""),
            "provider": data.get("provider", ""),
            "user_id": data.get("connection_id", ""),
            "webhook_url": data.get("webhook_url", ""),
            "filters": data.get("filters", {}),
            "poll_interval_seconds": data.get("poll_interval_seconds", 90),
            "enabled": data.get("enabled", True),
            "last_poll_at": data.get("last_poll_at"),
            "created_at": str(r.created_at) if r.created_at else "",
        })
    return {"triggers": triggers, "total": len(triggers)}


@router.delete("/{trigger_id}")
async def remove_trigger(trigger_id: str, account: dict = Depends(get_account)):
    """Remove a trigger — stops polling."""
    record = await get_record("trigger", trigger_id)
    if not record or record.account_id != account["id"]:
        raise HTTPException(404, "Trigger not found")

    # Remove from engine
    engine = await get_trigger_engine()
    await engine.unregister(trigger_id)

    # Soft delete from DB
    await delete_record("trigger", trigger_id)

    return {"removed": True, "trigger_id": trigger_id}


@router.get("/types")
async def list_trigger_types(account: dict = Depends(get_account)):
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
