"""
v2 Engine singleton for the platform server.

Loads specs from the registry, provides execution with auth bridge.

    from server.engine_v2 import get_v2_engine, execute_action

    engine = get_v2_engine()
    result = await execute_action("gmail_send_email", "user-123", body={...}, workspace_id="ws-1", account_id="acc-1")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from anytool.core.engine import Engine
from anytool.core.executor import AuthTokens, ExecutionResult
from anytool.core.auth_bridge import AuthBridge
from anytool.auth.models import AppCredentials

_engine: Optional[Engine] = None

# Registry path — relative to project root
_REGISTRY_PATH = Path(__file__).parent.parent / "registry"


def get_v2_engine() -> Engine:
    """Get the shared v2 Engine instance."""
    global _engine
    if _engine is None:
        _engine = Engine(registry_path=_REGISTRY_PATH)
        logger.info(
            f"[engine_v2] Initialized | "
            f"{len(_engine.registry)} specs | "
            f"apps: {_engine.list_apps()}"
        )
    return _engine


async def execute_action(
    action: str,
    user_id: str,
    body: Dict[str, Any],
    workspace_id: str = "",
    account_id: str = "",
) -> ExecutionResult:
    """Execute an action with full auth resolution.

    This is the main entry point for the server. It:
    1. Looks up the spec
    2. Resolves auth tokens for the user
    3. Executes via the v2 engine
    """
    engine = get_v2_engine()

    # Get the spec to determine the app
    spec = engine.get_spec(action)
    if not spec:
        return ExecutionResult(
            successful=False,
            error=f"Unknown action '{action}'. Available: {engine.registry.names()[:20]}",
        )

    # Resolve auth
    auth = await _resolve_auth(spec.app, user_id, workspace_id, account_id)

    # Execute
    return await engine.execute(action, body, auth)


async def _resolve_auth(
    app: str,
    user_id: str,
    workspace_id: str,
    account_id: str,
) -> AuthTokens:
    """Resolve auth tokens for a user.

    Uses the existing server engine to get workspace-specific credentials
    and the auth bridge to convert tokens.
    """
    from server.engine import get_api_for_workspace

    # Get the AnyTool instance with workspace credentials
    api = await get_api_for_workspace(workspace_id, account_id)

    # The old API has an OAuth manager and credentials
    if not api._oauth:
        raise ValueError("Auth not available — API not in standalone mode")

    bridge = AuthBridge(
        oauth_manager=api._oauth,
        credentials=api._credentials,
    )

    return await bridge.get_auth(app, user_id)
