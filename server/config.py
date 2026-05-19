"""
Platform configuration — loaded from environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class PlatformConfig:
    """Platform settings."""

    # Nango (auth layer — hidden from developers)
    nango_secret_key: str = ""
    nango_base_url: str = "https://api.nango.dev"

    # Database
    database_url: str = "sqlite+aiosqlite:///anytool.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 8100
    base_url: str = "http://localhost:8100"

    # API
    api_prefix: str = "/v1"

    @classmethod
    def from_env(cls) -> "PlatformConfig":
        return cls(
            nango_secret_key=os.environ.get("NANGO_SECRET_KEY", ""),
            nango_base_url=os.environ.get("NANGO_BASE_URL", "https://api.nango.dev"),
            database_url=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///anytool.db"),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8100")),
            base_url=os.environ.get("BASE_URL", "http://localhost:8100"),
        )


config = PlatformConfig.from_env()
