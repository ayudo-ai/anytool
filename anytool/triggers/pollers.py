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

from anytool.client import AnyTool
from anytool.triggers.base import TriggerConfig, TriggerEvent


# ── Gmail ────────────────────────────────────────────────────────────

async def poll_gmail_new_message(
    api: AnyTool,
    trigger: TriggerConfig,
) -> List[TriggerEvent]:
    """Poll Gmail for new messages."""
    query_parts = ["is:unread", "newer_than:3m"]

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

    search_result = await api.call(
        "gmail_search",
        connection_id=trigger.connection_id,
        q=query,
        maxResults=20,
    )

    if not search_result.get("successful"):
        logger.warning(f"[trigger.gmail] Search failed | trigger={trigger.id}")
        return []

    messages = search_result.get("data", {}).get("messages", [])
    if not messages:
        return []

    last_seen = trigger.last_seen_id
    new_message_ids = []
    for msg in messages:
        msg_id = msg.get("id", "")
        if msg_id == last_seen:
            break
        new_message_ids.append(msg_id)

    if not new_message_ids:
        return []

    logger.info(f"[trigger.gmail] Found {len(new_message_ids)} new | trigger={trigger.id}")

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
        headers = {}
        for h in msg_data.get("payload", {}).get("headers", []):
            name = h.get("name", "").lower()
            if name in ("from", "to", "subject", "date", "cc", "message-id"):
                headers[name] = h.get("value", "")

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


# ── Slack ─────────────────────────────────────────────────────────────

async def poll_slack_new_message(
    api: AnyTool,
    trigger: TriggerConfig,
) -> List[TriggerEvent]:
    """Poll Slack channel for new messages.

    Filters:
      channel_id (required): Channel to monitor
      from_user: Filter by user ID
      contains: Text must contain this string
    """
    filters = trigger.filters or {}
    channel_id = filters.get("channel_id", "")
    if not channel_id:
        logger.warning(f"[trigger.slack] No channel_id | trigger={trigger.id}")
        return []

    result = await api.call(
        "slack_get_history",
        connection_id=trigger.connection_id,
        channel=channel_id,
        limit=20,
    )

    if not result.get("successful"):
        logger.warning(f"[trigger.slack] History failed | trigger={trigger.id}")
        return []

    messages = result.get("data", {}).get("messages", [])
    if not messages:
        return []

    last_seen = trigger.last_seen_id
    events = []
    for msg in messages:
        ts = msg.get("ts", "")
        if ts == last_seen:
            break
        # Skip bot messages and subtypes (joins, leaves, etc.)
        if msg.get("subtype") or msg.get("bot_id"):
            continue

        # Apply filters
        if filters.get("from_user") and msg.get("user") != filters["from_user"]:
            continue
        if filters.get("contains"):
            if filters["contains"].lower() not in msg.get("text", "").lower():
                continue

        events.append(TriggerEvent(
            trigger_id=trigger.id,
            trigger_type="slack_new_message",
            provider="slack",
            connection_id=trigger.connection_id,
            data={
                "message_id": ts,
                "channel_id": channel_id,
                "user": msg.get("user", ""),
                "text": msg.get("text", ""),
                "ts": ts,
                "thread_ts": msg.get("thread_ts", ""),
            },
            raw=msg,
        ))

    return events


# ── GitHub ────────────────────────────────────────────────────────────

async def poll_github_new_issue(
    api: AnyTool,
    trigger: TriggerConfig,
) -> List[TriggerEvent]:
    """Poll GitHub repo for new issues.

    Filters:
      owner (required): Repo owner
      repo (required): Repo name
      labels: Comma-separated label filter
      state: open (default), closed, all
    """
    filters = trigger.filters or {}
    owner = filters.get("owner", "")
    repo = filters.get("repo", "")
    if not owner or not repo:
        logger.warning(f"[trigger.github] No owner/repo | trigger={trigger.id}")
        return []

    result = await api.call(
        "github_list_issues",
        connection_id=trigger.connection_id,
        owner=owner,
        repo=repo,
        state=filters.get("state", "open"),
        sort="created",
        direction="desc",
        per_page=20,
    )

    if not result.get("successful"):
        logger.warning(f"[trigger.github] List issues failed | trigger={trigger.id}")
        return []

    issues = result.get("data", [])
    if not issues:
        return []

    # Filter out PRs (GitHub API returns PRs in issues endpoint)
    issues = [i for i in issues if "pull_request" not in i]

    last_seen = trigger.last_seen_id
    events = []
    for issue in issues:
        issue_id = str(issue.get("number", ""))
        if issue_id == last_seen:
            break

        # Label filter
        if filters.get("labels"):
            required_labels = set(l.strip() for l in filters["labels"].split(","))
            issue_labels = set(l.get("name", "") for l in issue.get("labels", []))
            if not required_labels.intersection(issue_labels):
                continue

        events.append(TriggerEvent(
            trigger_id=trigger.id,
            trigger_type="github_new_issue",
            provider="github",
            connection_id=trigger.connection_id,
            data={
                "message_id": issue_id,
                "issue_number": issue.get("number"),
                "title": issue.get("title", ""),
                "body": (issue.get("body") or "")[:500],
                "state": issue.get("state", ""),
                "user": issue.get("user", {}).get("login", ""),
                "labels": [l.get("name", "") for l in issue.get("labels", [])],
                "url": issue.get("html_url", ""),
                "created_at": issue.get("created_at", ""),
            },
            raw=issue,
        ))

    return events


