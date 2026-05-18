"""
anyapi — Agent-native API execution.

No wrappers. No Composio. No Pipedream.

Two modes:
  Nango mode:     AnyAPI(nango_secret_key="nango-xxx")
  Standalone:     AnyAPI(token_store=MemoryTokenStore())
"""

from anyapi.client import AnyAPI
from anyapi.auth.token_store import TokenStore, MemoryTokenStore
from anyapi.auth.models import AppCredentials, UserTokens
from anyapi.auth.nango import NangoClient

__version__ = "0.1.0"

__all__ = [
    "AnyAPI",
    "NangoClient",
    "TokenStore",
    "MemoryTokenStore",
    "AppCredentials",
    "UserTokens",
]
