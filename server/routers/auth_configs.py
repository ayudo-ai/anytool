"""
Auth Config management — per-workspace OAuth app credentials.

Each workspace can have multiple auth configs (one per provider).
Supports managed (platform-provided) and custom (developer-provided) credentials.

POST   /v1/auth-configs           → create auth config
GET    /v1/auth-configs           → list auth configs for workspace
GET    /v1/auth-configs/{id}      → get single auth config
PUT    /v1/auth-configs/{id}      → update auth config
DELETE /v1/auth-configs/{id}      → delete auth config
GET    /v1/auth-configs/providers → list supported providers
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_auth_context, AuthContext
from server.database import (
    put_record, get_record, list_records, delete_record,
    update_record_fields, new_id, now,
)
from server.token_store import _encrypt, _decrypt

router = APIRouter(prefix="/auth-configs", tags=["auth-configs"])


# ── Supported providers ──────────────────────────────────────────────

PROVIDERS = {
    "google": {
        "name": "Google",
        "auth_scheme": "oauth2",
        "icon": "gmail",
        "apps": ["gmail", "google_sheets", "google_drive", "google_calendar", "google_docs"],
        "default_scopes": [
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/documents",
            "https://mail.google.com/",
        ],
    },
    "slack": {
        "name": "Slack",
        "auth_scheme": "oauth2",
        "icon": "slack",
        "apps": ["slack"],
        "default_scopes": [
            "channels:read", "channels:history", "chat:write",
            "users:read", "users:read.email", "reactions:write",
        ],
    },
    "hubspot": {
        "name": "HubSpot",
        "auth_scheme": "oauth2",
        "icon": "hubspot",
        "apps": ["hubspot"],
        "default_scopes": [
            "crm.objects.contacts.read", "crm.objects.contacts.write",
            "crm.objects.companies.read", "crm.objects.companies.write",
            "crm.objects.deals.read", "crm.objects.deals.write",
            "crm.objects.owners.read",
        ],
    },
    "github": {
        "name": "GitHub",
        "auth_scheme": "oauth2",
        "icon": "github",
        "apps": ["github"],
        "default_scopes": ["repo", "read:org", "workflow"],
    },
    "docusign": {
        "name": "DocuSign",
        "auth_scheme": "oauth2",
        "icon": "docusign",
        "apps": ["docusign"],
        "default_scopes": ["signature", "impersonation"],
    },
    "zendesk": {
        "name": "Zendesk",
        "auth_scheme": "oauth2",
        "icon": "zendesk",
        "apps": ["zendesk"],
        "default_scopes": ["read", "write"],
    },
    "freshdesk": {
        "name": "Freshdesk",
        "auth_scheme": "api_key",
        "icon": "freshdesk",
        "apps": ["freshdesk"],
        "default_scopes": [],
    },
    "whatsapp": {
        "name": "WhatsApp Business",
        "auth_scheme": "bearer",
        "icon": "whatsapp",
        "apps": ["whatsapp"],
        "default_scopes": [],
    },
}


# ── Models ───────────────────────────────────────────────────────────

class CreateAuthConfigRequest(BaseModel):
    name: str                       # "Google Production", "Slack Bot"
    provider: str                   # google, slack, hubspot, etc.
    auth_scheme: str = "oauth2"     # oauth2, api_key, bearer
    management: str = "custom"      # managed, custom
    client_id: str = ""
    client_secret: str = ""         # Will be encrypted before storage
    scopes: List[str] = []
    redirect_uri: str = ""
    api_key: str = ""               # For api_key auth
    domain: str = ""                # For Freshdesk/Zendesk
    extra_config: Dict[str, Any] = {}


class UpdateAuthConfigRequest(BaseModel):
    name: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scopes: Optional[List[str]] = None
    redirect_uri: Optional[str] = None
    api_key: Optional[str] = None
    domain: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class AuthConfigResponse(BaseModel):
    id: str
    name: str
    provider: str
    auth_scheme: str
    management: str
    client_id: str
    scopes: List[str]
    redirect_uri: str
    domain: str
    connections_count: int
    enabled: bool
    created_at: str
    # NOTE: client_secret and api_key are NEVER returned


# ── Routes ───────────────────────────────────────────────────────────

@router.get("/providers")
async def list_providers(ctx: AuthContext = Depends(get_auth_context)):
    """List all supported providers with their default config."""
    return {
        "providers": [
            {
                "slug": slug,
                "name": info["name"],
                "auth_scheme": info["auth_scheme"],
                "apps": info["apps"],
                "default_scopes": info["default_scopes"],
            }
            for slug, info in PROVIDERS.items()
        ]
    }


@router.post("")
async def create_auth_config(
    body: CreateAuthConfigRequest,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Create an auth config for a provider in this workspace.

    Client secrets are encrypted before storage.
    Each workspace can have one auth config per provider.

    Example:
        POST /v1/auth-configs
        {
            "name": "Google Production",
            "provider": "google",
            "client_id": "xxx.apps.googleusercontent.com",
            "client_secret": "GOCSPX-xxx",
            "scopes": ["https://www.googleapis.com/auth/gmail.send"]
        }
    """
    if body.provider not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider: {body.provider}. Available: {list(PROVIDERS.keys())}")

    # Check for duplicate provider in workspace
    existing = await list_records("auth_config", account_id=ctx.account_id, workspace_id=ctx.workspace_id)
    for r in existing:
        d = r.custom_data or {}
        if d.get("provider") == body.provider and d.get("enabled", True):
            raise HTTPException(400, f"Auth config for {body.provider} already exists in this workspace. Update it instead.")

    config_id = new_id()
    provider_info = PROVIDERS[body.provider]

    # Use default scopes if none provided
    scopes = body.scopes or provider_info["default_scopes"]

    # Default redirect URI
    from server.config import config
    redirect_uri = body.redirect_uri or f"{config.base_url}{config.api_prefix}/connections/callback"

    # Encrypt secrets
    client_secret_enc = _encrypt(body.client_secret) if body.client_secret else ""
    api_key_enc = _encrypt(body.api_key) if body.api_key else ""

    await put_record(
        object_slug="auth_config",
        primary_key=config_id,
        account_id=ctx.account_id,
        workspace_id=ctx.workspace_id,
        data={
            "name": body.name,
            "provider": body.provider,
            "auth_scheme": body.auth_scheme or provider_info["auth_scheme"],
            "management": body.management,
            "client_id": body.client_id,
            "client_secret_encrypted": client_secret_enc,
            "scopes": scopes,
            "redirect_uri": redirect_uri,
            "api_key_encrypted": api_key_enc,
            "domain": body.domain,
            "extra_config": body.extra_config,
            "connections_count": 0,
            "enabled": True,
        },
    )

    return {
        "id": config_id,
        "name": body.name,
        "provider": body.provider,
        "auth_scheme": body.auth_scheme or provider_info["auth_scheme"],
        "management": body.management,
        "status": "enabled",
    }


