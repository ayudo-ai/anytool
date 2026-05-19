"""
Developer authentication — Google SSO + Email/Password.

POST /v1/auth/google         → exchange Google ID token for session
GET  /v1/auth/google/config  → return Client ID for frontend
POST /v1/auth/signup         → email + password signup
POST /v1/auth/login          → email + password login
GET  /v1/auth/me             → get current user (from session token)
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import httpx

from server.config import config
from server.database import (
    get_record, get_record_by_field, put_record, list_records,
    update_record_fields, generate_api_key, new_id, now,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Models ───────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str  # min 8 chars enforced in frontend


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class AuthResponse(BaseModel):
    session_token: str  # Short-lived token for dashboard access
    api_key: str        # Long-lived key for API access
    account_id: str
    workspace_id: str
    name: str
    email: str
    picture: str
    is_new: bool


# ── Helpers ──────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _generate_session_token() -> str:
    """Generate a short-lived session token for dashboard access."""
    return f"sess_{secrets.token_urlsafe(32)}"


async def _create_account(
    name: str,
    email: str,
    picture: str = "",
    auth_provider: str = "email",
    password_hash: str = "",
) -> AuthResponse:
    """Create a new account + workspace + API key + session."""
    account_id = new_id()
    workspace_id = new_id()
    api_key = generate_api_key()
    session_token = _generate_session_token()

    # Account
    await put_record(
        object_slug="account",
        primary_key=account_id,
        account_id=account_id,
        data={
            "name": name,
            "email": email,
            "picture": picture,
            "plan": "free",
            "auth_provider": auth_provider,
            "password_hash": password_hash,
        },
    )

    # Workspace
    await put_record(
        object_slug="workspace",
        primary_key=workspace_id,
        account_id=account_id,
        workspace_id=workspace_id,
        data={"name": "Default", "calls_this_month": 0},
    )

    # API Key
    await put_record(
        object_slug="api_key",
        primary_key=api_key,
        account_id=account_id,
        workspace_id=workspace_id,
        data={"label": "Default key", "is_active": True},
    )

    # Session
    await put_record(
        object_slug="session",
        primary_key=session_token,
        account_id=account_id,
        workspace_id=workspace_id,
        data={
            "expires_at": (now() + timedelta(days=7)).isoformat(),
        },
    )

    return AuthResponse(
        session_token=session_token,
        api_key=api_key,
        account_id=account_id,
        workspace_id=workspace_id,
        name=name,
        email=email,
        picture=picture,
        is_new=True,
    )


async def _login_existing(
    account_id: str,
    account_data: dict,
) -> AuthResponse:
    """Create session for existing account, return first active API key."""
    # Find API key
    keys = await list_records("api_key", account_id=account_id)
    active_key = next(
        (k for k in keys if (k.custom_data or {}).get("is_active", True)),
        None,
    )

    if not active_key:
        api_key = generate_api_key()
        workspaces = await list_records("workspace", account_id=account_id)
        workspace_id = workspaces[0].primary_field_value if workspaces else new_id()
        await put_record(
            object_slug="api_key",
            primary_key=api_key,
            account_id=account_id,
            workspace_id=workspace_id,
            data={"label": "Auto-generated key", "is_active": True},
        )
    else:
        api_key = active_key.primary_field_value
        workspace_id = active_key.workspace_id or ""

    # Create session
    session_token = _generate_session_token()
    await put_record(
        object_slug="session",
        primary_key=session_token,
        account_id=account_id,
        workspace_id=workspace_id,
        data={
            "expires_at": (now() + timedelta(days=7)).isoformat(),
        },
    )

    return AuthResponse(
        session_token=session_token,
        api_key=api_key,
        account_id=account_id,
        workspace_id=workspace_id,
        name=account_data.get("name", ""),
        email=account_data.get("email", ""),
        picture=account_data.get("picture", ""),
        is_new=False,
    )


# ── Google JWT Verification ──────────────────────────────────────────

async def _verify_google_token(id_token: str) -> dict:
    """Verify a Google ID token using Google's tokeninfo endpoint."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
        )

    if not resp.is_success:
        raise HTTPException(401, "Invalid Google ID token")

    payload = resp.json()

    if payload.get("aud") != config.google_client_id:
        raise HTTPException(401, "Token not issued for this application")

    if payload.get("email_verified") != "true":
        raise HTTPException(401, "Email not verified by Google")

    return payload


