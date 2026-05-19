"""
Platform configuration — loaded from environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class PlatformConfig:
    """Platform settings."""

    # Token encryption key (Fernet — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    token_encryption_key: str = ""

    # PostgreSQL — uses 'anytool' schema in the same Postgres instance
    # Fully isolated from Ayudo's tables (different schema)
    db_host: str = "localhost"
    db_port: str = "5432"
    db_name: str = "metadb"  # same DB instance, different schema
    db_user: str = "ayudo"
    db_password: str = "password"
    db_schema: str = "anytool"  # all tables live here

    # Google SSO (for developer login — same Client ID as Nango)
    google_client_id: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8100
    base_url: str = "http://localhost:8100"

    # API
    api_prefix: str = "/v1"

    @property
    def database_url(self) -> str:
        """Async PostgreSQL URL for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @classmethod
    def from_env(cls) -> "PlatformConfig":
        return cls(
            token_encryption_key=os.environ.get("ANYTOOL_TOKEN_KEY", ""),
            db_host=os.environ.get("ANYTOOL_DB_HOST", os.environ.get("DB_HOST", "localhost")),
            db_port=os.environ.get("ANYTOOL_DB_PORT", os.environ.get("DB_PORT", "5432")),
            db_name=os.environ.get("ANYTOOL_DB_NAME", "metadb"),
            db_user=os.environ.get("ANYTOOL_DB_USER", os.environ.get("DB_USER", "ayudo")),
            db_password=os.environ.get("ANYTOOL_DB_PASSWORD", os.environ.get("DB_PASSWORD", "password")),
            db_schema=os.environ.get("ANYTOOL_DB_SCHEMA", "anytool"),
            google_client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8100")),
            base_url=os.environ.get("BASE_URL", "http://localhost:8100"),
        )


config = PlatformConfig.from_env()
