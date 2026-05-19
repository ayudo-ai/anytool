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
from server.database import get_record, update_record_fields
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
    # Check workspace usage limit
    workspace_record = await get_record("workspace", ctx.workspace_id)
    workspace_data = workspace_record.custom_data if workspace_record else {}
    calls_used = workspace_data.get("calls_this_month", 0)
    max_calls = ctx.limits.get("max_calls", 1000)

    if max_calls > 0 and calls_used >= max_calls:
        raise HTTPException(
            429,
            f"Monthly call limit reached ({max_calls}). Upgrade at anytool.dev"
        )

    api = get_api()

    try:
        result = await api.call(
            body.action,
            connection_id=body.user_id,
            **body.params,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Execution failed: {e}")

    # Increment workspace usage
    await update_record_fields("workspace", ctx.workspace_id, {
        "calls_this_month": calls_used + 1,
    })

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


@router.get("/tools")
async def get_tool_definitions(
    app: str,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Get OpenAI-compatible tool definitions for an app.

    Use these with any LLM that supports function calling.

    Example:
        GET /v1/tools?app=gmail
    """
    from anytool import AnyTool as AnyToolClass

    anytool_app = APP_MAP.get(app.lower(), app.lower())
    actions = AnyToolClass.list_actions(anytool_app)

    tools = []
    for action in actions:
        tools.append({
            "type": "function",
            "function": {
                "name": action["name"],
                "description": action["description"],
                "parameters": {
                    "type": "object",
                    "required": action.get("params", []),
                    "properties": {
                        p: {"type": "string", "description": ""}
                        for p in action.get("params", [])
                    },
                },
            },
        })

    return {"tools": tools, "total": len(tools), "app": app}
