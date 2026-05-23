"""
Trigger management — per user_id, each with its own webhook_url.

A user can have multiple triggers, each pointing to a different webhook.
Triggers poll for events and POST to the specified webhook_url.

POST   /v1/triggers       → deploy trigger for a user
GET    /v1/triggers       → list triggers (filter by user_id)
DELETE /v1/triggers/{id}  → remove a trigger
GET    /v1/triggers/types → list available trigger types
"""

from __future__ import annotations

import ipaddress
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from loguru import logger

from server.auth import get_auth_context, AuthContext
from server.database import (
    put_record, get_record, list_records, delete_record, update_record_fields, new_id,
)
from server.trigger_engine import get_trigger_engine
from server.engine import get_api_for_workspace
from server.config import config as server_config
from anytool.triggers.loader import TriggerSpecLoader

router = APIRouter(prefix="/triggers", tags=["triggers"])


# ── Spec-based trigger registry ──────────────────────────────────────

_trigger_loader: Optional[TriggerSpecLoader] = None


def _get_trigger_loader() -> TriggerSpecLoader:
    """Get the trigger spec loader (lazy singleton)."""
    global _trigger_loader
    if _trigger_loader is None:
        _trigger_loader = TriggerSpecLoader("registry/")
    return _trigger_loader


def _get_trigger_info(trigger_type: str) -> Optional[Dict[str, Any]]:
    """Look up trigger info from YAML specs. Returns dict compatible with old TRIGGER_MAP format."""
    loader = _get_trigger_loader()
    spec = loader.get_trigger(trigger_type)
    if not spec:
        return None
    return {
        "trigger_type": spec.trigger,
        "provider": spec.provider,
        "mode": spec.mode,
        "events": spec.events,
    }


def _validate_webhook_url(url: str) -> None:
    """Validate webhook URL — block private IPs and non-HTTPS (except localhost)."""
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "Webhook URL must use http or https")

    hostname = parsed.hostname or ""

    # Allow localhost for development
    if hostname in ("localhost", "127.0.0.1", "::1"):
        return

    # Require HTTPS for non-localhost
    if parsed.scheme != "https":
        raise HTTPException(400, "Webhook URL must use HTTPS (http only allowed for localhost)")

    # Block private/reserved IPs
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
            raise HTTPException(400, "Webhook URL cannot point to private/reserved IP addresses")
    except ValueError:
        pass  # hostname is a domain, not an IP — that's fine


class DeployTriggerRequest(BaseModel):
    trigger_type: str                   # gmail_new_message
    user_id: str                        # end-user whose connection to poll
    webhook_url: str                    # where to POST events (unique per trigger)
    filters: Dict[str, Any] = {}       # from_contains, subject_contains, etc.
    poll_interval_seconds: int = 90


async def _setup_provider_webhook(
    trigger_id: str,
    trigger_info: dict,
    filters: dict,
    user_id: str,
    ctx: "AuthContext",
) -> Optional[dict]:
    """Auto-register a webhook on the provider (e.g. GitHub) for real-time triggers.

    Returns setup info (hook_id, webhook_url) or None on failure.
    """
    provider = trigger_info["provider"]
    events = trigger_info.get("events", [])

    if provider == "github":
        owner = filters.get("owner", "")
        repo = filters.get("repo", "")
        if not owner or not repo:
            raise HTTPException(
                400,
                "GitHub webhook triggers require 'owner' and 'repo' in filters."
            )

        # Build the inbound webhook URL that GitHub will POST to
        inbound_url = f"{server_config.base_url}{server_config.api_prefix}/webhooks/github/{trigger_id}"

        # Generate a secret for signature verification
        import secrets
        webhook_secret = secrets.token_hex(20)

        # Register webhook on GitHub using the user's connection
        api = await get_api_for_workspace(ctx.workspace_id, ctx.account_id)
        try:
            result = await api.call(
                "github_create_webhook",
                connection_id=user_id,
                owner=owner,
                repo=repo,
                url=inbound_url,
                events=events,
                secret=webhook_secret,
            )

            if result.get("successful"):
                hook_id = result.get("data", {}).get("id", "")
                from loguru import logger
                logger.info(
                    f"[triggers] GitHub webhook registered | trigger={trigger_id} "
                    f"repo={owner}/{repo} hook_id={hook_id} events={events}"
                )
                # Store webhook secret for signature verification
                await update_record_fields("trigger", trigger_id, {
                    "webhook_secret": webhook_secret,
                })
                return {
                    "hook_id": str(hook_id),
                    "inbound_url": inbound_url,
                    "events": events,
                    "repo": f"{owner}/{repo}",
                }
            else:
                error = result.get("error", "Unknown error")
                raise HTTPException(500, f"Failed to create GitHub webhook: {error}")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Failed to register GitHub webhook: {e}")

    return None


# ── Routes ───────────────────────────────────────────────────────────