async def poll_github_new_pr(
    api: AnyTool,
    trigger: TriggerConfig,
) -> List[TriggerEvent]:
    """Poll GitHub repo for new pull requests.

    Filters:
      owner (required), repo (required)
      state: open (default), closed, all
    """
    filters = trigger.filters or {}
    owner = filters.get("owner", "")
    repo = filters.get("repo", "")
    if not owner or not repo:
        return []

    result = await api.call(
        "github_list_prs",
        connection_id=trigger.connection_id,
        owner=owner,
        repo=repo,
        state=filters.get("state", "open"),
        sort="created",
        direction="desc",
        per_page=20,
    )

    if not result.get("successful"):
        return []

    prs = result.get("data", [])
    if not prs:
        return []

    last_seen = trigger.last_seen_id
    events = []
    for pr in prs:
        pr_id = str(pr.get("number", ""))
        if pr_id == last_seen:
            break

        events.append(TriggerEvent(
            trigger_id=trigger.id,
            trigger_type="github_new_pr",
            provider="github",
            connection_id=trigger.connection_id,
            data={
                "message_id": pr_id,
                "pr_number": pr.get("number"),
                "title": pr.get("title", ""),
                "body": (pr.get("body") or "")[:500],
                "state": pr.get("state", ""),
                "user": pr.get("user", {}).get("login", ""),
                "head_branch": pr.get("head", {}).get("ref", ""),
                "base_branch": pr.get("base", {}).get("ref", ""),
                "url": pr.get("html_url", ""),
                "created_at": pr.get("created_at", ""),
                "draft": pr.get("draft", False),
            },
            raw=pr,
        ))

    return events


# ── HubSpot ──────────────────────────────────────────────────────────

async def poll_hubspot_new_contact(
    api: AnyTool,
    trigger: TriggerConfig,
) -> List[TriggerEvent]:
    """Poll HubSpot for new contacts.

    Filters:
      property: Filter by a specific property
      value: Expected value for the property
    """
    result = await api.call(
        "hubspot_list_contacts",
        connection_id=trigger.connection_id,
        limit=20,
    )

    if not result.get("successful"):
        return []

    contacts = result.get("data", {}).get("results", [])
    if not contacts:
        return []

    # Sort by created date descending
    contacts.sort(key=lambda c: c.get("createdAt", ""), reverse=True)

    last_seen = trigger.last_seen_id
    events = []
    for contact in contacts:
        contact_id = str(contact.get("id", ""))
        if contact_id == last_seen:
            break

        props = contact.get("properties", {})

        # Apply property filter
        filters = trigger.filters or {}
        if filters.get("property") and filters.get("value"):
            if props.get(filters["property"]) != filters["value"]:
                continue

        events.append(TriggerEvent(
            trigger_id=trigger.id,
            trigger_type="hubspot_new_contact",
            provider="hubspot",
            connection_id=trigger.connection_id,
            data={
                "message_id": contact_id,
                "contact_id": contact_id,
                "email": props.get("email", ""),
                "firstname": props.get("firstname", ""),
                "lastname": props.get("lastname", ""),
                "company": props.get("company", ""),
                "phone": props.get("phone", ""),
                "created_at": contact.get("createdAt", ""),
            },
            raw=contact,
        ))

    return events


