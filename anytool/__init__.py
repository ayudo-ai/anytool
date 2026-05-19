"""
anytool — Agent-native API execution.

No wrappers. No Composio. No Pipedream.

Modes:
  Nango:      AnyAPI(nango_secret_key="xxx")
  Standalone: AnyAPI(token_store=MemoryTokenStore())
"""

from anytool.client import AnyAPI
from anytool.auth.token_store import TokenStore, MemoryTokenStore
from anytool.auth.models import AppCredentials, UserTokens
from anytool.auth.nango import NangoClient
from anytool.triggers.base import TriggerConfig, TriggerEvent
from anytool.triggers.store import TriggerStore, MemoryTriggerStore
from anytool.triggers.engine import TriggerEngine

__version__ = "0.1.0"

__all__ = [
    "AnyAPI",
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
