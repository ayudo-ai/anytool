"""
Dashboard endpoints — overview, usage stats, logs, connections.

GET /v1/dashboard/overview       → key metrics at a glance
GET /v1/dashboard/usage          → daily usage breakdown
GET /v1/dashboard/logs           → recent execution logs (paginated)
GET /v1/dashboard/connections    → all connections across users
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, cast, String, text

from server.auth import get_auth_context, AuthContext
from server.database import (
    async_session, MetaRecord, SCHEMA,
    list_records, get_record,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def dashboard_overview(ctx: AuthContext = Depends(get_auth_context)):
    """Key metrics: connections, calls, triggers, errors.

    Example response:
        {
            "plan": "free",
            "calls_this_month": 127,
            "max_calls": 1000,
            "active_connections": 8,
            "max_connections": 10,
            "active_triggers": 3,
            "max_triggers": 5,
            "triggers_with_errors": 1
        }
    """
    # Workspace usage
    workspace_record = await get_record("workspace", ctx.workspace_id)
    ws_data = workspace_record.custom_data if workspace_record else {}

    # Count connections
    connections = await list_records("connection", account_id=ctx.account_id)
    active_connections = sum(
        1 for c in connections
        if (c.custom_data or {}).get("status") == "active"
    )

    # Count triggers
    triggers = await list_records("trigger", account_id=ctx.account_id, workspace_id=ctx.workspace_id)
    active_triggers = len(triggers)
    triggers_with_errors = sum(
        1 for t in triggers
        if (t.custom_data or {}).get("error_count", 0) > 0
    )

    return {
        "plan": ctx.plan,
        "calls_this_month": ws_data.get("calls_this_month", 0),
        "max_calls": ctx.limits.get("max_calls", 1000),
        "active_connections": active_connections,
        "max_connections": ctx.limits.get("max_connections", 10),
        "active_triggers": active_triggers,
        "max_triggers": ctx.limits.get("max_triggers", 5),
        "triggers_with_errors": triggers_with_errors,
    }


@router.get("/usage")
async def dashboard_usage(
    days: int = Query(default=30, ge=1, le=90),
    ctx: AuthContext = Depends(get_auth_context),
):
    """Daily usage breakdown for the last N days.

    Returns per-day aggregates: total calls, successful, failed, avg duration.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session() as session:
        # Get all usage logs for this workspace in the time range
        result = await session.execute(
            select(MetaRecord).where(
                MetaRecord.object_slug == "usage_log",
                MetaRecord.workspace_id == ctx.workspace_id,
                MetaRecord.is_deleted.is_(False),
                MetaRecord.created_at >= cutoff,
            ).order_by(MetaRecord.created_at.desc())
        )
        records = result.scalars().all()

    # Aggregate by day
    daily = {}
    for r in records:
        data = r.custom_data or {}
        day = r.created_at.strftime("%Y-%m-%d") if r.created_at else "unknown"
        if day not in daily:
            daily[day] = {"date": day, "total": 0, "successful": 0, "failed": 0, "total_duration_ms": 0}
        daily[day]["total"] += 1
        if data.get("successful"):
            daily[day]["successful"] += 1
        else:
            daily[day]["failed"] += 1
        daily[day]["total_duration_ms"] += data.get("duration_ms", 0)

    # Calculate averages and sort
    usage_days = sorted(daily.values(), key=lambda d: d["date"], reverse=True)
    for d in usage_days:
        d["avg_duration_ms"] = round(d["total_duration_ms"] / d["total"]) if d["total"] else 0
        del d["total_duration_ms"]

    return {"days": usage_days, "total_days": len(usage_days)}


