"""
Google SSO — developer login via Google Identity Services.

Flow:
  1. Frontend uses Google's "Sign in with Google" button
  2. Google returns a JWT ID token (contains email, name, picture)
  3. Frontend POSTs the token here
  4. We verify it with Google's public keys
  5. Create or find the developer account
  6. Return API key

POST /v1/auth/google         → exchange Google ID token for API key
GET  /v1/auth/google/config  → return Client ID for frontend
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

from server.config import config
from server.database import (
    get_record_by_field, put_record, generate_api_key, new_id,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleLoginRequest(BaseModel):
    id_token: str  # JWT from Google Identity Services


class GoogleLoginResponse(BaseModel):
    api_key: str
    account_id: str
    workspace_id: str
    name: str
    email: str
    picture: str
    is_new: bool  # True if account was just created


# ── Google JWT Verification ──────────────────────────────────────────

async def verify_google_token(id_token: str) -> dict:
    """Verify a Google ID token using Google's tokeninfo endpoint.

    Returns the decoded token payload with email, name, picture, etc.
    For production, use google-auth library with cached certs.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Google's tokeninfo endpoint verifies signature + expiry
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
        )

    if not resp.is_success:
        raise HTTPException(401, "Invalid Google ID token")

    payload = resp.json()

    # Verify the token was issued for our app
    if payload.get("aud") != config.google_client_id:
        raise HTTPException(401, "Token not issued for this application")

    # Verify email is verified
    if payload.get("email_verified") != "true":
        raise HTTPException(401, "Email not verified by Google")

    return payload


# ── Routes ───────────────────────────────────────────────────────────

@router.get("/google/config")
async def google_config():
    """Return the Google Client ID for the frontend.

    The frontend needs this to initialize the Google Sign-In button.
    """
    if not config.google_client_id:
        raise HTTPException(500, "Google SSO not configured. Set GOOGLE_OAUTH_CLIENT_ID.")
    return {"client_id": config.google_client_id}


@router.post("/google", response_model=GoogleLoginResponse)
async def google_login(body: GoogleLoginRequest):
    """Exchange a Google ID token for an anytool API key.

    If the email already has an account → return existing API key.
    If new → create account + workspace + API key.
    """
    if not config.google_client_id:
        raise HTTPException(500, "Google SSO not configured")

    # 1. Verify the token with Google
    payload = await verify_google_token(body.id_token)

    email = payload.get("email", "")
    name = payload.get("name", "")
    picture = payload.get("picture", "")

    if not email:
        raise HTTPException(400, "No email in Google token")

    # 2. Check if account already exists
    existing = await get_record_by_field("account", "email", email)

    if existing:
        # Existing account — find their API key
        account_id = existing.primary_field_value

        # Update name/picture if changed
        account_data = existing.custom_data or {}
        if name and account_data.get("name") != name:
            from server.database import update_record_fields
            await update_record_fields("account", account_id, {
                "name": name,
                "picture": picture,
                "auth_provider": "google",
            })

        # Find their first active API key
        from server.database import list_records
        keys = await list_records("api_key", account_id=account_id)
        active_key = next(
            (k for k in keys if (k.custom_data or {}).get("is_active", True)),
            None,
        )

        if not active_key:
            # No active key — create one
            api_key = generate_api_key()
            # Find their workspace
            workspaces = await list_records("workspace", account_id=account_id)
            workspace_id = workspaces[0].primary_field_value if workspaces else new_id()

            await put_record(
                object_slug="api_key",
                primary_key=api_key,
                account_id=account_id,
                workspace_id=workspace_id,
                data={"label": "Google SSO key", "is_active": True},
            )
        else:
            api_key = active_key.primary_field_value
            # Find workspace from key
            workspace_id = active_key.workspace_id or ""

        return GoogleLoginResponse(
            api_key=api_key,
            account_id=account_id,
            workspace_id=workspace_id,
            name=name,
            email=email,
            picture=picture,
            is_new=False,
        )

    # 3. New account — create everything
    account_id = new_id()
    workspace_id = new_id()
    api_key = generate_api_key()

    await put_record(
        object_slug="account",
        primary_key=account_id,
        account_id=account_id,
        data={
            "name": name,
            "email": email,
            "picture": picture,
            "plan": "free",
            "auth_provider": "google",
        },
    )

    await put_record(
        object_slug="workspace",
        primary_key=workspace_id,
        account_id=account_id,
        workspace_id=workspace_id,
        data={
            "name": "Default",
            "calls_this_month": 0,
        },
    )

    await put_record(
        object_slug="api_key",
        primary_key=api_key,
        account_id=account_id,
        workspace_id=workspace_id,
        data={
            "label": "Default key",
            "is_active": True,
        },
    )

    return GoogleLoginResponse(
        api_key=api_key,
        account_id=account_id,
        workspace_id=workspace_id,
        name=name,
        email=email,
        picture=picture,
        is_new=True,
    )
