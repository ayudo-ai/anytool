"""
Stripe billing — checkout, portal, webhooks.

POST   /v1/billing/checkout       → create Stripe checkout session
POST   /v1/billing/portal         → create Stripe billing portal session
POST   /v1/billing/webhook        → Stripe webhook handler
GET    /v1/billing/status         → current plan status + usage

Env vars:
  STRIPE_SECRET_KEY       → Stripe API key
  STRIPE_WEBHOOK_SECRET   → Webhook signing secret
  STRIPE_PRICE_PRO        → Price ID for Pro plan (e.g. price_xxx)
  STRIPE_PRICE_ENTERPRISE → Price ID for Enterprise plan
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from server.auth import get_auth_context, AuthContext
from server.database import get_record, update_record_fields

router = APIRouter(prefix="/billing", tags=["billing"])

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO = os.environ.get("STRIPE_PRICE_PRO", "")
STRIPE_PRICE_ENTERPRISE = os.environ.get("STRIPE_PRICE_ENTERPRISE", "")
ANYTOOL_BASE_URL = os.environ.get("ANYTOOL_BASE_URL", "http://localhost:5174")

PLAN_PRICES = {
    "pro": STRIPE_PRICE_PRO,
    "enterprise": STRIPE_PRICE_ENTERPRISE,
}


def _get_stripe():
    """Lazy import stripe to avoid import error when not installed."""
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        raise HTTPException(500, "Stripe not installed. Run: pip install stripe")


class CheckoutRequest(BaseModel):
    plan: str  # "pro" or "enterprise"
    success_url: str = ""
    cancel_url: str = ""


@router.post("/checkout")
async def create_checkout(body: CheckoutRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Create a Stripe Checkout session for plan upgrade.

    Returns a URL to redirect the user to Stripe's hosted checkout page.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "Stripe not configured. Set STRIPE_SECRET_KEY.")

    price_id = PLAN_PRICES.get(body.plan)
    if not price_id:
        raise HTTPException(400, f"Unknown plan: {body.plan}. Available: {list(PLAN_PRICES.keys())}")

    stripe = _get_stripe()

    # Get or create Stripe customer
    account = await get_record("account", ctx.account_id)
    account_data = account.custom_data if account else {}
    stripe_customer_id = account_data.get("stripe_customer_id")

    if not stripe_customer_id:
        customer = stripe.Customer.create(
            email=account_data.get("email", ""),
            name=account_data.get("name", ""),
            metadata={"anytool_account_id": ctx.account_id},
        )
        stripe_customer_id = customer.id
        await update_record_fields("account", ctx.account_id, {
            "stripe_customer_id": stripe_customer_id,
        })

    success_url = body.success_url or f"{ANYTOOL_BASE_URL}/dashboard/settings?checkout=success"
    cancel_url = body.cancel_url or f"{ANYTOOL_BASE_URL}/dashboard/settings?checkout=cancel"

    session = stripe.checkout.Session.create(
        customer=stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"anytool_account_id": ctx.account_id},
    )

    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/portal")
async def create_portal(ctx: AuthContext = Depends(get_auth_context)):
    """Create a Stripe Billing Portal session.

    Lets users manage their subscription, update payment method, cancel, etc.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "Stripe not configured")

    stripe = _get_stripe()

    account = await get_record("account", ctx.account_id)
    account_data = account.custom_data if account else {}
    stripe_customer_id = account_data.get("stripe_customer_id")

    if not stripe_customer_id:
        raise HTTPException(400, "No billing account. Subscribe to a plan first.")

    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=f"{ANYTOOL_BASE_URL}/dashboard/settings",
    )

    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events.

    Processes:
      - checkout.session.completed → upgrade plan
      - customer.subscription.updated → sync plan changes
      - customer.subscription.deleted → downgrade to free
    """
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(500, "Stripe webhooks not configured")

    stripe = _get_stripe()

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(400, f"Invalid webhook: {e}")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        account_id = data.get("metadata", {}).get("anytool_account_id")
        if account_id:
            # Look up the subscription to determine the plan
            sub_id = data.get("subscription")
            if sub_id:
                sub = stripe.Subscription.retrieve(sub_id)
                price_id = sub["items"]["data"][0]["price"]["id"] if sub["items"]["data"] else ""
                plan = "free"
                for plan_name, pid in PLAN_PRICES.items():
                    if pid == price_id:
                        plan = plan_name
                        break
                await update_record_fields("account", account_id, {
                    "plan": plan,
                    "stripe_subscription_id": sub_id,
                })

    elif event_type == "customer.subscription.updated":
        sub_id = data.get("id")
        customer_id = data.get("customer")
        # Find account by stripe_customer_id
        # For now, use metadata
        price_id = data["items"]["data"][0]["price"]["id"] if data.get("items", {}).get("data") else ""
        plan = "free"
        for plan_name, pid in PLAN_PRICES.items():
            if pid == price_id:
                plan = plan_name
                break
        # Update via customer metadata
        if data.get("metadata", {}).get("anytool_account_id"):
            await update_record_fields("account", data["metadata"]["anytool_account_id"], {
                "plan": plan,
            })

    elif event_type == "customer.subscription.deleted":
        if data.get("metadata", {}).get("anytool_account_id"):
            await update_record_fields("account", data["metadata"]["anytool_account_id"], {
                "plan": "free",
                "stripe_subscription_id": "",
            })

    return {"received": True}


@router.get("/status")
async def billing_status(ctx: AuthContext = Depends(get_auth_context)):
    """Get current billing status — plan, usage, limits."""
    account = await get_record("account", ctx.account_id)
    account_data = account.custom_data if account else {}

    workspace = await get_record("workspace", ctx.workspace_id)
    ws_data = workspace.custom_data if workspace else {}

    from server.auth import PLAN_LIMITS
    limits = PLAN_LIMITS.get(ctx.plan, PLAN_LIMITS["free"])

    return {
        "plan": ctx.plan,
        "stripe_customer_id": account_data.get("stripe_customer_id", ""),
        "has_subscription": bool(account_data.get("stripe_subscription_id")),
        "usage": {
            "calls_this_month": ws_data.get("calls_this_month", 0),
            "max_calls": limits["max_calls"],
        },
        "limits": limits,
        "upgradeable": ctx.plan != "enterprise",
    }
