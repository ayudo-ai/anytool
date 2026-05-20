"""
Built-in webhook echo server — lets developers test triggers
without deploying their own webhook endpoint.

POST /v1/webhook-test/{workspace_id}  → receive webhook, store in DB
GET  /v1/webhook-test                → list received webhooks (dashboard)

Developers can use:
  webhook_url = "https://your-anytool.com/v1/webhook-test/{workspace_id}"
when deploying triggers for testing.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from loguru import logger
from sqlalchemy import select, func, and_

from server.auth import get_auth_context, AuthContext
from server.database import (
    put_record, new_id, async_session, MetaRecord,
)

router = APIRouter(prefix="/webhook-test", tags=["webhook-test"])


@router.post("/{workspace_id}")
async def receive_test_webhook(workspace_id: str, request: Request):
    """Receive a test webhook and store it for inspection.

    This endpoint intentionally has NO auth — it acts like a developer's
    webhook server receiving events from anytool triggers.

    Usage in trigger deploy:
        webhook_url = "https://your-server.com/v1/webhook-test/<workspace_id>"
    """
    body = await request.json()
    headers = dict(request.headers)

    # Store the received webhook
    try:
        await put_record(
            object_slug="webhook_test",
            primary_key=new_id(),
            workspace_id=workspace_id,
            data={
                "workspace_id": workspace_id,
                "trigger_id": body.get("trigger_id", ""),
                "trigger_type": body.get("trigger_type", ""),
                "connection_id": body.get("connection_id", ""),
                "event_data": body.get("data", body),
                "full_payload": body,
                "signature": headers.get("x-anytool-signature", ""),
                "timestamp": headers.get("x-anytool-timestamp", ""),
            },
        )
        logger.info(
            f"[webhook-test] Received | workspace={workspace_id} | "
            f"trigger={body.get('trigger_type', '?')}"
        )
    except Exception as e:
        logger.error(f"[webhook-test] Failed to store: {e}")

    return {"received": True}


@router.get("")
async def list_test_webhooks(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: AuthContext = Depends(get_auth_context),
):
    """List received test webhooks for this workspace.

    Dashboard endpoint — shows all webhooks received by the echo server.
    """
    async with async_session() as session:
        conditions = [
            MetaRecord.object_slug == "webhook_test",
            MetaRecord.workspace_id == ctx.workspace_id,
            MetaRecord.is_deleted.is_(False),
        ]

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

    webhooks = []
    for r in records:
        data = r.custom_data or {}
        webhooks.append({
            "id": r.id,
            "trigger_id": data.get("trigger_id", ""),
            "trigger_type": data.get("trigger_type", ""),
            "connection_id": data.get("connection_id", ""),
            "event_data": data.get("event_data", {}),
            "full_payload": data.get("full_payload", {}),
            "signature": data.get("signature", ""),
            "received_at": str(r.created_at) if r.created_at else "",
        })

    return {"webhooks": webhooks, "total": total}
