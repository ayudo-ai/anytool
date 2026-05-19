"""
AnyAPI client — the single entry point.

Two modes:
  1. Nango mode (recommended):
     api = AnyAPI(nango_secret_key="nango-xxx")

  2. Standalone mode:
     api = AnyAPI(token_store=MemoryTokenStore())
     api.register_app(AppCredentials(app="google", ...))
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from anyapi.specs.base import ActionSpec

# Import all spec modules
from anyapi.specs.google import GOOGLE_SPECS
from anyapi.specs.docusign import DOCUSIGN_SPECS
from anyapi.specs.freshdesk import FRESHDESK_SPECS
from anyapi.specs.slack import SLACK_SPECS
from anyapi.specs.hubspot import HUBSPOT_SPECS

# Spec registry
_ALL_SPECS: Dict[str, ActionSpec] = {}
_APP_SPECS: Dict[str, List[ActionSpec]] = {}

for spec in GOOGLE_SPECS + DOCUSIGN_SPECS + FRESHDESK_SPECS + SLACK_SPECS + HUBSPOT_SPECS:
    _ALL_SPECS[spec.name] = spec
    _APP_SPECS.setdefault(spec.app, []).append(spec)


# Provider → Nango provider config key mapping.
# These MUST match the Integration ID in your Nango dashboard.
# Override at runtime with: api.set_provider_mapping("docusign", "my-docusign-key")
_NANGO_PROVIDERS: Dict[str, str] = {
    "google": "google",
    "freshdesk": "freshdesk",
    "docusign": "docusign-sandbox",  # Nango names sandbox differently
    "slack": "slack",
    "microsoft": "microsoft",
    "github": "github",
    "hubspot": "hubspot",
}


class AnyAPI:
    """Main client for anyapi."""

    def __init__(
        self,
        nango_secret_key: str = "",
        nango_base_url: str = "",
        token_store=None,
    ):
        """
        Args:
            nango_secret_key: Nango Secret Key (enables Nango mode)
            nango_base_url: Override Nango API URL (for self-hosted)
            token_store: TokenStore instance (standalone mode, no Nango)
        """
        self._nango = None
        self._oauth = None
        self._executor = None
        self._credentials = {}

        if nango_secret_key:
            # Nango mode
            from anyapi.auth.nango import NangoClient
            self._nango = NangoClient(
                secret_key=nango_secret_key,
                base_url=nango_base_url,
            )
            from anyapi.executor import APIExecutor
            self._executor = APIExecutor(nango=self._nango)
            logger.info("[anyapi] Initialized in Nango mode")
        elif token_store:
            # Standalone mode
            from anyapi.auth.oauth import OAuthManager
            from anyapi.executor import APIExecutor
            self._oauth = OAuthManager(token_store)
            self._executor = APIExecutor(oauth_manager=self._oauth)
            self._store = token_store
            logger.info("[anyapi] Initialized in standalone mode")
        else:
            raise ValueError("Provide either nango_secret_key or token_store")

    # ── Nango Auth ───────────────────────────────────────────────────

    async def get_connect_session(
        self,
        provider: str,
        connection_id: str,
    ) -> Dict[str, Any]:
        """Create a Nango Connect session (for frontend ConnectUI).

        Returns a session token to pass to Nango's frontend widget.
        """
        if not self._nango:
            raise ValueError("Nango mode required for get_connect_session")
        return await self._nango.create_connect_session(
            provider=_NANGO_PROVIDERS.get(provider, provider),
            connection_id=connection_id,
        )

    async def get_auth_url(
        self,
        provider: str,
        connection_id: str,
        callback_url: str = "",
        extra_scopes: Optional[List[str]] = None,
    ) -> str:
        """Get OAuth authorization URL.

        Nango mode: Uses Nango's auth endpoint
        Standalone mode: Uses our own OAuth manager
        """
        if self._nango:
            return await self._nango.get_auth_url(
                provider=_NANGO_PROVIDERS.get(provider, provider),
                connection_id=connection_id,
                callback_url=callback_url,
            )
        else:
            creds = self._get_credentials(provider)
            return await self._oauth.get_auth_url(creds, connection_id, extra_scopes)

    # ── Standalone Auth (only when not using Nango) ──────────────────

    def set_provider_mapping(self, app: str, nango_key: str) -> None:
        """Override the Nango provider config key for an app.

        Use when your Nango integration ID differs from the default.
        Example: api.set_provider_mapping("docusign", "docusign-prod")
        """
        _NANGO_PROVIDERS[app] = nango_key
        logger.info(f"[anyapi] Provider mapping: {app} → {nango_key}")

    def register_app(self, credentials) -> None:
        """Register OAuth credentials (standalone mode only)."""
        self._credentials[credentials.app] = credentials
        logger.info(f"[anyapi] Registered app: {credentials.app}")

    async def handle_callback(self, app: str, code: str, state: str):
        """Handle OAuth callback (standalone mode only)."""
        if self._nango:
            raise ValueError("In Nango mode, Nango handles callbacks automatically")
        creds = self._get_credentials(app)
        return await self._oauth.handle_callback(creds, code, state)

    # ── Connection Management ────────────────────────────────────────

    async def is_connected(self, provider: str, connection_id: str) -> bool:
        """Check if a user has connected an app."""
        if self._nango:
            conn = await self._nango.get_connection(
                _NANGO_PROVIDERS.get(provider, provider), connection_id
            )
            return bool(conn)
        else:
            tokens = await self._store.get_tokens(provider, connection_id)
            return tokens is not None

    async def list_connections(self, connection_id: str) -> list:
        """List all connected apps for a user."""
        if self._nango:
            return await self._nango.list_connections(connection_id)
        else:
            return await self._store.list_connected(connection_id)

    async def disconnect(self, provider: str, connection_id: str) -> None:
        """Disconnect an app."""
        if self._nango:
            await self._nango.delete_connection(
                _NANGO_PROVIDERS.get(provider, provider), connection_id
            )
        else:
            await self._store.delete_tokens(provider, connection_id)

    # ── API Execution ────────────────────────────────────────────────

    async def call(
        self,
        action: str,
        connection_id: str,
        **params: Any,
    ) -> Dict[str, Any]:
        """Call an API action by name.

        Example:
            result = await api.call(
                "gmail_send_email",
                connection_id="workspace-123",
                to="vendor@example.com",
                subject="Follow-up",
                body="Hello",
            )
        """
        spec = _ALL_SPECS.get(action)
        if not spec:
            raise ValueError(f"Unknown action '{action}'. Available: {list(_ALL_SPECS.keys())}")

        provider = _NANGO_PROVIDERS.get(spec.app, spec.app)

        return await self._executor.execute(
            spec=spec,
            params=params,
            provider=provider,
            connection_id=connection_id,
            credentials=self._credentials.get(spec.app),
        )

    # ── LangChain Tools ──────────────────────────────────────────────

    def get_tools(
        self,
        app: str,
        connection_id: str,
        actions: Optional[List[str]] = None,
    ) -> list:
        """Get LangChain StructuredTools for an app.

        Returns tools ready for llm.bind_tools(tools).
        """
        from anyapi.tools.langchain import build_tools

        specs = _APP_SPECS.get(app, [])
        if actions:
            specs = [s for s in specs if s.name in actions]

        if not specs:
            logger.warning(f"[anyapi] No specs for app={app} actions={actions}")
            return []

        provider = _NANGO_PROVIDERS.get(app, app)

        return build_tools(
            executor=self._executor,
            specs=specs,
            provider=provider,
            connection_id=connection_id,
        )

    def get_all_tools(self, connection_id: str, apps: Optional[List[str]] = None) -> list:
        """Get LangChain tools for multiple apps."""
        all_tools = []
        for app in (apps or list(_APP_SPECS.keys())):
            tools = self.get_tools(app, connection_id)
            all_tools.extend(tools)
        return all_tools

    # ── Discovery ────────────────────────────────────────────────────

    @staticmethod
    def list_actions(app: Optional[str] = None) -> List[Dict[str, str]]:
        """List available actions."""
        specs = _APP_SPECS.get(app, []) if app else list(_ALL_SPECS.values())
        return [
            {
                "name": s.name,
                "app": s.app,
                "description": s.description[:200],
                "method": s.method,
                "params": [p.name for p in s.required_params],
            }
            for s in specs
        ]

    # ── Internal ─────────────────────────────────────────────────────

    def _get_credentials(self, app):
        if app not in self._credentials:
            raise ValueError(f"App '{app}' not registered. Registered: {list(self._credentials.keys())}")
        return self._credentials[app]

    async def close(self):
        if self._nango:
            await self._nango.close()
        if self._oauth:
            await self._oauth.close()
