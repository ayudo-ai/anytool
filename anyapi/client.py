"""
AnyAPI client — the single entry point for the SDK.

Usage:
    from anyapi import AnyAPI, MemoryTokenStore, AppCredentials

    api = AnyAPI(token_store=MemoryTokenStore())

    # Register your OAuth credentials
    api.register_app(AppCredentials(
        app="google",
        client_id="xxx.apps.googleusercontent.com",
        client_secret="GOCSPX-xxx",
        scopes=["https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.readonly"],
    ))

    # Get OAuth URL for user to click
    url = await api.get_auth_url("google", user_id="workspace-123")

    # After OAuth callback
    tokens = await api.handle_callback("google", code="xxx", state="yyy")

    # Get LangChain tools
    tools = api.get_tools("google", user_id="workspace-123")

    # Or call directly
    result = await api.call("gmail_send_email", user_id="workspace-123",
                            to="vendor@co.com", subject="Hi", body="Hello")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from anyapi.auth.models import AppCredentials, UserTokens
from anyapi.auth.oauth import OAuthManager
from anyapi.auth.token_store import TokenStore
from anyapi.executor import APIExecutor
from anyapi.specs.base import ActionSpec


# Import all spec modules
from anyapi.specs.google import GOOGLE_SPECS

# Spec registry: action_name → ActionSpec
_ALL_SPECS: Dict[str, ActionSpec] = {}
_APP_SPECS: Dict[str, List[ActionSpec]] = {}

for spec in GOOGLE_SPECS:
    _ALL_SPECS[spec.name] = spec
    _APP_SPECS.setdefault(spec.app, []).append(spec)


class AnyAPI:
    """Main client for anyapi.

    Manages OAuth, executes API calls, and generates LangChain tools.
    """

    def __init__(self, token_store: TokenStore):
        self._store = token_store
        self._oauth = OAuthManager(token_store)
        self._executor = APIExecutor(self._oauth)
        self._credentials: Dict[str, AppCredentials] = {}

    # ── App Registration ─────────────────────────────────────────────

    def register_app(self, credentials: AppCredentials) -> None:
        """Register OAuth credentials for an app.

        Call once per app at startup. Example:
            api.register_app(AppCredentials(
                app="google",
                client_id="xxx",
                client_secret="yyy",
                scopes=["https://www.googleapis.com/auth/gmail.send"],
            ))
        """
        self._credentials[credentials.app] = credentials
        logger.info(f"[anyapi] Registered app: {credentials.app}")

    def register_api_key_app(
        self,
        app: str,
        user_id: str,
        api_key: str,
        domain: str = "",
    ) -> None:
        """Register an API-key based app (e.g. Freshdesk).

        No OAuth needed — just store the key directly.
        """
        import asyncio

        tokens = UserTokens(
            app=app,
            user_id=user_id,
            api_key=api_key,
            domain=domain,
        )
        # Store synchronously if possible, otherwise create task
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._store.save_tokens(tokens))
        except RuntimeError:
            asyncio.run(self._store.save_tokens(tokens))

        self._credentials.setdefault(app, AppCredentials(app=app, auth_type="api_key"))
        logger.info(f"[anyapi] Registered API key app: {app} user={user_id}")

    # ── OAuth Flow ───────────────────────────────────────────────────

    async def get_auth_url(
        self,
        app: str,
        user_id: str,
        extra_scopes: Optional[List[str]] = None,
    ) -> str:
        """Get the OAuth authorization URL for a user to click.

        Returns a URL — redirect the user to it or open in a popup.
        """
        creds = self._get_credentials(app)
        return await self._oauth.get_auth_url(creds, user_id, extra_scopes)

    async def handle_callback(
        self,
        app: str,
        code: str,
        state: str,
    ) -> UserTokens:
        """Handle the OAuth callback after user authorizes.

        Call this in your /oauth/callback endpoint.
        Returns the stored tokens.
        """
        creds = self._get_credentials(app)
        return await self._oauth.handle_callback(creds, code, state)

    async def disconnect(self, app: str, user_id: str) -> None:
        """Disconnect an app (delete tokens)."""
        await self._oauth.disconnect(app, user_id)

    async def list_connected(self, user_id: str) -> List[UserTokens]:
        """List all connected apps for a user."""
        return await self._store.list_connected(user_id)

    async def is_connected(self, app: str, user_id: str) -> bool:
        """Check if an app is connected for a user."""
        tokens = await self._store.get_tokens(app, user_id)
        return tokens is not None

    # ── API Execution ────────────────────────────────────────────────

    async def call(
        self,
        action: str,
        user_id: str,
        **params: Any,
    ) -> Dict[str, Any]:
        """Call an API action by name.

        Example:
            result = await api.call(
                "gmail_send_email",
                user_id="workspace-123",
                to="vendor@example.com",
                subject="Follow-up",
                body="Hello, please update the status.",
            )
        """
        spec = _ALL_SPECS.get(action)
        if not spec:
            available = list(_ALL_SPECS.keys())
            raise ValueError(
                f"Unknown action '{action}'. Available: {available}"
            )

        creds = self._get_credentials(spec.app)
        return await self._executor.execute(spec, params, creds, user_id)

    # ── LangChain Tools ──────────────────────────────────────────────

    def get_tools(
        self,
        app: str,
        user_id: str,
        actions: Optional[List[str]] = None,
    ) -> list:
        """Get LangChain StructuredTools for an app.

        Returns tools ready for `llm.bind_tools(tools)`.

        Args:
            app: App slug (e.g. "google")
            user_id: User/workspace ID for token lookup
            actions: Optional list of specific action names to include.
                     If None, returns all actions for the app.
        """
        from anyapi.tools.langchain import build_tools

        specs = _APP_SPECS.get(app, [])
        if actions:
            specs = [s for s in specs if s.name in actions]

        if not specs:
            logger.warning(f"[anyapi] No specs found for app={app} actions={actions}")
            return []

        creds = self._get_credentials(app)
        return build_tools(self._executor, specs, creds, user_id)

    def get_all_tools(self, user_id: str) -> list:
        """Get LangChain tools for ALL registered apps."""
        all_tools = []
        for app in self._credentials:
            tools = self.get_tools(app, user_id)
            all_tools.extend(tools)
        return all_tools

    # ── Available Actions ────────────────────────────────────────────

    @staticmethod
    def list_actions(app: Optional[str] = None) -> List[Dict[str, str]]:
        """List available actions (for documentation/discovery).

        Returns:
            [{"name": "gmail_send_email", "app": "google", "description": "Send an email..."}]
        """
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

    def _get_credentials(self, app: str) -> AppCredentials:
        if app not in self._credentials:
            raise ValueError(
                f"App '{app}' not registered. Call api.register_app() first. "
                f"Registered: {list(self._credentials.keys())}"
            )
        return self._credentials[app]

    async def close(self):
        """Close HTTP clients."""
        await self._oauth.close()
        await self._executor.close()
