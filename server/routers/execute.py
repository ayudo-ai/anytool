"""
API execution — call any action by name.

POST /v1/execute → execute an action
GET  /v1/actions → list available actions
GET  /v1/tools   → get LangChain-compatible tool definitions
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_account
from server.database import update_record_fields
from server.engine import get_api

router = APIRouter(tags=["execute"])


class ExecuteRequest(BaseModel):
    action: str  # gmail_send_email, slack_send_message, etc.
    user_id: str  # end-user whose connection to use
    params: Dict[str, Any] = {}  # action parameters


class ExecuteResponse(BaseModel):
    successful: bool
    data: Any = None
    error: Optional[str] = None
    extracted_ids: Dict[str, str] = {}
    status_code: int = 0


@router.post("/execute", response_model=ExecuteResponse)
async def execute_action(body: ExecuteRequest, account: dict = Depends(get_account)):
    """Execute an API action.

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
    # Check usage limit
    limits = account.get("limits", {})
    max_calls = limits.get("max_calls", 1000)
    calls_used = account.get("calls_this_month", 0)
    if max_calls > 0 and calls_used >= max_calls:
        raise HTTPException(
            429,
            f"Monthly API call limit reached ({max_calls}). Upgrade your plan at anytool.dev"
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

    # Increment usage counter
    await update_record_fields("account", account["api_key"], {
        "calls_this_month": calls_used + 1,
    })

    return ExecuteResponse(
        successful=result.get("successful", False),
        data=result.get("data"),
        error=result.get("error"),
        extracted_ids=result.get("extracted_ids", {}),
        status_code=result.get("status_code", 0),
    )


@router.get("/actions")
async def list_actions(
    app: Optional[str] = None,
    account: dict = Depends(get_account),
):
    """List all available actions, optionally filtered by app.

    Example:
        GET /v1/actions?app=gmail
        GET /v1/actions  (all apps)
    """
    from anytool import AnyTool

    # Map friendly names to anytool app names
    APP_MAP = {
        "gmail": "google", "google_drive": "google", "google_sheets": "google",
        "google_calendar": "google", "google_docs": "google", "google": "google",
        "slack": "slack", "docusign": "docusign", "freshdesk": "freshdesk",
        "hubspot": "hubspot", "github": "github", "zendesk": "zendesk",
        "whatsapp": "whatsapp",
    }

    anytool_app = APP_MAP.get(app.lower(), app.lower()) if app else None
    actions = AnyTool.list_actions(anytool_app)
    return {"actions": actions, "total": len(actions)}


@router.get("/tools")
async def get_tool_definitions(
    app: str,
    user_id: str,
    account: dict = Depends(get_account),
):
    """Get LangChain-compatible tool definitions for an app.

    Returns tool schemas that can be used with any LLM framework.

    Example:
        GET /v1/tools?app=gmail&user_id=customer-123
    """
    from anytool import AnyTool as AnyToolClass

    APP_MAP = {
        "gmail": "google", "google_drive": "google", "google_sheets": "google",
        "google_calendar": "google", "google_docs": "google", "google": "google",
        "slack": "slack", "docusign": "docusign", "freshdesk": "freshdesk",
        "hubspot": "hubspot", "github": "github", "zendesk": "zendesk",
        "whatsapp": "whatsapp",
    }

    anytool_app = APP_MAP.get(app.lower(), app.lower())
    actions = AnyToolClass.list_actions(anytool_app)

    # Build OpenAI-compatible function definitions
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
