"""
Trigger base — defines the trigger contract.

A trigger watches for new events (new email, new ticket, etc.)
and calls a webhook URL when something happens.

The consuming app registers:
  - What to watch (provider, connection_id, trigger type)
  - Where to send events (webhook_url)
  - Optional filters (from_contains, subject_contains, etc.)

anytool handles detection, deduplication, and delivery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class TriggerConfig:
    """Configuration for a trigger subscription."""

    id: str  # Unique trigger ID
    trigger_type: str  # e.g. "gmail_new_message", "freshdesk_new_ticket"
    provider: str  # e.g. "google", "freshdesk"
    connection_id: str  # User/workspace ID (maps to Nango connection)
    webhook_url: str  # Where to POST events

    # Optional filters
    filters: Dict[str, Any] = field(default_factory=dict)
    # Gmail: {"from_contains": "vendor@", "subject_contains": "invoice"}
    # Freshdesk: {"status": "open", "priority": "high"}

    # Polling config
    poll_interval_seconds: int = 90  # How often to check
    enabled: bool = True

    # Internal state
    last_poll_at: Optional[datetime] = None
    last_seen_id: str = ""  # Last processed item ID (for deduplication)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TriggerEvent:
    """An event detected by a trigger — sent to the webhook."""

    trigger_id: str
    trigger_type: str
    provider: str
    connection_id: str
    data: Dict[str, Any]  # Normalized event data
    raw: Dict[str, Any] = field(default_factory=dict)  # Raw API response
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_webhook_payload(self) -> dict:
        """Convert to the payload POSTed to the webhook URL.

        Includes both normalized `data` (standard format across all providers)
        and `raw` (original provider payload for full access).
        """
        payload = {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type,
            "provider": self.provider,
            "connection_id": self.connection_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.raw:
            payload["raw"] = self.raw
        return payload