@router.get("/logs")
async def dashboard_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    successful: Optional[bool] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Recent execution logs with filters and pagination.

    Example:
        GET /v1/dashboard/logs?action=gmail_send_email&successful=false&limit=20
    """
    async with async_session() as session:
        conditions = [
            MetaRecord.object_slug == "usage_log",
            MetaRecord.workspace_id == ctx.workspace_id,
            MetaRecord.is_deleted.is_(False),
        ]

        if action:
            conditions.append(MetaRecord.custom_data["action"].astext == action)
        if user_id:
            conditions.append(MetaRecord.custom_data["user_id"].astext == user_id)
        if successful is not None:
            conditions.append(
                MetaRecord.custom_data["successful"].astext == str(successful).lower()
            )

        result = await session.execute(
            select(MetaRecord)
            .where(and_(*conditions))
            .order_by(MetaRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        records = result.scalars().all()

        # Get total count
        count_result = await session.execute(
            select(func.count(MetaRecord.id))
            .where(and_(*conditions))
        )
        total = count_result.scalar() or 0

    logs = []
    for r in records:
        data = r.custom_data or {}
        logs.append({
            "id": r.id,
            "action": data.get("action", ""),
            "provider": data.get("provider", ""),
            "user_id": data.get("user_id", ""),
            "successful": data.get("successful", False),
            "status_code": data.get("status_code", 0),
            "duration_ms": data.get("duration_ms", 0),
            "error": data.get("error"),
            "created_at": str(r.created_at) if r.created_at else "",
        })

    return {"logs": logs, "total": total, "limit": limit, "offset": offset}


@router.get("/connections")
async def dashboard_connections(
    user_id: Optional[str] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """All connections tracked in our DB, optionally filtered by user_id.

    Shows connection metadata stored when /v1/connections/confirm is called.
    """
    records = await list_records("connection", account_id=ctx.account_id)

    connections = []
    for r in records:
        data = r.custom_data or {}
        # Filter by user_id if provided
        if user_id and data.get("user_id") != user_id:
            continue
        connections.append({
            "user_id": data.get("user_id", ""),
            "provider": data.get("provider", ""),
            "status": data.get("status", "unknown"),
            "connected_at": data.get("connected_at", ""),
            "scopes": data.get("scopes", []),
        })

    return {"connections": connections, "total": len(connections)}


@router.get("/webhook-logs")
async def dashboard_webhook_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    trigger_id: Optional[str] = None,
    user_id: Optional[str] = None,
    successful: Optional[bool] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Recent webhook delivery logs from trigger polls.

    Reads from the webhook_log MetaObject.

    Example:
        GET /v1/dashboard/webhook-logs?trigger_id=abc123&limit=20
    """
    async with async_session() as session:
        conditions = [
            MetaRecord.object_slug == "webhook_log",
            MetaRecord.workspace_id == ctx.workspace_id,
            MetaRecord.is_deleted.is_(False),
        ]

        if trigger_id:
            conditions.append(MetaRecord.custom_data["trigger_id"].astext == trigger_id)
        if user_id:
            conditions.append(MetaRecord.custom_data["user_id"].astext == user_id)
        if successful is not None:
            conditions.append(
                MetaRecord.custom_data["successful"].astext == str(successful).lower()
            )

        result = await session.execute(
            select(MetaRecord)
            .where(and_(*conditions))
            .order_by(MetaRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        records = result.scalars().all()

        count_result = await session.execute(
            select(func.count(MetaRecord.id))
            .where(and_(*conditions))
        )
        total = count_result.scalar() or 0

    logs = []
    for r in records:
        data = r.custom_data or {}
        logs.append({
            "id": r.id,
            "trigger_id": data.get("trigger_id", ""),
            "user_id": data.get("user_id", ""),
            "webhook_url": data.get("webhook_url", ""),
            "event_type": data.get("event_type", ""),
            "event_data": data.get("event_data", {}),
            "status_code": data.get("status_code", 0),
            "successful": data.get("successful", False),
            "retry_count": data.get("retry_count", 0),
            "error": data.get("error"),
            "duration_ms": data.get("duration_ms", 0),
            "created_at": str(r.created_at) if r.created_at else "",
        })

    return {"logs": logs, "total": total, "limit": limit, "offset": offset}
