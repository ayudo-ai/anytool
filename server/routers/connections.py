"""
Connection management — OAuth flows + status tracking.

POST /v1/connections           → start OAuth for an end-user
GET  /v1/connections/callback  → handle OAuth callback (redirect from Google/Slack/etc)
GET  /v1/connections           → list connections
GET  /v1/connections/check     → check if user has connected a provider
DELETE /v1/connections         → disconnect a user's app
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from server.auth import get_auth_context, AuthContext
from server.database import put_record, list_records, delete_record, now
from server.engine import get_api, get_api_for_workspace

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
    user_id: str    # end-user in YOUR app


class DisconnectRequest(BaseModel):
    provider: str
    user_id: str


class ApiKeyConnectRequest(BaseModel):
    provider: str     # freshdesk, zendesk
    user_id: str      # end-user in YOUR app
    api_key: str      # the end-user's API key for this provider
    domain: str = ""  # e.g. "yourcompany.freshdesk.com"


# Providers that use API key auth instead of OAuth
API_KEY_PROVIDERS = {"freshdesk", "zendesk", "whatsapp"}


# ── Routes ───────────────────────────────────────────────────────────

@router.post("")
async def connect_app(body: ConnectRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Start OAuth flow for an end-user to connect an app.

    Returns an auth_url to redirect the end-user to.
    After they authorize, they'll be redirected to /v1/connections/callback
    which exchanges the code for tokens and stores them encrypted in our DB.

    Example:
        POST /v1/connections
        {"provider": "gmail", "user_id": "customer-123"}
        → {"auth_url": "https://accounts.google.com/o/oauth2/..."}
    """
    provider = PROVIDER_MAP.get(body.provider.lower())
    if not provider:
        raise HTTPException(
            400,
            f"Unknown provider: {body.provider}. "
            f"Available: {list(PROVIDER_MAP.keys())}"
        )

    api = await get_api_for_workspace(ctx.workspace_id, ctx.account_id)
    try:
        auth_url = await api.get_auth_url(
            provider=provider,
            connection_id=body.user_id,
            account_id=ctx.account_id,
            workspace_id=ctx.workspace_id,
        )

        # Track the connection attempt
        connection_key = f"{body.user_id}:{provider}"
        await put_record(
            object_slug="connection",
            primary_key=connection_key,
            account_id=ctx.account_id,
            workspace_id=ctx.workspace_id,
            data={
                "user_id": body.user_id,
                "provider": provider,
                "status": "pending",
                "connected_at": "",
            },
        )

        return {
            "auth_url": auth_url,
            "user_id": body.user_id,
            "provider": body.provider,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to start OAuth: {e}")


@router.post("/api-key")
async def connect_api_key(body: ApiKeyConnectRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Connect an app using API key auth (Freshdesk, Zendesk, WhatsApp).

    No OAuth flow needed — the developer provides the API key directly.
    The key is encrypted and stored, same as OAuth tokens.

    Example:
        POST /v1/connections/api-key
        {"provider": "freshdesk", "user_id": "customer-123",
         "api_key": "your-freshdesk-key", "domain": "yourcompany.freshdesk.com"}
    """
    provider = PROVIDER_MAP.get(body.provider.lower(), body.provider.lower())
    if provider not in API_KEY_PROVIDERS:
        raise HTTPException(
            400,
            f"Provider '{body.provider}' uses OAuth, not API key auth. "
            f"Use POST /v1/connections instead. "
            f"API key providers: {list(API_KEY_PROVIDERS)}"
        )

    if not body.api_key:
        raise HTTPException(400, "api_key is required")

    # Clean domain — strip protocol and trailing slashes
    domain = body.domain.strip()
    domain = domain.replace("https://", "").replace("http://", "").rstrip("/")

    # Store as UserTokens with api_key field
    from anytool.auth.models import UserTokens
    from server.token_store import PostgresTokenStore

    store = PostgresTokenStore()
    tokens = UserTokens(
        app=provider,
        user_id=body.user_id,
        access_token="",
        api_key=body.api_key,
        domain=body.domain,
        token_type="api_key",
        scopes=[],
    )
    await store.save_tokens(tokens)

    # Track connection
    connection_key = f"{body.user_id}:{provider}"
    await put_record(
        object_slug="connection",
        primary_key=connection_key,
        account_id=ctx.account_id,
        workspace_id=ctx.workspace_id,
        data={
            "user_id": body.user_id,
            "provider": provider,
            "status": "active",
            "connected_at": now().isoformat(),
            "auth_type": "api_key",
            "domain": body.domain,
        },
    )

    return {
        "connected": True,
        "provider": provider,
        "user_id": body.user_id,
        "auth_type": "api_key",
    }


@router.get("/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """Handle OAuth callback from providers (Google, Slack, etc).

    The provider redirects here after the user authorizes.
    We exchange the code for tokens, store them encrypted, and show a success page.

    This is a GET endpoint (browser redirect) — no auth header needed.
    The state parameter links back to the original connect request.
    Workspace context is recovered from the stored OAuth state.
    """
    # First, peek at the state to get workspace context
    from server.token_store import PostgresTokenStore
    store = PostgresTokenStore()
    oauth_state = await store.get_oauth_state(state)

    if oauth_state and oauth_state.account_id and oauth_state.workspace_id:
        # Use workspace-specific API (with workspace's auth config credentials)
        api = await get_api_for_workspace(oauth_state.workspace_id, oauth_state.account_id)
        # Re-save state since get_oauth_state consumed it
        await store.save_oauth_state(oauth_state)
        account_id = oauth_state.account_id
        workspace_id = oauth_state.workspace_id
    else:
        # Fallback to global API (backward compat)
        api = get_api()
        account_id = ""
        workspace_id = ""

    try:
        # The OAuth manager verifies state, exchanges code, saves tokens
        tokens = await api.handle_callback(
            app="",  # Will be resolved from state
            code=code,
            state=state,
        )

        # Update connection status to active — scoped to workspace
        connection_key = f"{tokens.user_id}:{tokens.app}"
        await put_record(
            object_slug="connection",
            primary_key=connection_key,
            account_id=account_id,
            workspace_id=workspace_id,
            data={
                "user_id": tokens.user_id,
                "provider": tokens.app,
                "status": "active",
                "connected_at": now().isoformat(),
                "scopes": tokens.scopes,
            },
        )

        # Return a simple success page (this is a browser redirect)
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Connected!</title>
        <style>
            body {{ font-family: Inter, system-ui, sans-serif; display: flex;
                   align-items: center; justify-content: center; min-height: 100vh;
                   margin: 0; background: #fafafa; }}
            .card {{ background: white; border-radius: 12px; padding: 40px;
                    text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            h1 {{ font-size: 24px; margin: 0 0 8px; }}
            p {{ color: #666; font-size: 14px; margin: 0; }}
            .check {{ font-size: 48px; margin-bottom: 16px; }}
        </style>
        </head>
        <body>
            <div class="card">
                <div class="check">✅</div>
                <h1>Connected!</h1>
                <p>{tokens.app.title()} connected for user {tokens.user_id}</p>
                <p style="margin-top: 12px; font-size: 12px; color: #999;">
                    You can close this window.
                </p>
            </div>
        </body>
        </html>
        """)

    except ValueError as e:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Connection Failed</title>
        <style>
            body {{ font-family: Inter, system-ui, sans-serif; display: flex;
                   align-items: center; justify-content: center; min-height: 100vh;
                   margin: 0; background: #fafafa; }}
            .card {{ background: white; border-radius: 12px; padding: 40px;
                    text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            h1 {{ font-size: 24px; margin: 0 0 8px; color: #dc2626; }}
            p {{ color: #666; font-size: 14px; margin: 0; }}
        </style>
        </head>
        <body>
            <div class="card">
                <div style="font-size: 48px; margin-bottom: 16px;">❌</div>
                <h1>Connection Failed</h1>
                <p>{str(e)}</p>
            </div>
        </body>
        </html>
        """, status_code=400)


@router.get("")
async def list_connections(
    user_id: Optional[str] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """List connected apps from our DB, optionally filtered by user_id."""
    records = await list_records("connection", account_id=ctx.account_id)

    connections = []
    for r in records:
        data = r.custom_data or {}
        if user_id and data.get("user_id") != user_id:
            continue
        connections.append({
            "provider": data.get("provider", ""),
            "user_id": data.get("user_id", ""),
            "status": data.get("status", "unknown"),
            "connected_at": data.get("connected_at", ""),
            "scopes": data.get("scopes", []),
        })

    return {"connections": connections, "total": len(connections)}


@router.get("/check")
async def check_connection(
    provider: str,
    user_id: str,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Check if a specific user has connected a provider."""
    app = PROVIDER_MAP.get(provider.lower(), provider)
    api = await get_api_for_workspace(ctx.workspace_id, ctx.account_id)
    connected = await api.is_connected(app, user_id)
    return {"connected": connected, "provider": provider, "user_id": user_id}


@router.get("/health")
async def check_connection_health(
    provider: str,
    user_id: str,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Check if a connection's tokens are still valid.

    Makes a lightweight API call to verify the token works.
    Returns health status + token expiry info.
    """
    app = PROVIDER_MAP.get(provider.lower(), provider)
    api = await get_api_for_workspace(ctx.workspace_id, ctx.account_id)

    # Check if tokens exist
    connected = await api.is_connected(app, user_id)
    if not connected:
        return {
            "healthy": False,
            "provider": provider,
            "user_id": user_id,
            "reason": "not_connected",
        }

    # Try a lightweight API call to validate the token
    health_actions = {
        "google": ("gmail_search", {"q": "newer_than:1d", "maxResults": 1}),
        "slack": ("slack_list_channels", {"limit": 1}),
        "github": ("github_list_repos", {"per_page": 1}),
        "hubspot": ("hubspot_list_contacts", {"limit": 1}),
    }

    if app in health_actions:
        action, params = health_actions[app]
        try:
            result = await api.call(action, connection_id=user_id, **params)
            healthy = result.get("successful", False)
            return {
                "healthy": healthy,
                "provider": provider,
                "user_id": user_id,
                "status_code": result.get("status_code", 0),
                "reason": "" if healthy else result.get("error", "unknown"),
            }
        except Exception as e:
            return {
                "healthy": False,
                "provider": provider,
                "user_id": user_id,
                "reason": str(e),
            }

    return {
        "healthy": True,
        "provider": provider,
        "user_id": user_id,
        "reason": "token_exists_no_health_check",
    }


@router.delete("")
async def disconnect_app(body: DisconnectRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Disconnect an app for a user. Removes tokens + connection record."""
    provider = PROVIDER_MAP.get(body.provider.lower(), body.provider)
    api = await get_api_for_workspace(ctx.workspace_id, ctx.account_id)
    try:
        await api.disconnect(provider, body.user_id)

        connection_key = f"{body.user_id}:{provider}"
        await delete_record("connection", connection_key)

        return {"disconnected": True, "provider": body.provider, "user_id": body.user_id}
    except Exception as e:
        raise HTTPException(500, f"Disconnect failed: {e}")
