"""
Engine — the single entry point for the v2 core.

    from anytool.core.engine import Engine
    from anytool.core.executor import AuthTokens

    engine = Engine(registry_path="registry/")

    # Execute an action
    result = await engine.execute(
        "docusign_create_envelope",
        body={"templateId": "...", "templateRoles": [...], "status": "sent"},
        auth=AuthTokens(access_token="...", metadata={"account_id": "..."}),
    )

    # Get OpenAI tool definitions
    tools = engine.get_openai_tools(app="docusign")

    # List available actions
    actions = engine.list_actions(app="slack")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from anytool.core.loader import SpecRegistry
from anytool.core.executor import Executor, ExecutionResult, AuthTokens
from anytool.core.models import ActionSpec


class Engine:
    """Anytool v2 engine.

    Loads specs from the registry, executes actions, generates tool definitions.
    Stateless — all auth is passed per-call.
    """

    def __init__(
        self,
        registry_path: str | Path = "registry/",
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.registry = SpecRegistry(registry_path)
        self.executor = Executor(timeout=timeout, max_retries=max_retries)

        logger.info(
            f"[engine] Initialized | "
            f"{len(self.registry)} specs | "
            f"{len(self.registry.apps())} apps: {self.registry.apps()}"
        )

    # ── Execute ──────────────────────────────────────────────────────

    async def execute(
        self,
        action: str,
        body: Dict[str, Any],
        auth: AuthTokens,
    ) -> ExecutionResult:
        """Execute an API action by name.

        Args:
            action: Action name (e.g. "docusign_create_envelope")
            body: Request body as the LLM constructed it
            auth: Auth tokens with access_token and metadata
        """
        spec = self.registry.get(action)
        if not spec:
            return ExecutionResult(
                successful=False,
                error=f"Unknown action '{action}'. Available: {self.registry.names()[:20]}",
            )

        return await self.executor.execute(spec, body, auth)

    # ── Discovery ────────────────────────────────────────────────────

    def get_spec(self, action: str) -> Optional[ActionSpec]:
        """Get a spec by action name."""
        return self.registry.get(action)

    def list_actions(self, app: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available actions with metadata."""
        specs = self.registry.list_by_app(app) if app else self.registry.all()
        return [
            {
                "name": s.name,
                "app": s.app,
                "description": s.description,
                "method": s.method,
                "tier": s.tier,
                "tags": list(s.tags),
                "required_fields": s.required_fields,
            }
            for s in specs
        ]

    def list_apps(self) -> List[str]:
        """List all available app slugs."""
        return self.registry.apps()

    # ── OpenAI Tool Definitions ──────────────────────────────────────

    def get_openai_tools(
        self,
        app: Optional[str] = None,
        actions: Optional[List[str]] = None,
        include_examples: bool = True,
    ) -> List[Dict[str, Any]]:
        """Generate OpenAI function calling tool definitions.

        Returns a list ready for `tools=` in openai.chat.completions.create().

        Args:
            app: Filter by app slug.
            actions: Filter by specific action names.
            include_examples: Include examples in descriptions (recommended).
        """
        from anytool.core.adapters.openai import specs_to_openai_tools

        specs = self._filter_specs(app, actions)
        return specs_to_openai_tools(specs, include_examples=include_examples)

    # ── MCP Tool Definitions ─────────────────────────────────────────

    def get_mcp_tools(
        self,
        app: Optional[str] = None,
        actions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate MCP-compatible tool definitions.

        Returns tools in MCP format for tools/list responses.
        """
        from anytool.core.adapters.mcp import specs_to_mcp_tools

        specs = self._filter_specs(app, actions)
        return specs_to_mcp_tools(specs)

    # ── Internal ─────────────────────────────────────────────────────

    def _filter_specs(
        self,
        app: Optional[str] = None,
        actions: Optional[List[str]] = None,
    ) -> List[ActionSpec]:
        """Filter specs by app and/or action names."""
        if actions:
            action_set = set(actions)
            return [s for s in self.registry.all() if s.name in action_set]
        if app:
            return self.registry.list_by_app(app)
        return self.registry.all()