# ── Routes ───────────────────────────────────────────────────────────

@router.get("/google/config")
async def google_config():
    """Return Google Client ID for the frontend sign-in button."""
    if not config.google_client_id:
        raise HTTPException(500, "Google SSO not configured. Set GOOGLE_OAUTH_CLIENT_ID.")
    return {"client_id": config.google_client_id}


@router.post("/google", response_model=AuthResponse)
async def google_login(body: GoogleLoginRequest):
    """Sign in / sign up with Google."""
    if not config.google_client_id:
        raise HTTPException(500, "Google SSO not configured")

    payload = await _verify_google_token(body.id_token)
    email = payload.get("email", "")
    name = payload.get("name", "")
    picture = payload.get("picture", "")

    if not email:
        raise HTTPException(400, "No email in Google token")

    existing = await get_record_by_field("account", "email", email)

    if existing:
        account_data = existing.custom_data or {}
        # Update picture/name if changed
        updates = {}
        if name and account_data.get("name") != name:
            updates["name"] = name
        if picture and account_data.get("picture") != picture:
            updates["picture"] = picture
        if updates:
            await update_record_fields("account", existing.primary_field_value, updates)
            account_data.update(updates)

        return await _login_existing(existing.primary_field_value, account_data)

    return await _create_account(name=name, email=email, picture=picture, auth_provider="google")


@router.post("/signup", response_model=AuthResponse)
async def email_signup(body: SignupRequest):
    """Create account with email + password."""
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    existing = await get_record_by_field("account", "email", body.email)
    if existing:
        raise HTTPException(400, "Account with this email already exists. Try signing in.")

    password_hash = _hash_password(body.password)

    return await _create_account(
        name=body.name,
        email=body.email,
        auth_provider="email",
        password_hash=password_hash,
    )


@router.post("/login", response_model=AuthResponse)
async def email_login(body: LoginRequest):
    """Sign in with email + password."""
    account = await get_record_by_field("account", "email", body.email)
    if not account:
        raise HTTPException(401, "Invalid email or password")

    account_data = account.custom_data or {}
    password_hash = account_data.get("password_hash", "")

    if not password_hash:
        # Account was created via Google SSO — no password set
        provider = account_data.get("auth_provider", "google")
        raise HTTPException(
            401,
            f"This account uses {provider} sign-in. Use the Google button instead."
        )

    if not _verify_password(body.password, password_hash):
        raise HTTPException(401, "Invalid email or password")

    return await _login_existing(account.primary_field_value, account_data)


@router.get("/me")
async def get_current_user(authorization: str = Header(...)):
    """Get the current user from session token.

    Used by dashboard to verify session is still valid.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header")

    token = authorization[7:].strip()

    # Check if it's a session token
    if token.startswith("sess_"):
        session = await get_record("session", token)
        if not session:
            raise HTTPException(401, "Invalid or expired session")

        session_data = session.custom_data or {}
        expires_at = session_data.get("expires_at", "")
        if expires_at:
            exp = datetime.fromisoformat(expires_at)
            if datetime.now(timezone.utc) > exp:
                raise HTTPException(401, "Session expired. Please sign in again.")

        account_id = session.account_id
        account = await get_record("account", account_id)
        if not account:
            raise HTTPException(401, "Account not found")

        account_data = account.custom_data or {}
        return {
            "account_id": account_id,
            "name": account_data.get("name", ""),
            "email": account_data.get("email", ""),
            "picture": account_data.get("picture", ""),
            "plan": account_data.get("plan", "free"),
        }

    # Also support API key for backward compat
    if token.startswith("at_"):
        key_record = await get_record("api_key", token)
        if not key_record:
            raise HTTPException(401, "Invalid API key")
        account = await get_record("account", key_record.account_id or "")
        if not account:
            raise HTTPException(401, "Account not found")
        account_data = account.custom_data or {}
        return {
            "account_id": key_record.account_id,
            "name": account_data.get("name", ""),
            "email": account_data.get("email", ""),
            "picture": account_data.get("picture", ""),
            "plan": account_data.get("plan", "free"),
        }

    raise HTTPException(401, "Invalid token format")
