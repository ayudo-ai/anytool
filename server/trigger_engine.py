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

from anytool.triggers.base import TriggerConfig
from anytool.triggers.engine import TriggerEngine
from anytool.triggers.store import TriggerStore
from server.database import (
    list_records, get_record, put_record, update_record_fields, delete_record,
)
from server.engine import get_api

_engine: Optional[TriggerEngine] = None
_engine_task: Optional[asyncio.Task] = None


class DBTriggerStore(TriggerStore):
    """Trigger store backed by the platform's records table."""

    async def save_trigger(self, config: TriggerConfig) -> None:
        await put_record(
            object_type="trigger",
            key=config.id,
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
        return self._to_config(record.key, record.data)

    async def list_triggers(self, enabled_only: bool = True) -> List[TriggerConfig]:
        records = await list_records("trigger", active_only=True)
        triggers = []
        for r in records:
            config = self._to_config(r.key, r.data)
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


async def get_trigger_engine() -> TriggerEngine:
    """Get or create the singleton trigger engine."""
    global _engine, _engine_task

    if _engine is None:
        api = get_api()
        store = DBTriggerStore()
        _engine = TriggerEngine(api=api, store=store)
        logger.info("[platform] TriggerEngine initialized with DBTriggerStore")

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
