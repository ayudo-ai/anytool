"""
Inbound webhook receiver — receives push events from providers (GitHub, Slack, etc).

Instead of polling every 90s, providers push events here in real-time.
We normalize the payload and forward to the developer's webhook_url.

POST /v1/webhooks/github/{trigger_id}   → receive GitHub webhook events
POST /v1/webhooks/slack/{trigger_id}    → receive Slack Events API
POST /v1/webhooks/hubspot/{trigger_id}  → receive HubSpot webhook events

The developer's experience is identical whether we poll or receive webhooks.
Same trigger deploy, same webhook format on their end.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from loguru import logger

from anytool.triggers.base import TriggerEvent
from server.database import get_record, put_record, new_id

router = APIRouter(prefix="/webhooks", tags=["webhooks-inbound"])


# ── GitHub Webhooks ──────────────────────────────────────────────────

@router.post("/github/{trigger_id}")
async def receive_github_webhook(trigger_id: str, request: Request):
    """Receive webhook events from GitHub.

    GitHub sends events when issues are opened, PRs created, code pushed, etc.
    We verify the signature, normalize the payload, and forward to the developer's webhook.
    """
    body = await request.body()
    headers = dict(request.headers)

    # Verify GitHub signature
    trigger_record = await get_record("trigger", trigger_id)
    if not trigger_record:
        raise HTTPException(404, "Trigger not found")

    trigger_data = trigger_record.custom_data or {}
    webhook_secret = trigger_data.get("webhook_secret", "")

    if webhook_secret:
        signature = headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(
            webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning(f"[webhooks.github] Invalid signature | trigger={trigger_id}")
            raise HTTPException(401, "Invalid signature")

    # Parse event
    event_type = headers.get("x-github-event", "")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    logger.info(f"[webhooks.github] Received | trigger={trigger_id} event={event_type}")

    # Normalize based on event type
    event_data = _normalize_github_event(event_type, payload)
    if not event_data:
        # Event type we don't care about — acknowledge but don't forward
        return {"received": True, "forwarded": False, "reason": f"Ignoring event type: {event_type}"}

    # Build TriggerEvent
    event = TriggerEvent(
        trigger_id=trigger_id,
        trigger_type=f"github_{event_type}",
        provider="github",
        connection_id=trigger_data.get("user_id", trigger_data.get("connection_id", "")),
        data=event_data,
        raw=payload,
    )

    # Forward to developer's webhook
    webhook_url = trigger_data.get("webhook_url", "")
    if not webhook_url:
        return {"received": True, "forwarded": False, "reason": "No webhook_url configured"}

    success = await _forward_event(event, webhook_url, trigger_record)
    return {"received": True, "forwarded": success}


def _normalize_github_event(event_type: str, payload: dict) -> Optional[dict]:
    """Normalize GitHub webhook payload to standard event data."""

    if event_type == "issues" and payload.get("action") == "opened":
        issue = payload.get("issue", {})
        return {
            "message_id": str(issue.get("number", "")),
            "event": "issue_opened",
            "issue_number": issue.get("number"),
            "title": issue.get("title", ""),
            "body": (issue.get("body") or "")[:500],
            "state": issue.get("state", ""),
            "user": issue.get("user", {}).get("login", ""),
            "labels": [l.get("name", "") for l in issue.get("labels", [])],
            "url": issue.get("html_url", ""),
            "created_at": issue.get("created_at", ""),
            "repo": payload.get("repository", {}).get("full_name", ""),
        }

    if event_type == "pull_request" and payload.get("action") in ("opened", "synchronize"):
        pr = payload.get("pull_request", {})
        return {
            "message_id": str(pr.get("number", "")),
            "event": f"pr_{payload['action']}",
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
            "repo": payload.get("repository", {}).get("full_name", ""),
        }

    if event_type == "push":
        commits = payload.get("commits", [])
        return {
            "message_id": payload.get("after", "")[:12],
            "event": "push",
            "ref": payload.get("ref", ""),
            "branch": payload.get("ref", "").replace("refs/heads/", ""),
            "pusher": payload.get("pusher", {}).get("name", ""),
            "commit_count": len(commits),
            "commits": [
                {
                    "id": c.get("id", "")[:12],
                    "message": c.get("message", "")[:200],
                    "author": c.get("author", {}).get("name", ""),
                    "url": c.get("url", ""),
                }
                for c in commits[:10]  # cap at 10 commits
            ],
            "compare_url": payload.get("compare", ""),
            "repo": payload.get("repository", {}).get("full_name", ""),
        }

    if event_type == "star" and payload.get("action") == "created":
        return {
            "message_id": str(payload.get("sender", {}).get("id", "")),
            "event": "starred",
            "user": payload.get("sender", {}).get("login", ""),
            "repo": payload.get("repository", {}).get("full_name", ""),
            "stars_count": payload.get("repository", {}).get("stargazers_count", 0),
        }

    if event_type == "issue_comment" and payload.get("action") == "created":
        comment = payload.get("comment", {})
        return {
            "message_id": str(comment.get("id", "")),
            "event": "issue_comment",
            "issue_number": payload.get("issue", {}).get("number"),
            "issue_title": payload.get("issue", {}).get("title", ""),
            "comment_body": (comment.get("body") or "")[:500],
            "user": comment.get("user", {}).get("login", ""),
            "url": comment.get("html_url", ""),
            "repo": payload.get("repository", {}).get("full_name", ""),
        }

    # Unknown event type
    return None


# ── Shared forwarding logic ──────────────────────────────────────────

async def _forward_event(event: TriggerEvent, webhook_url: str, trigger_record) -> bool:
    """Forward a normalized event to the developer's webhook URL."""
    import httpx
    import os

    payload = event.to_webhook_payload()
    payload_bytes = json.dumps(payload, default=str).encode()

    headers = {"Content-Type": "application/json"}

    # Sign with platform webhook secret
    webhook_secret = os.environ.get("ANYTOOL_WEBHOOK_SECRET", "")
    if webhook_secret:
        sig = hmac.new(webhook_secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
        headers["X-Anytool-Signature"] = f"sha256={sig}"
        headers["X-Anytool-Timestamp"] = datetime.now(timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, content=payload_bytes, headers=headers)

        success = resp.is_success
        logger.info(
            f"[webhooks.inbound] Forwarded | trigger={event.trigger_id} "
            f"event={event.data.get('event', '?')} | → {webhook_url} | "
            f"status={resp.status_code}"
        )
    except Exception as e:
        success = False
        logger.error(f"[webhooks.inbound] Forward failed | trigger={event.trigger_id} | {e}")

    # Log to webhook_log
    try:
        account_id = trigger_record.account_id if trigger_record else ""
        workspace_id = trigger_record.workspace_id if trigger_record else ""
        await put_record(
            object_slug="webhook_log",
            primary_key=new_id(),
            account_id=account_id,
            workspace_id=workspace_id,
            data={
                "trigger_id": event.trigger_id,
                "user_id": event.connection_id,
                "webhook_url": webhook_url,
                "event_type": event.data.get("event", event.trigger_type),
                "event_data": event.data,
                "status_code": resp.status_code if success else 0,
                "successful": success,
                "retry_count": 0,
                "error": None if success else "Delivery failed",
                "source": "webhook",  # vs "poll" for polling triggers
            },
        )
    except Exception:
        pass

    return success
