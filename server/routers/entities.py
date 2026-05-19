"""
Entity (end-user) management — browse, search, and manage connected users.

Entities are end-users of the developer's app. Each entity can have:
  - Multiple connections (one per provider)
  - Multiple triggers
  - Usage history

GET /v1/entities           → list all entities (unique user_ids)
GET /v1/entities/{user_id} → get entity detail (connections, triggers, usage)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from server.auth import get_auth_context, AuthContext
from server.database import list_records

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("")
async def list_entities(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """List all unique entities (end-users) across connections.

    Aggregates connection and trigger counts per user_id.
    """
    # Get all connections for this workspace
    connections = await list_records("connection", account_id=ctx.account_id, workspace_id=ctx.workspace_id)

    # Get all triggers for this workspace
    triggers = await list_records("trigger", account_id=ctx.account_id, workspace_id=ctx.workspace_id)

    # Aggregate by user_id
    entities = {}
    for c in connections:
        d = c.custom_data or {}
        uid = d.get("user_id", "")
        if not uid:
            continue
        if search and search.lower() not in uid.lower():
            continue
        if uid not in entities:
            entities[uid] = {
                "user_id": uid,
                "connections": [],
                "connection_count": 0,
                "trigger_count": 0,
                "providers": [],
                "status": "active",
                "first_seen": str(c.created_at) if c.created_at else "",
            }
        conn_info = {
            "provider": d.get("provider", ""),
            "status": d.get("status", "unknown"),
            "connected_at": d.get("connected_at", ""),
        }
        entities[uid]["connections"].append(conn_info)
        entities[uid]["connection_count"] += 1
        if d.get("provider") and d["provider"] not in entities[uid]["providers"]:
            entities[uid]["providers"].append(d["provider"])

    # Count triggers per user
    for t in triggers:
        d = t.custom_data or {}
        uid = d.get("user_id", "")
        if uid in entities:
            entities[uid]["trigger_count"] += 1

    # Sort by first_seen (newest first) and paginate
    entity_list = sorted(entities.values(), key=lambda e: e["first_seen"], reverse=True)
    total = len(entity_list)
    paginated = entity_list[offset:offset + limit]

    return {"entities": paginated, "total": total, "limit": limit, "offset": offset}


@router.get("/{user_id}")
async def get_entity(user_id: str, ctx: AuthContext = Depends(get_auth_context)):
    """Get detailed info about a specific entity (end-user).

    Returns all connections, triggers, and recent usage for this user.
    """
    # Connections
    all_connections = await list_records("connection", account_id=ctx.account_id, workspace_id=ctx.workspace_id)
    user_connections = []
    for c in all_connections:
        d = c.custom_data or {}
        if d.get("user_id") == user_id:
            user_connections.append({
                "provider": d.get("provider", ""),
                "status": d.get("status", "unknown"),
                "connected_at": d.get("connected_at", ""),
                "scopes": d.get("scopes", []),
            })

    if not user_connections:
        raise HTTPException(404, f"Entity '{user_id}' not found")

    # Triggers
    all_triggers = await list_records("trigger", account_id=ctx.account_id, workspace_id=ctx.workspace_id)
    user_triggers = []
    for t in all_triggers:
        d = t.custom_data or {}
        if d.get("user_id") == user_id:
            user_triggers.append({
                "trigger_id": t.primary_field_value,
                "trigger_type": d.get("trigger_type", ""),
                "provider": d.get("provider", ""),
                "webhook_url": d.get("webhook_url", ""),
                "enabled": d.get("enabled", True),
                "error_count": d.get("error_count", 0),
                "last_poll_at": d.get("last_poll_at"),
            })

    # Recent usage logs
    all_logs = await list_records("usage_log", account_id=ctx.account_id, workspace_id=ctx.workspace_id)
    user_logs = []
    for l in all_logs:
        d = l.custom_data or {}
        if d.get("user_id") == user_id:
            user_logs.append({
                "action": d.get("action", ""),
                "provider": d.get("provider", ""),
                "successful": d.get("successful", False),
                "duration_ms": d.get("duration_ms", 0),
                "created_at": str(l.created_at) if l.created_at else "",
            })
            if len(user_logs) >= 20:
                break

    return {
        "user_id": user_id,
        "connections": user_connections,
        "triggers": user_triggers,
        "recent_activity": user_logs,
        "connection_count": len(user_connections),
        "trigger_count": len(user_triggers),
        "providers": list(set(c["provider"] for c in user_connections)),
    }
