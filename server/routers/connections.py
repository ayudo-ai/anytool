"""
Connection management — OAuth flows + listing connected apps.

POST /v1/connections       → start OAuth flow, get auth URL
GET  /v1/connections       → list connected apps
GET  /v1/connections/check → check if user+provider is connected
DELETE /v1/connections     → disconnect
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_account
from server.engine import get_api

router = APIRouter(prefix="/connections", tags=["connections"])


# ── Provider mapping ─────────────────────────────────────────────────
# Developers use friendly names. We map to Nango provider keys.

PROVIDER_MAP = {
    "gmail": "google",
    "google_drive": "google",
    "google_sheets": "google",
    "google_calendar": "google",
    "google_docs": "google",
    "google": "google",
    "slack": "slack",
    "docusign": "docusign",
    "freshdesk": "freshdesk",
    "hubspot": "hubspot",
    "github": "github",
    "zendesk": "zendesk",
    "whatsapp": "whatsapp",
}


# ── Request/Response models ──────────────────────────────────────────

class ConnectRequest(BaseModel):
    provider: str  # gmail, slack, docusign, etc.
    user_id: str  # end-user in YOUR app
    callback_url: str = ""


class DisconnectRequest(BaseModel):
    provider: str
    user_id: str


# ── Routes ───────────────────────────────────────────────────────────

@router.post("")
async def connect_app(body: ConnectRequest, account: dict = Depends(get_account)):
    """Start OAuth flow for an end-user to connect an app.

    Returns an auth_url — redirect your user there.

    Example:
        POST /v1/connections
        {"provider": "gmail", "user_id": "customer-123"}
        → {"auth_url": "https://accounts.google.com/o/oauth2/..."}
    """
    nango_provider = PROVIDER_MAP.get(body.provider.lower())
    if not nango_provider:
        raise HTTPException(400, f"Unknown provider: {body.provider}. Available: {list(PROVIDER_MAP.keys())}")

    api = get_api()
    try:
        auth_url = await api.get_auth_url(
            provider=nango_provider,
            connection_id=body.user_id,
            callback_url=body.callback_url,
        )
        return {
            "auth_url": auth_url,
            "user_id": body.user_id,
            "provider": body.provider,
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to start OAuth: {e}")


@router.get("")
async def list_connections(
    user_id: Optional[str] = None,
    account: dict = Depends(get_account),
):
    """List all connected apps, optionally filtered by user_id."""
    api = get_api()
    try:
        connections = await api.list_connections(connection_id=user_id or "")
        result = []
        for conn in connections:
            if isinstance(conn, dict):
                result.append({
                    "provider": conn.get("provider_config_key", ""),
                    "user_id": conn.get("connection_id", ""),
                    "status": "active",
                })
        return {"connections": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(500, f"Failed to list connections: {e}")


@router.get("/check")
async def check_connection(
    provider: str,
    user_id: str,
    account: dict = Depends(get_account),
):
    """Check if a specific user+provider connection exists."""
    nango_provider = PROVIDER_MAP.get(provider.lower(), provider)
    api = get_api()
    connected = await api.is_connected(nango_provider, user_id)
    return {"connected": connected, "provider": provider, "user_id": user_id}


@router.delete("")
async def disconnect_app(body: DisconnectRequest, account: dict = Depends(get_account)):
    """Disconnect an app for a user."""
    nango_provider = PROVIDER_MAP.get(body.provider.lower(), body.provider)
    api = get_api()
    try:
        await api.disconnect(nango_provider, body.user_id)
        return {"disconnected": True, "provider": body.provider, "user_id": body.user_id}
    except Exception as e:
        raise HTTPException(500, f"Disconnect failed: {e}")
