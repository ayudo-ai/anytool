"""
Account + Workspace management.

Hierarchy:
  Account (company/developer)
    └── Workspace (isolated environment — project, team, customer)
          └── API Key (scoped to workspace)

POST /v1/accounts              → create account + default workspace + API key
POST /v1/workspaces            → create workspace under your account
GET  /v1/workspaces            → list workspaces
GET  /v1/accounts/me           → account info + usage
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_auth_context, AuthContext
from server.database import (
    put_record, get_record, get_record_by_field, list_records,
    generate_api_key, new_id,
)

router = APIRouter(tags=["accounts"])


# ── Request/Response models ──────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str            # Company or developer name
    email: str


class SignupResponse(BaseModel):
    api_key: str
    account_id: str
    workspace_id: str
    workspace_name: str
    plan: str
    message: str


class CreateWorkspaceRequest(BaseModel):
    name: str            # "Production", "Staging", "Customer-X"


class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    api_key: str


# ── Routes ───────────────────────────────────────────────────────────

@router.post("/accounts", response_model=SignupResponse)
async def create_account(body: SignupRequest):
    """Create a new account + default workspace + API key.

    No credit card required. Free tier: 10 connections, 1000 calls/month, 5 triggers per workspace.

    Example:
        POST /v1/accounts
        {"name": "Acme Corp", "email": "dev@acme.com"}
        → {"api_key": "at_xxxx...", "account_id": "...", "workspace_id": "...", "plan": "free"}
    """
    # Check if email already exists
    existing = await get_record_by_field("account", "email", body.email)
    if existing:
        raise HTTPException(400, f"Account with email {body.email} already exists")

    account_id = new_id()
    workspace_id = new_id()
    api_key = generate_api_key()

    # 1. Create Account
    await put_record(
        object_slug="account",
        primary_key=account_id,
        account_id=account_id,
        data={
            "name": body.name,
            "email": body.email,
            "plan": "free",
        },
    )

    # 2. Create default Workspace
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

    # 3. Create API Key (scoped to account + workspace)
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

    return SignupResponse(
        api_key=api_key,
        account_id=account_id,
        workspace_id=workspace_id,
        workspace_name="Default",
        plan="free",
        message=(
            "Account created! Use this API key in all requests: "
            "Authorization: Bearer at_xxxx..."
        ),
    )


@router.post("/workspaces", response_model=WorkspaceResponse)
async def create_workspace(body: CreateWorkspaceRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Create a new workspace under your account.

    Each workspace is isolated — its own connections, triggers, and usage.
    A new API key is generated for the workspace.

    Example:
        POST /v1/workspaces
        {"name": "Production"}
        → {"workspace_id": "...", "name": "Production", "api_key": "at_xxxx..."}
    """
    workspace_id = new_id()
    api_key = generate_api_key()

    # Create Workspace
    await put_record(
        object_slug="workspace",
        primary_key=workspace_id,
        account_id=ctx.account_id,
        workspace_id=workspace_id,
        data={
            "name": body.name,
            "calls_this_month": 0,
        },
    )

    # Create API Key for this workspace
    await put_record(
        object_slug="api_key",
        primary_key=api_key,
        account_id=ctx.account_id,
        workspace_id=workspace_id,
        data={
            "label": f"{body.name} key",
            "is_active": True,
        },
    )

    return WorkspaceResponse(
        workspace_id=workspace_id,
        name=body.name,
        api_key=api_key,
    )


@router.get("/workspaces")
async def list_workspaces(ctx: AuthContext = Depends(get_auth_context)):
    """List all workspaces under your account."""
    records = await list_records("workspace", account_id=ctx.account_id)
    workspaces = []
    for r in records:
        data = r.custom_data or {}
        workspaces.append({
            "workspace_id": r.primary_field_value,
            "name": data.get("name", ""),
            "calls_this_month": data.get("calls_this_month", 0),
            "created_at": str(r.created_at) if r.created_at else "",
        })
    return {"workspaces": workspaces, "total": len(workspaces)}


@router.get("/accounts/me")
async def get_me(ctx: AuthContext = Depends(get_auth_context)):
    """Get your account info, current workspace, and usage."""
    # Get account data
    account_record = await get_record("account", ctx.account_id)
    account_data = account_record.custom_data if account_record else {}

    # Get workspace data
    workspace_record = await get_record("workspace", ctx.workspace_id)
    workspace_data = workspace_record.custom_data if workspace_record else {}

    # Plan limits
    plan_limits = {
        "free": {"max_calls": 1000, "max_connections": 10, "max_triggers": 5},
        "pro": {"max_calls": 100_000, "max_connections": 100, "max_triggers": 50},
        "enterprise": {"max_calls": -1, "max_connections": -1, "max_triggers": -1},
    }
    plan = account_data.get("plan", "free")
    limits = plan_limits.get(plan, plan_limits["free"])

    return {
        "account": {
            "id": ctx.account_id,
            "name": account_data.get("name", ""),
            "email": account_data.get("email", ""),
            "plan": plan,
        },
        "workspace": {
            "id": ctx.workspace_id,
            "name": workspace_data.get("name", ""),
        },
        "usage": {
            "calls_this_month": workspace_data.get("calls_this_month", 0),
            "max_calls": limits["max_calls"],
        },
        "limits": limits,
    }
