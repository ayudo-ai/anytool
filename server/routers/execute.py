"""
API execution — call any action for a user_id.

POST /v1/execute  → execute an action using a user's connection
GET  /v1/actions  → list available actions
GET  /v1/tools    → get tool definitions (OpenAI-compatible)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_auth_context, AuthContext
import time

from server.database import get_record, update_record_fields, atomic_increment, put_record, new_id
from server.engine import get_api

router = APIRouter(tags=["execute"])


class ExecuteRequest(BaseModel):
    action: str              # gmail_send_email, slack_send_message, etc.
    user_id: str             # end-user whose connection to use
    params: Dict[str, Any] = {}


@router.post("/execute")
async def execute_action(body: ExecuteRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Execute an API action using a user's connected account.

    The user_id must have already connected the relevant provider
    via POST /v1/connections.

    Example:
        POST /v1/execute
        {
            "action": "gmail_send_email",
            "user_id": "customer-123",
            "params": {
                "to": "vendor@example.com",
                "subject": "Invoice follow-up",
                "body": "Hi, please send the updated invoice."
            }
        }
    """
    # Check workspace usage limit (atomic increment avoids race conditions)
    max_calls = ctx.limits.get("max_calls", 1000)

    if max_calls > 0:
        workspace_record = await get_record("workspace", ctx.workspace_id)
        workspace_data = workspace_record.custom_data if workspace_record else {}
        calls_used = workspace_data.get("calls_this_month", 0)
        if calls_used >= max_calls:
            raise HTTPException(
                429,
                f"Monthly call limit reached ({max_calls}). Upgrade at anytool.dev"
            )

    api = get_api()

    start_time = time.monotonic()
    result = None
    error_msg = None

    try:
        result = await api.call(
            body.action,
            connection_id=body.user_id,
            **body.params,
        )
    except ValueError as e:
        error_msg = str(e)
        raise HTTPException(400, error_msg)
    except Exception as e:
        error_msg = f"Execution failed: {e}"
        raise HTTPException(500, error_msg)
    finally:
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Atomically increment usage counter (no read-modify-write race)
        await atomic_increment("workspace", ctx.workspace_id, "calls_this_month")

        # Write usage log (fire-and-forget, don't block response)
        try:
            # Determine provider from action name
            action_app = body.action.split("_")[0] if "_" in body.action else ""
            provider = APP_MAP.get(action_app, action_app)

            await put_record(
                object_slug="usage_log",
                primary_key=new_id(),
                account_id=ctx.account_id,
                workspace_id=ctx.workspace_id,
                data={
                    "workspace_id": ctx.workspace_id,
                    "user_id": body.user_id,
                    "action": body.action,
                    "provider": provider,
                    "status_code": result.get("status_code", 0) if result else 0,
                    "successful": result.get("successful", False) if result else False,
                    "duration_ms": duration_ms,
                    "error": error_msg or (result.get("error") if result else None),
                },
            )
        except Exception:
            pass  # Never fail the request over logging

    return {
        "successful": result.get("successful", False),
        "data": result.get("data"),
        "error": result.get("error"),
        "extracted_ids": result.get("extracted_ids", {}),
        "status_code": result.get("status_code", 0),
    }


# ── App mapping ──────────────────────────────────────────────────────

APP_MAP = {
    "gmail": "google", "google_drive": "google", "google_sheets": "google",
    "google_calendar": "google", "google_docs": "google", "google": "google",
    "slack": "slack", "docusign": "docusign", "freshdesk": "freshdesk",
    "hubspot": "hubspot", "github": "github", "zendesk": "zendesk",
    "whatsapp": "whatsapp",
}


@router.get("/actions")
async def list_actions(
    app: Optional[str] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """List all available actions, optionally filtered by app.

    Example:
        GET /v1/actions?app=gmail
    """
    from anytool import AnyTool

    anytool_app = APP_MAP.get(app.lower(), app.lower()) if app else None
    actions = AnyTool.list_actions(anytool_app)
    return {"actions": actions, "total": len(actions)}


# Map anytool param types → JSON Schema types
_JSON_SCHEMA_TYPES = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "list": "array",
    "object": "object",
}


@router.get("/tools")
async def get_tool_definitions(
    app: str,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Get OpenAI-compatible tool definitions for an app.

    Use these with any LLM that supports function calling.
    Returns full parameter schemas with types, descriptions, and enums.

    Example:
        GET /v1/tools?app=gmail
    """
    from anytool import AnyTool as AnyToolClass

    anytool_app = APP_MAP.get(app.lower(), app.lower())
    actions = AnyToolClass.list_actions(anytool_app)

    tools = []
    for action in actions:
        params = action.get("params", [])
        properties = {}
        required = []

        for p in params:
            # Skip path params — they're filled from other params, not by the LLM
            prop: Dict[str, Any] = {
                "type": _JSON_SCHEMA_TYPES.get(p["type"], "string"),
                "description": p.get("description", ""),
            }
            if p.get("enum"):
                prop["enum"] = p["enum"]
            if p.get("default") is not None:
                prop["default"] = p["default"]
            if prop["type"] == "array":
                prop["items"] = {"type": "string"}  # sensible default

            properties[p["name"]] = prop
            if p.get("required"):
                required.append(p["name"])

        tools.append({
            "type": "function",
            "function": {
                "name": action["name"],
                "description": action["description"],
                "parameters": {
                    "type": "object",
                    "required": required,
                    "properties": properties,
                },
            },
        })

    return {"tools": tools, "total": len(tools), "app": app}
