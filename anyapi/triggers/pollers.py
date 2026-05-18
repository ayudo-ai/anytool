"""
Pollers — app-specific logic to detect new events.

Each poller knows how to:
1. Call the API to check for new items
2. Filter based on trigger config
3. Normalize the data into a TriggerEvent
4. Track what was already seen (dedup)

Adding a new poller = one function. Same pattern every time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from loguru import logger

from anyapi.client import AnyAPI
from anyapi.triggers.base import TriggerConfig, TriggerEvent


async def poll_gmail_new_message(
    api: AnyAPI,
    trigger: TriggerConfig,
) -> List[TriggerEvent]:
    """Poll Gmail for new messages.

    Strategy:
    - Search for messages newer than the last poll
    - Compare against last_seen_id to avoid duplicates
    - Apply filters (from_contains, subject_contains, etc.)
    - Return new messages as TriggerEvents
    """
    # Build search query
    query_parts = ["is:unread", "newer_than:3m"]  # 3 min window (overlaps poll interval for safety)

    filters = trigger.filters or {}
    if filters.get("from_contains"):
        query_parts.append(f"from:{filters['from_contains']}")
    if filters.get("subject_contains"):
        query_parts.append(f"subject:{filters['subject_contains']}")
    if filters.get("to_contains"):
        query_parts.append(f"to:{filters['to_contains']}")
    if filters.get("label"):
        query_parts.append(f"label:{filters['label']}")
    if filters.get("has_attachment"):
        query_parts.append("has:attachment")

    query = " ".join(query_parts)

    # Search for messages
    search_result = await api.call(
        "gmail_search",
        connection_id=trigger.connection_id,
        q=query,
        maxResults=20,
    )

    if not search_result.get("successful"):
        logger.warning(
            f"[trigger.gmail] Search failed | trigger={trigger.id} | "
            f"{search_result.get('error', 'unknown')}"
        )
        return []

    messages = search_result.get("data", {}).get("messages", [])
    if not messages:
        return []

    # Filter out already-seen messages
    last_seen = trigger.last_seen_id
    new_message_ids = []
    for msg in messages:
        msg_id = msg.get("id", "")
        if msg_id == last_seen:
            break  # Gmail returns newest first — stop at last seen
        new_message_ids.append(msg_id)

    if not new_message_ids:
        return []

    logger.info(
        f"[trigger.gmail] Found {len(new_message_ids)} new messages | "
        f"trigger={trigger.id} connection={trigger.connection_id}"
    )

    # Fetch each new message's details
    events = []
    for msg_id in new_message_ids:
        msg_result = await api.call(
            "gmail_get_message",
            connection_id=trigger.connection_id,
            message_id=msg_id,
            format="metadata",
        )

        if not msg_result.get("successful"):
            continue

        msg_data = msg_result.get("data", {})

        # Extract headers
        headers = {}
        for h in msg_data.get("payload", {}).get("headers", []):
            name = h.get("name", "").lower()
            if name in ("from", "to", "subject", "date", "cc", "message-id"):
                headers[name] = h.get("value", "")

        # Build normalized event data
        event_data = {
            "message_id": msg_data.get("id", msg_id),
            "thread_id": msg_data.get("threadId", ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "snippet": msg_data.get("snippet", ""),
            "label_ids": msg_data.get("labelIds", []),
        }

        # Apply post-fetch filters (body_contains needs snippet)
        if filters.get("body_contains"):
            if filters["body_contains"].lower() not in event_data["snippet"].lower():
                continue

        events.append(TriggerEvent(
            trigger_id=trigger.id,
            trigger_type=trigger.trigger_type,
            provider=trigger.provider,
            connection_id=trigger.connection_id,
            data=event_data,
            raw=msg_data,
        ))

    return events


# ── Poller Registry ──────────────────────────────────────────────────

# Maps trigger_type → poller function
POLLERS = {
    "gmail_new_message": poll_gmail_new_message,
}


def get_poller(trigger_type: str):
    """Get the poller function for a trigger type."""
    poller = POLLERS.get(trigger_type)
    if not poller:
        raise ValueError(
            f"No poller for trigger type '{trigger_type}'. "
            f"Available: {list(POLLERS.keys())}"
        )
    return poller
