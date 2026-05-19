"""
MCP (Model Context Protocol) server — exposes anytool actions as MCP tools.

POST /v1/mcp/tools/list  → list available tools (MCP format)
POST /v1/mcp/tools/call  → execute a tool call

Compatible with any MCP client (Claude Desktop, Cursor, etc.)
Requires API key authentication.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_auth_context, AuthContext
from server.engine import get_api_for_workspace

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ── MCP Protocol Models ──────────────────────────────────────────────

class MCPToolsListRequest(BaseModel):
    """MCP tools/list request."""
    pass


class MCPToolCallRequest(BaseModel):
    """MCP tools/call request."""
    name: str
    arguments: Dict[str, Any] = {}
    # MCP requires connection_id to know which user's credentials to use
    _meta: Dict[str, Any] = {}


class MCPToolCallWithContext(BaseModel):
    """Tool call with user context (for anytool)."""
    name: str
    arguments: Dict[str, Any] = {}
    user_id: str = ""  # Which end-user's connection to use


# ── Routes ───────────────────────────────────────────────────────────

@router.post("/tools/list")
async def mcp_list_tools(
    body: MCPToolsListRequest = MCPToolsListRequest(),
    ctx: AuthContext = Depends(get_auth_context),
):
    """List all available tools in MCP format.

    Returns tools with JSON Schema parameters, compatible with
    Claude Desktop, Cursor, and other MCP clients.
    """
    from anytool import AnyTool as AnyToolClass

    actions = AnyToolClass.list_actions()
    tools = []

    _type_map = {
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "list": "array",
        "object": "object",
    }

    for action in actions:
        properties = {}
        required = []

        for p in action.get("params", []):
            prop: Dict[str, Any] = {
                "type": _type_map.get(p["type"], "string"),
                "description": p.get("description", ""),
            }
            if p.get("enum"):
                prop["enum"] = p["enum"]
            if p.get("default") is not None:
                prop["default"] = p["default"]
            if prop["type"] == "array":
                prop["items"] = {"type": "string"}
            properties[p["name"]] = prop
            if p.get("required"):
                required.append(p["name"])

        # Add user_id as a required parameter
        properties["user_id"] = {
            "type": "string",
            "description": "The end-user ID whose connected account to use",
        }
        required.append("user_id")

        tools.append({
            "name": action["name"],
            "description": action["description"],
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        })

    return {"tools": tools}


@router.post("/tools/call")
async def mcp_call_tool(
    body: MCPToolCallWithContext,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Execute a tool call via MCP protocol.

    The user_id field specifies which end-user's connection to use.

    Returns MCP-compatible response with content array.
    """
    if not body.user_id:
        # Try to get user_id from arguments
        body.user_id = body.arguments.pop("user_id", "")

    if not body.user_id:
        return {
            "content": [{
                "type": "text",
                "text": "Error: user_id is required. Specify which end-user's connection to use.",
            }],
            "isError": True,
        }

    api = await get_api_for_workspace(ctx.workspace_id, ctx.account_id)

    try:
        result = await api.call(
            body.name,
            connection_id=body.user_id,
            **body.arguments,
        )
    except ValueError as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Execution failed: {e}"}],
            "isError": True,
        }

    # Format response
    import json
    if result.get("successful"):
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result.get("data", {}), indent=2, default=str),
            }],
        }
    else:
        return {
            "content": [{
                "type": "text",
                "text": f"Error: {result.get('error', 'Unknown error')}",
            }],
            "isError": True,
        }
