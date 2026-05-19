"""
Connection management — per user_id (end-user in developer's app).

Each user connects their own apps. Connections are scoped to user_id,
not workspace. The workspace just owns the API key for billing.

POST /v1/connections           → start OAuth for a user
GET  /v1/connections           → list connections (filter by user_id)
GET  /v1/connections/check     → check if user has connected a provider
DELETE /v1/connections         → disconnect a user's app
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_auth_context, AuthContext
from server.engine import get_api

router = APIRouter(prefix="/connections", tags=["connections"])


# ── Provider mapping ─────────────────────────────────────────────────

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


# ── Models ───────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    provider: str   # gmail, slack, docusign, etc.
    user_id: str    # end-user in YOUR app (customer-123, john@acme.com, etc.)
    callback_url: str = ""


class DisconnectRequest(BaseModel):
    provider: str
    user_id: str


# ── Routes ───────────────────────────────────────────────────────────

@router.post("")
async def connect_app(body: ConnectRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Start OAuth flow for an end-user to connect an app.

    The user_id is YOUR user — a customer, employee, or workspace member.
    Each user manages their own OAuth connections independently.

    Example:
        POST /v1/connections
        {"provider": "gmail", "user_id": "customer-123"}
        → {"auth_url": "https://accounts.google.com/o/oauth2/..."}
    """
    nango_provider = PROVIDER_MAP.get(body.provider.lower())
    if not nango_provider:
        raise HTTPException(
            400,
            f"Unknown provider: {body.provider}. "
            f"Available: {list(PROVIDER_MAP.keys())}"
        )

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
    ctx: AuthContext = Depends(get_auth_context),
):
    """List connected apps, optionally filtered by user_id.

    Without user_id: returns ALL connections across all users.
    With user_id: returns only that user's connections.
    """
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
    ctx: AuthContext = Depends(get_auth_context),
):
    """Check if a specific user has connected a provider."""
    nango_provider = PROVIDER_MAP.get(provider.lower(), provider)
    api = get_api()
    connected = await api.is_connected(nango_provider, user_id)
    return {"connected": connected, "provider": provider, "user_id": user_id}


@router.delete("")
async def disconnect_app(body: DisconnectRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Disconnect an app for a user."""
    nango_provider = PROVIDER_MAP.get(body.provider.lower(), body.provider)
    api = get_api()
    try:
        await api.disconnect(nango_provider, body.user_id)
        return {"disconnected": True, "provider": body.provider, "user_id": body.user_id}
    except Exception as e:
        raise HTTPException(500, f"Disconnect failed: {e}")
