"""
API execution — call any action for a user_id.

POST /v1/execute    → execute an action (v2 spec-first engine)
GET  /v1/actions    → list available actions
GET  /v1/tools      → get OpenAI-compatible tool definitions
GET  /v1/tools/mcp  → get MCP-compatible tool definitions
GET  /v1/apps       → list available apps (generic, from registry + specs)
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


# ── Generic app resolver ─────────────────────────────────────────────
# Derives provider from action name + registry. No hardcoded mapping.

def _resolve_provider(action_or_app: str) -> str:
    """Resolve an action prefix or app slug to the OAuth provider.

    Uses SUB_APPS registry to map sub-app prefixes (gmail_, calendar_)
    back to their parent provider (google). Falls through to identity
    for providers without sub-apps (slack → slack).
    """
    from anytool.apps.registry import SUB_APPS
    key = action_or_app.lower().rstrip("_")
    # Check if it's a sub-app action prefix (e.g. "gmail" from "gmail_send_email")
    for sub_slug, sub_config in SUB_APPS.items():
        prefix = sub_config.action_prefix.rstrip("_")
        if key == prefix or key == sub_slug or key == sub_slug.replace("_", ""):
            return sub_config.parent
    return key


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
            action_prefix = body.action.split("_")[0] if "_" in body.action else ""
            provider = _resolve_provider(action_prefix)

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


# ── List Apps (generic) ──────────────────────────────────────────────

@router.get("/apps")
async def list_apps(
    ctx: AuthContext = Depends(get_auth_context),
):
    """List all available apps with icons and sub-app breakdowns.

    Fully generic — reads everything from the registry + specs.
    Apps with sub-apps (defined in SUB_APPS registry) are split automatically.
    Add a new app = add specs + optional SubAppConfig. Zero code changes here.
    """
    from server.engine_v2 import get_v2_engine
    from anytool.apps.registry import APPS, get_sub_apps_for, get_icon_path

    engine = get_v2_engine()
    all_actions = engine.list_actions()

    # Group actions by app
    app_actions: Dict[str, list] = {}
    for action in all_actions:
        app_name = action.get("app", "")
        app_actions.setdefault(app_name, []).append(action)

    apps = []
    for app_name, actions in app_actions.items():
        # Only show apps that have auth configured (users can actually connect)
        app_config = APPS.get(app_name)
        if not app_config:
            continue  # No config at all — skip
        has_auth = (
            app_config.auth_type in ("api_key", "bearer")
            or (app_config.authorize_url and app_config.token_url)
        )
        if not has_auth:
            continue  # OAuth not configured yet — hide from users

        sub_apps = get_sub_apps_for(app_name)

        if sub_apps:
            # Split into sub-apps based on action prefix
            for sub_slug, sub_config in sub_apps.items():
                sub_actions = [a for a in actions if a["name"].startswith(sub_config.action_prefix)]
                if sub_actions:
                    parent_config = APPS.get(app_name)
                    apps.append({
                        "slug": sub_slug.upper().replace("_", ""),
                        "name": sub_config.name,
                        "provider": app_name,
                        "description": f"{sub_config.description} — {len(sub_actions)} actions" if sub_config.description else f"{len(sub_actions)} actions",
                        "icon_path": sub_config.icon_url or get_icon_path(app_name),
                        "action_count": len(sub_actions),
                        "auth_type": parent_config.auth_type if parent_config else "oauth2",
                        "auth_fields": [],
                        "action_prefix": sub_config.action_prefix,
                    })
        else:
            # No sub-apps — emit as a single app
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


# ── List Actions ─────────────────────────────────────────────────────

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
    anytool_app = _resolve_provider(app) if app else None
    actions = engine.list_actions(anytool_app)
    return {"actions": actions, "total": len(actions)}


# ── Tool Definitions ─────────────────────────────────────────────────

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
    anytool_app = _resolve_provider(app) if app else None
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
    anytool_app = _resolve_provider(app) if app else None
    tools = engine.get_mcp_tools(app=anytool_app)
    return {"tools": tools, "total": len(tools)}
