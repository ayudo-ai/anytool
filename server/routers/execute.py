"""
API execution — call any action for a user_id.

POST /v1/execute    → execute an action (v2 spec-first engine)
GET  /v1/actions    → list available actions
GET  /v1/tools      → get OpenAI-compatible tool definitions
GET  /v1/tools/mcp  → get MCP-compatible tool definitions
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_auth_context, AuthContext
import time

from loguru import logger
from server.database import get_record, update_record_fields, atomic_increment, put_record, new_id
from server.engine import get_api_for_workspace

router = APIRouter(tags=["execute"])


class ExecuteRequest(BaseModel):
    action: str              # gmail_send_email, slack_send_message, etc.
    user_id: str             # end-user whose connection to use
    params: Dict[str, Any] = {}


# ── v2 Execute (spec-first, pass-through) ────────────────────────────

@router.post("/execute")
async def execute_action_v2(body: ExecuteRequest, ctx: AuthContext = Depends(get_auth_context)):
    """Execute an API action using the v2 spec-first engine.

    The LLM constructs the exact request body. Anytool sends it through
    unchanged to the API. No intermediate models. No data loss.

    For Tier 1/2 actions: params IS the API request body.
    For Tier 3 actions (e.g. gmail_send_email): params are agent-friendly
    fields that get encoded (MIME, etc.) before sending.

    Example:
        POST /v1/execute
        {
            "action": "docusign_create_envelope",
            "user_id": "customer-123",
            "params": {
                "templateId": "2184100d-...",
                "templateRoles": [
                    {"roleName": "Signer", "name": "Sarah", "email": "sarah@example.com"}
                ],
                "status": "sent"
            }
        }
    """
    # Check workspace usage limit
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

    from server.engine_v2 import execute_action as v2_execute

    start_time = time.monotonic()
    result = None
    error_msg = None

    logger.info(f"[execute] action={body.action} params={body.params}")

    try:
        result = await v2_execute(
            action=body.action,
            user_id=body.user_id,
            body=body.params,
            workspace_id=ctx.workspace_id,
            account_id=ctx.account_id,
        )
    except ValueError as e:
        error_msg = str(e)
        raise HTTPException(400, error_msg)
    except Exception as e:
        error_msg = f"Execution failed: {e}"
        raise HTTPException(500, error_msg)
    finally:
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Atomically increment usage counter
        await atomic_increment("workspace", ctx.workspace_id, "calls_this_month")

        # Write usage log
        try:
            action_app = body.action.split("_")[0] if "_" in body.action else ""
            provider = APP_MAP.get(action_app, action_app)

            status_code = result.status_code if result else 0
            successful = result.successful if result else False
            log_error = error_msg or (result.error if result else None)

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
                    "status_code": status_code,
                    "successful": successful,
                    "duration_ms": duration_ms,
                    "error": log_error,
                    "engine": "v2",
                },
            )
        except Exception:
            pass

    return {
        "successful": result.successful,
        "data": result.data,
        "error": result.error,
        "extracted_ids": result.extracted_ids,
        "status_code": result.status_code,
        "duration_ms": result.duration_ms,
    }



# ── App mapping ──────────────────────────────────────────────────────

APP_MAP = {
    "gmail": "google", "google_drive": "google", "google_sheets": "google",
    "google_calendar": "google", "google_docs": "google", "google": "google",
    "slack": "slack", "docusign": "docusign", "freshdesk": "freshdesk",
    "hubspot": "hubspot", "github": "github", "zendesk": "zendesk",
    "whatsapp": "whatsapp",
}


@router.get("/apps")
async def list_apps(
    ctx: AuthContext = Depends(get_auth_context),
):
    """List all available apps with icons and sub-app breakdowns.

    Returns apps from the spec registry with CDN icon paths.
    Google is split into sub-apps (Gmail, Drive, Sheets, etc.).
    """
    from server.engine_v2 import get_v2_engine
    from anytool.apps.registry import APPS, SUB_APP_ICONS, get_icon_path
    from server.config import config

    engine = get_v2_engine()
    all_actions = engine.list_actions()

    # Group actions by app
    app_actions: Dict[str, list] = {}
    for action in all_actions:
        app_name = action.get("app", "")
        app_actions.setdefault(app_name, []).append(action)

    # Google sub-apps
    GOOGLE_SUB_APPS = {
        "gmail": {"name": "Gmail", "prefix": "gmail_", "description": "Send, read, and manage emails"},
        "google_drive": {"name": "Google Drive", "prefix": "drive_", "description": "Manage files and folders"},
        "google_sheets": {"name": "Google Sheets", "prefix": "sheets_", "description": "Read and write spreadsheets"},
        "google_calendar": {"name": "Google Calendar", "prefix": "calendar_", "description": "Manage events and calendars"},
        "google_docs": {"name": "Google Docs", "prefix": "docs_", "description": "Create and edit documents"},
    }

    apps = []
    for app_name, actions in app_actions.items():
        if app_name == "google":
            # Split into sub-apps
            for sub_slug, sub_info in GOOGLE_SUB_APPS.items():
                sub_actions = [a for a in actions if a["name"].startswith(sub_info["prefix"])]
                if sub_actions:
                    apps.append({
                        "slug": sub_slug.upper().replace("_", ""),
                        "name": sub_info["name"],
                        "provider": "google",
                        "description": f"{sub_info['description']} \u2014 {len(sub_actions)} actions",
                        "icon_path": get_icon_path("google", sub_slug),
                        "action_count": len(sub_actions),
                        "auth_type": "oauth2",
                        "auth_fields": [],
                        "action_prefix": sub_info["prefix"],
                    })
        else:
            app_config = APPS.get(app_name)
            auth_type = app_config.auth_type if app_config else "oauth2"
            auth_fields = []
            if app_config and app_config.auth_fields:
                auth_fields = [
                    {
                        "name": f.name,
                        "label": f.label,
                        "placeholder": f.placeholder,
                        "type": f.type,
                        "required": f.required,
                        "help_text": f.help_text,
                        "suffix": f.suffix,
                    }
                    for f in app_config.auth_fields
                ]
            apps.append({
                "slug": app_name.upper(),
                "name": app_config.name if app_config else app_name.title(),
                "provider": app_name,
                "description": f"{len(actions)} actions available",
                "icon_path": get_icon_path(app_name),
                "action_count": len(actions),
                "auth_type": auth_type,
                "auth_fields": auth_fields,
                "action_prefix": f"{app_name}_",
            })

    return {"apps": apps, "total": len(apps)}


@router.get("/actions")
async def list_actions(
    app: Optional[str] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """List all available actions from the v2 spec registry.

    Example:
        GET /v1/actions?app=slack
    """
    from server.engine_v2 import get_v2_engine

    engine = get_v2_engine()
    anytool_app = APP_MAP.get(app.lower(), app.lower()) if app else None
    actions = engine.list_actions(anytool_app)
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
    app: Optional[str] = None,
    actions: Optional[str] = None,
    include_examples: bool = True,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Get OpenAI-compatible tool definitions from v2 spec registry.

    Uses the real API spec (body_schema) as the tool parameters.
    Nested objects are preserved — no flattening.

    Args:
        app: Filter by app slug (e.g. 'slack', 'docusign')
        actions: Comma-separated action names to include
        include_examples: Include examples in tool descriptions (recommended)

    Example:
        GET /v1/tools?app=docusign
        GET /v1/tools?actions=gmail_send_email,slack_send_message
    """
    from server.engine_v2 import get_v2_engine

    engine = get_v2_engine()
    anytool_app = APP_MAP.get(app.lower(), app.lower()) if app else None
    action_list = [a.strip() for a in actions.split(",")] if actions else None

    tools = engine.get_openai_tools(
        app=anytool_app,
        actions=action_list,
        include_examples=include_examples,
    )
    return {"tools": tools, "total": len(tools), "app": app}


@router.get("/tools/mcp")
async def get_mcp_tool_definitions(
    app: Optional[str] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Get MCP-compatible tool definitions from v2 spec registry.

    Example:
        GET /v1/tools/mcp?app=slack
    """
    from server.engine_v2 import get_v2_engine

    engine = get_v2_engine()
    anytool_app = APP_MAP.get(app.lower(), app.lower()) if app else None
    tools = engine.get_mcp_tools(app=anytool_app)
    return {"tools": tools, "total": len(tools)}
