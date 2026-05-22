"""
MCP (Model Context Protocol) server — exposes anytool actions as MCP tools.

POST /v1/mcp/tools/list  → list available tools (MCP format)
POST /v1/mcp/tools/call  → execute a tool call

Compatible with any MCP client (Claude Desktop, Cursor, etc.)
Requires API key authentication.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.auth import get_auth_context, AuthContext

router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPToolsListRequest(BaseModel):
    pass


class MCPToolCallWithContext(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}
    user_id: str = ""


@router.post("/tools/list")
async def mcp_list_tools(
    body: MCPToolsListRequest = MCPToolsListRequest(),
    ctx: AuthContext = Depends(get_auth_context),
):
    """List all available tools in MCP format."""
    from server.engine_v2 import get_v2_engine

    engine = get_v2_engine()
    tools = engine.get_mcp_tools()

    # Add user_id as required param to each tool
    for tool in tools:
        tool["inputSchema"]["properties"]["user_id"] = {
            "type": "string",
            "description": "The end-user ID whose connected account to use",
        }
        tool["inputSchema"].setdefault("required", []).append("user_id")

    return {"tools": tools}


@router.post("/tools/call")
async def mcp_call_tool(
    body: MCPToolCallWithContext,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Execute a tool call via MCP protocol."""
    if not body.user_id:
        body.user_id = body.arguments.pop("user_id", "")

    if not body.user_id:
        return {
            "content": [{"type": "text", "text": "Error: user_id is required."}],
            "isError": True,
        }

    from server.engine_v2 import execute_action

    try:
        result = await execute_action(
            action=body.name,
            user_id=body.user_id,
            body=body.arguments,
            workspace_id=ctx.workspace_id,
            account_id=ctx.account_id,
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

    import json
    if result.successful:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result.data, indent=2, default=str),
            }],
        }
    else:
        return {
            "content": [{"type": "text", "text": f"Error: {result.error}"}],
            "isError": True,
        }