async def poll_hubspot_new_deal(
    api: AnyTool,
    trigger: TriggerConfig,
) -> List[TriggerEvent]:
    """Poll HubSpot for new deals.

    Filters:
      pipeline: Filter by pipeline name
      dealstage: Filter by deal stage
    """
    result = await api.call(
        "hubspot_search_deals",
        connection_id=trigger.connection_id,
        limit=20,
    )

    if not result.get("successful"):
        return []

    deals = result.get("data", {}).get("results", [])
    if not deals:
        return []

    deals.sort(key=lambda d: d.get("createdAt", ""), reverse=True)

    last_seen = trigger.last_seen_id
    events = []
    filters = trigger.filters or {}
    for deal in deals:
        deal_id = str(deal.get("id", ""))
        if deal_id == last_seen:
            break

        props = deal.get("properties", {})

        if filters.get("pipeline") and props.get("pipeline") != filters["pipeline"]:
            continue
        if filters.get("dealstage") and props.get("dealstage") != filters["dealstage"]:
            continue

        events.append(TriggerEvent(
            trigger_id=trigger.id,
            trigger_type="hubspot_new_deal",
            provider="hubspot",
            connection_id=trigger.connection_id,
            data={
                "message_id": deal_id,
                "deal_id": deal_id,
                "dealname": props.get("dealname", ""),
                "amount": props.get("amount", ""),
                "pipeline": props.get("pipeline", ""),
                "dealstage": props.get("dealstage", ""),
                "closedate": props.get("closedate", ""),
                "created_at": deal.get("createdAt", ""),
            },
            raw=deal,
        ))

    return events


# ── Freshdesk ────────────────────────────────────────────────────────

async def poll_freshdesk_new_ticket(
    api: AnyTool,
    trigger: TriggerConfig,
) -> List[TriggerEvent]:
    """Poll Freshdesk for new tickets.

    Filters:
      status: Filter by status (2=open, 3=pending, 4=resolved, 5=closed)
      priority: Filter by priority (1=low, 2=medium, 3=high, 4=urgent)
    """
    result = await api.call(
        "freshdesk_list_tickets",
        connection_id=trigger.connection_id,
        order_by="created_at",
        order_type="desc",
        per_page=20,
    )

    if not result.get("successful"):
        return []

    tickets = result.get("data", [])
    if not tickets:
        return []

    last_seen = trigger.last_seen_id
    events = []
    filters = trigger.filters or {}
    for ticket in tickets:
        ticket_id = str(ticket.get("id", ""))
        if ticket_id == last_seen:
            break

        if filters.get("status") and ticket.get("status") != int(filters["status"]):
            continue
        if filters.get("priority") and ticket.get("priority") != int(filters["priority"]):
            continue

        events.append(TriggerEvent(
            trigger_id=trigger.id,
            trigger_type="freshdesk_new_ticket",
            provider="freshdesk",
            connection_id=trigger.connection_id,
            data={
                "message_id": ticket_id,
                "ticket_id": ticket_id,
                "subject": ticket.get("subject", ""),
                "description_text": (ticket.get("description_text") or "")[:500],
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "requester_id": ticket.get("requester_id"),
                "responder_id": ticket.get("responder_id"),
                "created_at": ticket.get("created_at", ""),
            },
            raw=ticket,
        ))

    return events


# ── Zendesk ──────────────────────────────────────────────────────────

async def poll_zendesk_new_ticket(
    api: AnyTool,
    trigger: TriggerConfig,
) -> List[TriggerEvent]:
    """Poll Zendesk for new tickets.

    Filters:
      status: new, open, pending, hold, solved, closed
      priority: low, normal, high, urgent
    """
    result = await api.call(
        "zendesk_list_tickets",
        connection_id=trigger.connection_id,
        sort_by="created_at",
        sort_order="desc",
    )

    if not result.get("successful"):
        return []

    tickets = result.get("data", {}).get("tickets", [])
    if not tickets:
        return []

    last_seen = trigger.last_seen_id
    events = []
    filters = trigger.filters or {}
    for ticket in tickets:
        ticket_id = str(ticket.get("id", ""))
        if ticket_id == last_seen:
            break

        if filters.get("status") and ticket.get("status") != filters["status"]:
            continue
        if filters.get("priority") and ticket.get("priority") != filters["priority"]:
            continue

        events.append(TriggerEvent(
            trigger_id=trigger.id,
            trigger_type="zendesk_new_ticket",
            provider="zendesk",
            connection_id=trigger.connection_id,
            data={
                "message_id": ticket_id,
                "ticket_id": ticket_id,
                "subject": ticket.get("subject", ""),
                "description": (ticket.get("description") or "")[:500],
                "status": ticket.get("status", ""),
                "priority": ticket.get("priority", ""),
                "requester_id": ticket.get("requester_id"),
                "assignee_id": ticket.get("assignee_id"),
                "created_at": ticket.get("created_at", ""),
            },
            raw=ticket,
        ))

    return events


# ── Poller Registry ──────────────────────────────────────────────────

POLLERS = {
    "gmail_new_message": poll_gmail_new_message,
    "slack_new_message": poll_slack_new_message,
    "github_new_issue": poll_github_new_issue,
    "github_new_pr": poll_github_new_pr,
    "hubspot_new_contact": poll_hubspot_new_contact,
    "hubspot_new_deal": poll_hubspot_new_deal,
    "freshdesk_new_ticket": poll_freshdesk_new_ticket,
    "zendesk_new_ticket": poll_zendesk_new_ticket,
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
