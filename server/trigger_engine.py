"""
Platform trigger engine — loads triggers from DB, runs background polling.

Uses anytool's TriggerEngine with a DB-backed store that reads/writes
to the records table.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from loguru import logger

from anytool.triggers.base import TriggerConfig, TriggerEvent
from anytool.triggers.engine import TriggerEngine
from anytool.triggers.store import TriggerStore
from server.database import (
    list_records, get_record, put_record, update_record_fields, delete_record, new_id,
)
from server.engine import get_api

_engine: Optional['LoggingTriggerEngine'] = None
_engine_task: Optional[asyncio.Task] = None


class DBTriggerStore(TriggerStore):
    """Trigger store backed by the platform's records table."""

    async def save_trigger(self, config: TriggerConfig) -> None:
        await put_record(
            object_slug="trigger",
            primary_key=config.id,
            data={
                "trigger_type": config.trigger_type,
                "provider": config.provider,
                "connection_id": config.connection_id,
                "webhook_url": config.webhook_url,
                "filters": config.filters,
                "poll_interval_seconds": config.poll_interval_seconds,
                "enabled": config.enabled,
                "last_seen_id": config.last_seen_id,
                "last_poll_at": config.last_poll_at.isoformat() if config.last_poll_at else None,
            },
        )

    async def get_trigger(self, trigger_id: str) -> Optional[TriggerConfig]:
        record = await get_record("trigger", trigger_id)
        if not record:
            return None
        return self._to_config(record.primary_field_value, record.custom_data)

    async def list_triggers(self, enabled_only: bool = True) -> List[TriggerConfig]:
        records = await list_records("trigger", active_only=True)
        triggers = []
        for r in records:
            config = self._to_config(r.primary_field_value, r.custom_data)
            if enabled_only and not config.enabled:
                continue
            triggers.append(config)
        return triggers

    async def update_state(self, trigger_id: str, last_seen_id: str, last_poll_at: datetime) -> None:
        await update_record_fields("trigger", trigger_id, {
            "last_seen_id": last_seen_id,
            "last_poll_at": last_poll_at.isoformat(),
        })

    async def delete_trigger(self, trigger_id: str) -> None:
        await delete_record("trigger", trigger_id)

    async def track_error(self, trigger_id: str, error: str) -> int:
        """Increment error count, store last error. Returns new count."""
        record = await get_record("trigger", trigger_id)
        if not record:
            return 0
        data = record.custom_data or {}
        error_count = data.get("error_count", 0) + 1
        updates = {
            "error_count": error_count,
            "last_error": str(error)[:500],
        }
        # Auto-disable after 10 consecutive errors
        if error_count >= 10:
            updates["enabled"] = False
            logger.warning(
                f"[trigger.store] Auto-disabled trigger {trigger_id} after {error_count} errors"
            )
        await update_record_fields("trigger", trigger_id, updates)
        return error_count

    async def clear_errors(self, trigger_id: str) -> None:
        """Reset error counter on success."""
        await update_record_fields("trigger", trigger_id, {
            "error_count": 0,
            "last_error": "",
        })

    def _to_config(self, trigger_id: str, data: dict) -> TriggerConfig:
        last_poll = data.get("last_poll_at")
        if last_poll and isinstance(last_poll, str):
            last_poll = datetime.fromisoformat(last_poll)
        else:
            last_poll = None

        # user_id is the end-user whose connection to poll
        # stored as "user_id" in data, maps to TriggerConfig.connection_id
        connection_id = data.get("user_id", data.get("connection_id", ""))

        return TriggerConfig(
            id=trigger_id,
            trigger_type=data.get("trigger_type", ""),
            provider=data.get("provider", ""),
            connection_id=connection_id,
            webhook_url=data.get("webhook_url", ""),
            filters=data.get("filters", {}),
            poll_interval_seconds=data.get("poll_interval_seconds", 90),
            enabled=data.get("enabled", True),
            last_seen_id=data.get("last_seen_id", ""),
            last_poll_at=last_poll,
        )


class LoggingTriggerEngine(TriggerEngine):
    """TriggerEngine that logs webhook deliveries to the webhook_log table."""

    async def _deliver_event(self, event: TriggerEvent, webhook_url: str, max_retries: int = 3) -> bool:
        """Override to log each webhook delivery to webhook_log."""
        import time
        start = time.monotonic()
        success = await super()._deliver_event(event, webhook_url, max_retries)
        duration_ms = int((time.monotonic() - start) * 1000)

        # Log to webhook_log (matches the seeded MetaObject schema)
        try:
            record = await get_record("trigger", event.trigger_id)
            account_id = record.account_id if record else ""
            workspace_id = record.workspace_id if record else ""

            await put_record(
                object_slug="webhook_log",
                primary_key=new_id(),
                account_id=account_id,
                workspace_id=workspace_id,
                data={
                    "trigger_id": event.trigger_id,
                    "user_id": event.connection_id,
                    "webhook_url": webhook_url,
                    "event_type": event.trigger_type,
                    "event_data": event.data,
                    "status_code": 200 if success else 0,
                    "successful": success,
                    "retry_count": max_retries - 1 if not success else 0,
                    "error": None if success else "Webhook delivery failed after retries",
                    "duration_ms": duration_ms,
                },
            )
        except Exception as e:
            logger.warning(f"[trigger.engine] Failed to log webhook delivery: {e}")

        return success


async def get_trigger_engine() -> LoggingTriggerEngine:
    """Get or create the singleton trigger engine."""
    global _engine, _engine_task

    if _engine is None:
        import os
        api = get_api()
        store = DBTriggerStore()
        webhook_secret = os.environ.get("ANYTOOL_WEBHOOK_SECRET", "")
        _engine = LoggingTriggerEngine(
            api=api, store=store,
            webhook_secret=webhook_secret,
        )
        logger.info(f"[platform] TriggerEngine initialized | hmac={'yes' if webhook_secret else 'no'}")

    # Start background loop if not running
    if _engine_task is None or _engine_task.done():
        _engine_task = asyncio.create_task(_engine.start())
        logger.info("[platform] TriggerEngine background loop started")

    return _engine


async def stop_trigger_engine():
    """Stop the trigger engine on shutdown."""
    global _engine
    if _engine:
        await _engine.stop()
        logger.info("[platform] TriggerEngine stopped")
