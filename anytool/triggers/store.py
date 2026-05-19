"""
Trigger store — persists trigger configs and dedup state.

MemoryTriggerStore for testing/dev.
Implement TriggerStore for your DB in production.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone
from typing import Dict, List, Optional

from anytool.triggers.base import TriggerConfig


class TriggerStore(abc.ABC):
    """Abstract trigger store. Implement for your database."""

    @abc.abstractmethod
    async def save_trigger(self, config: TriggerConfig) -> None:
        ...

    @abc.abstractmethod
    async def get_trigger(self, trigger_id: str) -> Optional[TriggerConfig]:
        ...

    @abc.abstractmethod
    async def list_triggers(self, enabled_only: bool = True) -> List[TriggerConfig]:
        ...

    @abc.abstractmethod
    async def update_state(self, trigger_id: str, last_seen_id: str, last_poll_at: datetime) -> None:
        """Update dedup state after a successful poll."""
        ...

    @abc.abstractmethod
    async def delete_trigger(self, trigger_id: str) -> None:
        ...

    async def track_error(self, trigger_id: str, error: str) -> int:
        """Record a consecutive error. Returns new error count. Override in DB stores."""
        return 0

    async def clear_errors(self, trigger_id: str) -> None:
        """Reset error counter on successful poll. Override in DB stores."""
        pass


class MemoryTriggerStore(TriggerStore):
    """In-memory trigger store for testing."""

    def __init__(self):
        self._triggers: Dict[str, TriggerConfig] = {}

    async def save_trigger(self, config: TriggerConfig) -> None:
        self._triggers[config.id] = config

    async def get_trigger(self, trigger_id: str) -> Optional[TriggerConfig]:
        return self._triggers.get(trigger_id)

    async def list_triggers(self, enabled_only: bool = True) -> List[TriggerConfig]:
        triggers = list(self._triggers.values())
        if enabled_only:
            triggers = [t for t in triggers if t.enabled]
        return triggers

    async def update_state(self, trigger_id: str, last_seen_id: str, last_poll_at: datetime) -> None:
        t = self._triggers.get(trigger_id)
        if t:
            t.last_seen_id = last_seen_id
            t.last_poll_at = last_poll_at

    async def delete_trigger(self, trigger_id: str) -> None:
        self._triggers.pop(trigger_id, None)

    async def track_error(self, trigger_id: str, error: str) -> int:
        # Simple in-memory error tracking
        t = self._triggers.get(trigger_id)
        if t:
            count = getattr(t, '_error_count', 0) + 1
            t._error_count = count
            return count
        return 0

    async def clear_errors(self, trigger_id: str) -> None:
        t = self._triggers.get(trigger_id)
        if t:
            t._error_count = 0
