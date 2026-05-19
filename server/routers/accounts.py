"""
Account management — signup, API key, usage.

POST /v1/accounts       → create account (get API key)
GET  /v1/accounts/me    → get account info + usage
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_account
from server.database import put_record, get_record_by_field, generate_api_key, new_id

router = APIRouter(prefix="/accounts", tags=["accounts"])


class SignupRequest(BaseModel):
    name: str
    email: str


class SignupResponse(BaseModel):
    api_key: str
    name: str
    email: str
    plan: str
    message: str


@router.post("", response_model=SignupResponse)
async def create_account(body: SignupRequest):
    """Create a new developer account and get an API key.

    No credit card required. Free tier: 10 connections, 1000 calls/month, 5 triggers.

    Example:
        POST /v1/accounts
        {"name": "John Doe", "email": "john@example.com"}
        → {"api_key": "at_xxxx...", "plan": "free"}
    """
    # Check if email already exists
    existing = await get_record_by_field("account", "email", body.email)
    if existing:
        raise HTTPException(400, f"Account with email {body.email} already exists")

    api_key = generate_api_key()
    account_id = new_id()

    await put_record(
        object_type="account",
        key=api_key,
        record_id=account_id,
        data={
            "name": body.name,
            "email": body.email,
            "plan": "free",
            "calls_this_month": 0,
        },
    )

    return SignupResponse(
        api_key=api_key,
        name=body.name,
        email=body.email,
        plan="free",
        message="Account created! Use this API key in all requests: Bearer at_xxxx...",
    )


@router.get("/me")
async def get_me(account: dict = Depends(get_account)):
    """Get your account info and usage stats."""
    limits = account.get("limits", {})
    return {
        "name": account.get("name", ""),
        "email": account.get("email", ""),
        "plan": account.get("plan", "free"),
        "usage": {
            "calls_this_month": account.get("calls_this_month", 0),
            "max_calls": limits.get("max_calls", 1000),
        },
        "limits": limits,
    }
