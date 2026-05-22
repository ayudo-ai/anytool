"""
MCP adapter — compile ActionSpecs into MCP tool definitions.

MCP (Model Context Protocol) uses JSON Schema for tool input schemas,
similar to OpenAI but with 'inputSchema' instead of 'parameters'.

    from anytool.core.adapters.mcp import specs_to_mcp_tools

    tools = specs_to_mcp_tools(specs)
    # → Ready for MCP tools/list response
"""

from __future__ import annotations

from typing import Any, Dict, List

from anytool.core.models import ActionSpec
from anytool.core.adapters.openai import _clean_schema_for_openai


def spec_to_mcp_tool(spec: ActionSpec) -> Dict[str, Any]:
    """Convert a single ActionSpec into an MCP tool definition."""
    schema = spec.llm_schema
    cleaned = _clean_schema_for_openai(schema)

    if cleaned.get("type") != "object":
        cleaned = {"type": "object", "properties": {}, "required": []}

    return {
        "name": spec.name,
        "description": spec.description.strip(),
        "inputSchema": cleaned,
    }


def specs_to_mcp_tools(specs: List[ActionSpec]) -> List[Dict[str, Any]]:
    """Convert a list of ActionSpecs into MCP tool definitions."""
    return [spec_to_mcp_tool(s) for s in specs]
