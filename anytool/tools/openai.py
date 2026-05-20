"""
OpenAI function calling adapter — converts ActionSpecs into OpenAI tool format.

Usage:
    from anytool import AnyTool
    from anytool.tools.openai import OpenAIToolSet

    anytool = AnyTool(api_key="at_xxx")
    toolset = OpenAIToolSet(anytool)

    tools = await toolset.get_tools("user-123", apps=["google", "github"])

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Star the ayudo-ai/anytool repo"}],
        tools=tools,
    )

    # Handle tool calls
    results = await toolset.handle_tool_calls(response, "user-123")
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from anytool.client import AnyTool


class OpenAIToolSet:
    """OpenAI function calling adapter for AnyTool."""

    def __init__(self, client: AnyTool):
        self.client = client

    async def get_tools(
        self,
        user_id: str = "",
        apps: Optional[List[str]] = None,
        actions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible tool definitions.

        Args:
            user_id: If provided, only return tools for apps this user has connected.
            apps: Filter by specific apps (e.g. ["google", "slack"]).
            actions: Filter by specific actions (e.g. ["gmail_send_email"]).

        Returns list of tool definitions for openai.chat.completions.create(tools=...)
        """
        all_tools = []

        target_apps = apps
        if not target_apps and user_id:
            # Auto-detect from user's connections
            connections = await self.client.list_connections(user_id)
            target_apps = list(set(c.get("provider", "") for c in connections))

        if not target_apps:
            target_apps = list(set(
                a["app"] for a in self.client.list_actions()
            ))

        for app in target_apps:
            tools = await self.client.get_tools_schema(app)
            all_tools.extend(tools)

        if actions:
            action_set = set(actions)
            all_tools = [t for t in all_tools if t["function"]["name"] in action_set]

        return all_tools

    async def handle_tool_calls(
        self,
        response,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """Handle tool calls from an OpenAI completion response.

        Returns tool result messages ready to append to the conversation.
        """
        tool_calls = response.choices[0].message.tool_calls or []
        results = []

        for tc in tool_calls:
            args = json.loads(tc.function.arguments)
            result = await self.client.call(
                tc.function.name,
                connection_id=user_id,
                **args,
            )
            results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
            })

        return results
