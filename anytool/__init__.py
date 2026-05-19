"""
anytool — Agent-native API execution.

No wrappers. Curated specs. Direct execution.

Modes:
  Platform:   AnyTool(api_key="at_xxxx")
  Standalone: AnyTool(token_store=MemoryTokenStore())
  Nango:      AnyTool(nango_secret_key="xxx")  # legacy
"""

from anytool.client import AnyTool
from anytool.auth.token_store import TokenStore, MemoryTokenStore
from anytool.auth.models import AppCredentials, UserTokens
from anytool.auth.nango import NangoClient
from anytool.triggers.base import TriggerConfig, TriggerEvent
from anytool.triggers.store import TriggerStore, MemoryTriggerStore
from anytool.triggers.engine import TriggerEngine

__version__ = "0.1.4"

__all__ = [
    "AnyTool",
    "NangoClient",
    "TokenStore",
    "MemoryTokenStore",
    "AppCredentials",
    "UserTokens",
    "TriggerConfig",
    "TriggerEvent",
    "TriggerStore",
    "MemoryTriggerStore",
    "TriggerEngine",
]
