"""
Singleton AnyTool instance for the platform.

All routers share this single instance.
Initialized on startup, closed on shutdown.
"""

from __future__ import annotations

from typing import Optional

from anytool import AnyTool
from server.config import config

_api: Optional[AnyTool] = None


def get_api() -> AnyTool:
    """Get the shared AnyTool instance."""
    global _api
    if _api is None:
        _api = AnyTool(nango_secret_key=config.nango_secret_key)
    return _api


async def close_api():
    """Cleanup on shutdown."""
    global _api
    if _api:
        await _api.close()
        _api = None