@router.post("")
async def deploy_trigger(body: DeployTriggerRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Deploy a trigger for a user with a specific webhook URL.

    Each trigger polls independently and delivers events to its own webhook_url.
    A single user can have multiple triggers — e.g., one for inbox alerts,
    another for invoice detection, each going to different webhooks.

    Example:
        POST /v1/triggers
        {
            "trigger_type": "gmail_new_message",
            "user_id": "customer-123",
            "webhook_url": "https://myapp.com/webhooks/inbox-alerts",
            "filters": {"from_contains": "vendor@example.com"},
            "poll_interval_seconds": 60
        }
    """
    # Check trigger limit per workspace
    existing = await list_records("trigger", account_id=ctx.account_id, workspace_id=ctx.workspace_id)
    max_triggers = ctx.limits.get("max_triggers", 5)
    if max_triggers > 0 and len(existing) >= max_triggers:
        raise HTTPException(
            429,
            f"Trigger limit reached ({max_triggers}). Upgrade at anytool.dev"
        )

    # Validate webhook URL (SSRF protection)
    _validate_webhook_url(body.webhook_url)

    # Validate trigger type (from YAML specs)
    trigger_info = _get_trigger_info(body.trigger_type.lower())
    if not trigger_info:
        loader = _get_trigger_loader()
        available = [s.trigger for s in loader.list_triggers()]
        raise HTTPException(
            400,
            f"Unknown trigger type: {body.trigger_type}. "
            f"Available: {available}"
        )

    trigger_id = new_id()

    trigger_mode = trigger_info.get("mode", "poll")

    # Save to DB
    trigger_data = {
        "trigger_type": trigger_info["trigger_type"],
        "provider": trigger_info["provider"],
        "user_id": body.user_id,
        "webhook_url": body.webhook_url,
        "filters": body.filters,
        "poll_interval_seconds": body.poll_interval_seconds,
        "enabled": False,  # enabled after setup completes
        "mode": trigger_mode,
        "last_seen_id": "",
        "last_poll_at": None,
    }

    await put_record(
        object_slug="trigger",
        primary_key=trigger_id,
        account_id=ctx.account_id,
        workspace_id=ctx.workspace_id,
        data=trigger_data,
    )

    webhook_setup = None

    if trigger_mode == "webhook":
        # Webhook mode — register a webhook on the provider (e.g. GitHub)
        webhook_setup = await _setup_provider_webhook(
            trigger_id=trigger_id,
            trigger_info=trigger_info,
            filters=body.filters,
            user_id=body.user_id,
            ctx=ctx,
        )
        # Enable the trigger (no polling needed)
        await update_record_fields("trigger", trigger_id, {
            "enabled": True,
            "webhook_setup": webhook_setup,
        })
    else:
        # Polling mode — baseline then enable via trigger engine
        engine = await get_trigger_engine()
        from anytool.triggers.base import TriggerConfig

        await engine.register(TriggerConfig(
            id=trigger_id,
            trigger_type=trigger_info["trigger_type"],
            provider=trigger_info["provider"],
            connection_id=body.user_id,
            webhook_url=body.webhook_url,
            filters=body.filters,
            poll_interval_seconds=body.poll_interval_seconds,
        ))

    return {
        "trigger_id": trigger_id,
        "trigger_type": body.trigger_type,
        "user_id": body.user_id,
        "webhook_url": body.webhook_url,
        "mode": trigger_mode,
        "status": "active",
        "webhook_setup": webhook_setup,
    }


@router.get("")
async def list_triggers(
    user_id: Optional[str] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """List triggers, optionally filtered by user_id.

    Without user_id: returns all triggers in this workspace.
    With user_id: returns only that user's triggers.
    """
    records = await list_records(
        "trigger",
        account_id=ctx.account_id,
        workspace_id=ctx.workspace_id,
    )

    triggers = []
    for r in records:
        data = r.custom_data or {}

        # Filter by user_id if provided
        if user_id and data.get("user_id") != user_id:
            continue

        triggers.append({
            "trigger_id": r.primary_field_value,
            "trigger_type": data.get("trigger_type", ""),
            "provider": data.get("provider", ""),
            "user_id": data.get("user_id", ""),
            "webhook_url": data.get("webhook_url", ""),
            "filters": data.get("filters", {}),
            "poll_interval_seconds": data.get("poll_interval_seconds", 90),
            "enabled": data.get("enabled", True),
            "last_poll_at": data.get("last_poll_at"),
            "created_at": str(r.created_at) if r.created_at else "",
        })

    return {"triggers": triggers, "total": len(triggers)}


@router.delete("/{trigger_id}")
async def remove_trigger(trigger_id: str, ctx: AuthContext = Depends(get_auth_context)):
    """Remove a trigger — stops polling and deletes config."""
    record = await get_record("trigger", trigger_id)
    if not record or record.account_id != ctx.account_id:
        raise HTTPException(404, "Trigger not found")

    # Remove from live engine
    engine = await get_trigger_engine()
    await engine.unregister(trigger_id)

    # Soft delete from DB
    await delete_record("trigger", trigger_id)

    return {"removed": True, "trigger_id": trigger_id}


@router.get("/types")
async def list_trigger_types(
    app: Optional[str] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """List available trigger types from YAML specs, optionally filtered by app/provider."""
    loader = _get_trigger_loader()
    specs = loader.list_triggers(provider=app) if app else loader.list_triggers()

    trigger_types = [spec.to_api_dict() for spec in specs]
    return {"trigger_types": trigger_types}
