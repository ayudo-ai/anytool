"""
anytool — Spec-first API integration. Zero wrappers. Zero data loss.

    from anytool import Engine, AnyTool, MemoryTokenStore, AppCredentials

    # v2 Engine — spec-first execution
    engine = Engine(registry_path="registry/")
    result = await engine.execute("gmail_send_email", body={...}, auth=auth)

    # Auth management
    api = AnyTool(token_store=MemoryTokenStore())
    api.register_app(AppCredentials(app="google", ...))
    auth_url = await api.get_auth_url("google", connection_id="user-123")
"""

from anytool.client import AnyTool
from anytool.core.engine import Engine
from anytool.core.executor import AuthTokens, ExecutionResult
from anytool.core.loader import SpecRegistry
from anytool.core.models import ActionSpec
from anytool.auth.token_store import TokenStore, MemoryTokenStore
from anytool.auth.models import AppCredentials, UserTokens
from anytool.triggers.base import TriggerConfig, TriggerEvent
from anytool.triggers.store import TriggerStore, MemoryTriggerStore
from anytool.triggers.engine import TriggerEngine

__version__ = "2.0.0"

__all__ = [
    # v2 Engine
    "Engine",
    "AuthTokens",
    "ExecutionResult",
    "SpecRegistry",
    "ActionSpec",
    # Auth
    "AnyTool",
    "TokenStore",
    "MemoryTokenStore",
    "AppCredentials",
    "UserTokens",
    # Triggers
    "TriggerConfig",
    "TriggerEvent",
    "TriggerStore",
    "MemoryTriggerStore",
    "TriggerEngine",
]
