"""
Trigger Engine — background loop that runs pollers and delivers events.

Usage:
    from anytool import AnyAPI
    from anytool.triggers.engine import TriggerEngine
    from anytool.triggers.store import MemoryTriggerStore
    from anytool.triggers.base import TriggerConfig

    api = AnyAPI(nango_secret_key="xxx")
    store = MemoryTriggerStore()
    engine = TriggerEngine(api=api, store=store)

    # Register a trigger
    await engine.register(TriggerConfig(
        id="t1",
        trigger_type="gmail_new_message",
        provider="google",
        connection_id="workspace-123",
        webhook_url="https://your-app.com/api/webhook/trigger",
        filters={"from_contains": "vendor@example.com"},
        poll_interval_seconds=90,
    ))

    # Start the engine (runs forever in background)
    await engine.start()

    # Or run one poll cycle (for testing)
    events = await engine.poll_once()
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from loguru import logger

from anytool.client import AnyAPI
from anytool.triggers.base import TriggerConfig, TriggerEvent
from anytool.triggers.pollers import get_poller
from anytool.triggers.store import TriggerStore


class TriggerEngine:
    """Runs trigger pollers and delivers events to webhooks."""

    def __init__(
        self,
        api: AnyAPI,
        store: TriggerStore,
        max_concurrent_polls: int = 5,
    ):
        self._api = api
        self._store = store
        self._max_concurrent = max_concurrent_polls
        self._running = False
        self._http = httpx.AsyncClient(timeout=10.0)

    # ── Trigger Management ───────────────────────────────────────────

    async def register(
        self,
        config: TriggerConfig,
        skip_baseline: bool = False,
    ) -> TriggerConfig:
        """Register a new trigger.

        If skip_baseline=False (default), runs an initial poll to set
        last_seen_id WITHOUT delivering events. This prevents old
        messages from flooding your webhook on first registration.
        """
        await self._store.save_trigger(config)
        logger.info(
            f"[trigger.engine] Registered | id={config.id} "
            f"type={config.trigger_type} connection={config.connection_id}"
        )

        if not skip_baseline and not config.last_seen_id:
            await self._baseline_trigger(config)

        return config

    async def _baseline_trigger(self, trigger: TriggerConfig) -> None:
        """Run initial poll to set last_seen_id without delivering events."""
        try:
            poller = get_poller(trigger.trigger_type)
        except ValueError:
            return

        events = await poller(self._api, trigger)
        if events:
            newest_id = events[0].data.get("message_id", "")
            await self._store.update_state(
                trigger.id,
                last_seen_id=newest_id,
                last_poll_at=datetime.now(timezone.utc),
            )
            logger.info(
                f"[trigger.engine] Baselined | id={trigger.id} | "
                f"skipped {len(events)} existing messages | "
                f"last_seen={newest_id}"
            )
        else:
            await self._store.update_state(
                trigger.id,
                last_seen_id="",
                last_poll_at=datetime.now(timezone.utc),
            )
            logger.info(f"[trigger.engine] Baselined | id={trigger.id} | no existing messages")

    async def unregister(self, trigger_id: str) -> None:
        """Remove a trigger."""
        await self._store.delete_trigger(trigger_id)
        logger.info(f"[trigger.engine] Unregistered | id={trigger_id}")

    async def list_triggers(self) -> List[TriggerConfig]:
        """List all active triggers."""
        return await self._store.list_triggers(enabled_only=True)

    # ── Polling ──────────────────────────────────────────────────────

    async def poll_once(self) -> List[TriggerEvent]:
        """Run one poll cycle for all triggers. Returns all events found.

        Use this for testing or manual polling.
        """
        triggers = await self._store.list_triggers(enabled_only=True)
        if not triggers:
            return []

        all_events = []

        # Poll triggers with concurrency limit
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def _poll_one(trigger: TriggerConfig) -> List[TriggerEvent]:
            async with semaphore:
                return await self._poll_trigger(trigger)

        results = await asyncio.gather(
            *[_poll_one(t) for t in triggers],
            return_exceptions=True,
        )

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"[trigger.engine] Poll failed | trigger={triggers[i].id} | {result}"
                )
            elif result:
                all_events.extend(result)

        return all_events

    async def _poll_trigger(self, trigger: TriggerConfig) -> List[TriggerEvent]:
        """Poll a single trigger, deliver events, update state."""
        try:
            poller = get_poller(trigger.trigger_type)
        except ValueError as e:
            logger.error(f"[trigger.engine] {e}")
            return []

        # Run the poller
        events = await poller(self._api, trigger)

        if not events:
            # Update last_poll_at even with no results
            await self._store.update_state(
                trigger.id,
                last_seen_id=trigger.last_seen_id,
                last_poll_at=datetime.now(timezone.utc),
            )
            return []

        # Deliver events to webhook
        delivered = []
        for event in events:
            success = await self._deliver_event(event, trigger.webhook_url)
            if success:
                delivered.append(event)

        # Update state with newest message ID
        if delivered:
            newest_id = delivered[0].data.get("message_id", "")
            await self._store.update_state(
                trigger.id,
                last_seen_id=newest_id,
                last_poll_at=datetime.now(timezone.utc),
            )

        logger.info(
            f"[trigger.engine] Poll complete | trigger={trigger.id} | "
            f"found={len(events)} delivered={len(delivered)}"
        )

        return delivered

    async def _deliver_event(self, event: TriggerEvent, webhook_url: str) -> bool:
        """POST an event to the webhook URL."""
        payload = event.to_webhook_payload()

        try:
            resp = await self._http.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if resp.is_success:
                logger.info(
                    f"[trigger.engine] Delivered | trigger={event.trigger_id} | "
                    f"message_id={event.data.get('message_id', '?')} | "
                    f"→ {webhook_url}"
                )
                return True
            else:
                logger.warning(
                    f"[trigger.engine] Delivery failed | {resp.status_code} | "
                    f"trigger={event.trigger_id} | {resp.text[:200]}"
                )
                return False

        except Exception as e:
            logger.error(
                f"[trigger.engine] Delivery error | trigger={event.trigger_id} | {e}"
            )
            return False

    # ── Background Loop ──────────────────────────────────────────────

    async def start(self):
        """Start the trigger engine. Runs forever, polling on schedule.

        Call this in a background task:
            asyncio.create_task(engine.start())
        """
        self._running = True
        logger.info("[trigger.engine] Started")

        while self._running:
            triggers = await self._store.list_triggers(enabled_only=True)

            if not triggers:
                await asyncio.sleep(10)
                continue

            now = datetime.now(timezone.utc)
            tasks = []

            for trigger in triggers:
                # Check if it's time to poll
                if trigger.last_poll_at:
                    elapsed = (now - trigger.last_poll_at).total_seconds()
                    if elapsed < trigger.poll_interval_seconds:
                        continue

                tasks.append(self._poll_trigger(trigger))

            if tasks:
                # Run due polls concurrently
                semaphore = asyncio.Semaphore(self._max_concurrent)

                async def _limited(coro):
                    async with semaphore:
                        return await coro

                await asyncio.gather(
                    *[_limited(t) for t in tasks],
                    return_exceptions=True,
                )

            # Sleep a short interval before checking again
            await asyncio.sleep(5)

    async def stop(self):
        """Stop the trigger engine."""
        self._running = False
        logger.info("[trigger.engine] Stopped")

    async def close(self):
        """Cleanup."""
        self._running = False
        await self._http.aclose()