@router.get("")
async def list_auth_configs(ctx: AuthContext = Depends(get_auth_context)):
    """List all auth configs for this workspace."""
    records = await list_records("auth_config", account_id=ctx.account_id, workspace_id=ctx.workspace_id)

    configs = []
    for r in records:
        d = r.custom_data or {}
        configs.append({
            "id": r.primary_field_value,
            "name": d.get("name", ""),
            "provider": d.get("provider", ""),
            "auth_scheme": d.get("auth_scheme", "oauth2"),
            "management": d.get("management", "custom"),
            "client_id": d.get("client_id", ""),
            "scopes": d.get("scopes", []),
            "redirect_uri": d.get("redirect_uri", ""),
            "domain": d.get("domain", ""),
            "connections_count": d.get("connections_count", 0),
            "enabled": d.get("enabled", True),
            "created_at": str(r.created_at) if r.created_at else "",
        })

    return {"auth_configs": configs, "total": len(configs)}


@router.get("/{config_id}")
async def get_auth_config(config_id: str, ctx: AuthContext = Depends(get_auth_context)):
    """Get a single auth config. Secrets are never returned."""
    record = await get_record("auth_config", config_id)
    if not record or record.account_id != ctx.account_id:
        raise HTTPException(404, "Auth config not found")

    d = record.custom_data or {}
    return {
        "id": record.primary_field_value,
        "name": d.get("name", ""),
        "provider": d.get("provider", ""),
        "auth_scheme": d.get("auth_scheme", "oauth2"),
        "management": d.get("management", "custom"),
        "client_id": d.get("client_id", ""),
        "has_client_secret": bool(d.get("client_secret_encrypted")),
        "scopes": d.get("scopes", []),
        "redirect_uri": d.get("redirect_uri", ""),
        "domain": d.get("domain", ""),
        "connections_count": d.get("connections_count", 0),
        "enabled": d.get("enabled", True),
        "created_at": str(record.created_at) if record.created_at else "",
    }


@router.put("/{config_id}")
async def update_auth_config(
    config_id: str,
    body: UpdateAuthConfigRequest,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Update an auth config. Only provided fields are updated."""
    record = await get_record("auth_config", config_id)
    if not record or record.account_id != ctx.account_id:
        raise HTTPException(404, "Auth config not found")

    updates: Dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.client_id is not None:
        updates["client_id"] = body.client_id
    if body.client_secret is not None:
        updates["client_secret_encrypted"] = _encrypt(body.client_secret)
    if body.scopes is not None:
        updates["scopes"] = body.scopes
    if body.redirect_uri is not None:
        updates["redirect_uri"] = body.redirect_uri
    if body.api_key is not None:
        updates["api_key_encrypted"] = _encrypt(body.api_key)
    if body.domain is not None:
        updates["domain"] = body.domain
    if body.extra_config is not None:
        updates["extra_config"] = body.extra_config
    if body.enabled is not None:
        updates["enabled"] = body.enabled

    if not updates:
        raise HTTPException(400, "No fields to update")

    await update_record_fields("auth_config", config_id, updates)
    return {"updated": True, "config_id": config_id}


@router.delete("/{config_id}")
async def delete_auth_config(config_id: str, ctx: AuthContext = Depends(get_auth_context)):
    """Delete an auth config."""
    record = await get_record("auth_config", config_id)
    if not record or record.account_id != ctx.account_id:
        raise HTTPException(404, "Auth config not found")

    await delete_record("auth_config", config_id)
    return {"deleted": True, "config_id": config_id}
