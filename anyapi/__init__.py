"""
anyapi — Agent-native API execution.

No wrappers. No Composio. No Pipedream.

Modes:
  Nango:      AnyAPI(nango_secret_key="xxx")
  Standalone: AnyAPI(token_store=MemoryTokenStore())
"""

from anyapi.client import AnyAPI
from anyapi.auth.token_store import TokenStore, MemoryTokenStore
from anyapi.auth.models import AppCredentials, UserTokens
from anyapi.auth.nango import NangoClient
from anyapi.triggers.base import TriggerConfig, TriggerEvent
from anyapi.triggers.store import TriggerStore, MemoryTriggerStore
from anyapi.triggers.engine import TriggerEngine

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
