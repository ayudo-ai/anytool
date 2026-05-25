"""
AnyTool client — auth and connection management.

Handles OAuth flows, token storage, and connection state.
Execution goes through anytool.core.engine.Engine (v2).

    from anytool import AnyTool, MemoryTokenStore, AppCredentials

    api = AnyTool(token_store=MemoryTokenStore())
    api.register_app(AppCredentials(app="google", ...))

    # OAuth
    auth_url = await api.get_auth_url("google", connection_id="user-123")
    tokens = await api.handle_callback("google", code="xxx", state="xxx")

    # Check connections
    connected = await api.is_connected("google", "user-123")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from anytool.auth.models import AppCredentials


class AnyTool:
    """Auth and connection manager.

    Three modes:
      1. Platform mode:    AnyTool(api_key="at_xxxx")
      2. Standalone mode:  AnyTool(token_store=MemoryTokenStore())
      3. Nango mode:       REMOVED — use standalone mode instead
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api-anytool.ayudo.ai/v1",
        token_store=None,
    ):
        self._oauth = None
        self._credentials: Dict[str, AppCredentials] = {}
        self._platform = None
        self._mode = "unknown"

        if api_key:
            self._platform = _PlatformClient(api_key, base_url)
            self._mode = "platform"
            logger.info("[anytool] Initialized in platform mode")
        elif token_store:
            from anytool.auth.oauth import OAuthManager
            self._oauth = OAuthManager(token_store)
            self._store = token_store
            self._mode = "standalone"
            logger.info("[anytool] Initialized in standalone mode")
        else:
            raise ValueError(
                "Provide one of: api_key (platform mode) or token_store (standalone mode)"
            )

    # ── App Registration ─────────────────────────────────────────────

    def register_app(self, credentials: AppCredentials) -> None:
        """Register OAuth credentials for an app."""
        self._credentials[credentials.app] = credentials
        logger.info(f"[anytool] Registered app: {credentials.app}")

    # ── OAuth Flows ──────────────────────────────────────────────────

    async def get_auth_url(
        self,
        provider: str,
        connection_id: str,
        callback_url: str = "",
        extra_scopes: Optional[List[str]] = None,
        account_id: str = "",
        workspace_id: str = "",
    ) -> str:
        """Generate OAuth authorization URL for a user to click."""
        if self._platform:
            result = await self._platform.post("/connections", json={
                "provider": provider,
                "user_id": connection_id,
            })
            return result["auth_url"]

        creds = self._get_credentials(provider)
        return await self._oauth.get_auth_url(
            creds, connection_id, extra_scopes,
            account_id=account_id, workspace_id=workspace_id,
        )

    async def handle_callback(self, app: str, code: str, state: str):
        """Handle OAuth callback — exchange code for tokens."""
        if self._platform:
            raise ValueError("In platform mode, the platform handles callbacks automatically")

        resolved_state = None
        if not app:
            resolved_state = await self._store.get_oauth_state(state)
            if not resolved_state:
                raise ValueError("Invalid or expired OAuth state")
            app = resolved_state.app
        creds = self._get_credentials(app)
        return await self._oauth.handle_callback(creds, code, state, oauth_state=resolved_state)

    # ── Connection Management ────────────────────────────────────────

    async def is_connected(self, provider: str, connection_id: str) -> bool:
        """Check if a user has connected an app."""
        if self._platform:
            result = await self._platform.get("/connections/check", params={
                "provider": provider, "user_id": connection_id,
            })
            return result.get("connected", False)

        tokens = await self._store.get_tokens(provider, connection_id)
        return tokens is not None

    async def list_connections(self, connection_id: str = "") -> list:
        """List connected apps for a user."""
        if self._platform:
            params = {"user_id": connection_id} if connection_id else {}
            result = await self._platform.get("/connections", params=params)
            return result.get("connections", [])

        return await self._store.list_connected(connection_id)

    async def disconnect(self, provider: str, connection_id: str) -> None:
        """Disconnect an app for a user."""
        if self._platform:
            await self._platform.delete(f"/connections?provider={provider}&user_id={connection_id}")
        else:
            await self._store.delete_tokens(provider, connection_id)

    # ── Action Execution ────────────────────────────────────────────

    async def call(
        self,
        action: str,
        connection_id: str,
        **params,
    ) -> dict:
        """Execute an action for a user. Used by pollers and triggers.

        Args:
            action: Action name (e.g. 'gmail_search', 'slack_list_channels')
            connection_id: User/connection ID for auth resolution
            **params: Action parameters

        Returns:
            Dict with 'successful', 'data', 'error' keys.
        """
        if self._platform:
            result = await self._platform.post("/execute", json={
                "action": action,
                "user_id": connection_id,
                "params": params,
            })
            return result

        # Standalone mode — use v2 engine directly
        from anytool.core.engine import Engine
        from anytool.core.auth_bridge import AuthBridge

        # Resolve auth tokens
        app_name = action.split("_")[0] if "_" in action else action
        # Map common prefixes to provider names
        app_map = {"gmail": "google", "drive": "google", "sheets": "google",
                   "calendar": "google", "docs": "google"}
        provider = app_map.get(app_name, app_name)

        try:
            bridge = AuthBridge(
                oauth_manager=self._oauth,
                credentials=self._credentials,
            )
            auth = await bridge.get_auth(provider, connection_id)

            # Get or create engine
            if not hasattr(self, '_engine'):
                self._engine = Engine()
            result = await self._engine.execute(action, params, auth)
            return {
                "successful": result.successful,
                "data": result.data,
                "error": result.error,
            }
        except Exception as e:
            logger.error(f"[anytool] call({action}) failed: {e}")
            return {"successful": False, "data": {}, "error": str(e)}

    # ── Internal ─────────────────────────────────────────────────────

    def _get_credentials(self, app: str) -> AppCredentials:
        if app not in self._credentials:
            raise ValueError(
                f"App '{app}' not registered. Registered: {list(self._credentials.keys())}"
            )
        return self._credentials[app]

    async def close(self):
        if self._platform:
            await self._platform.close()
        if self._oauth:
            await self._oauth.close()


class _PlatformClient:
    """HTTP client for the anytool platform API."""

    def __init__(self, api_key: str, base_url: str):
        import httpx
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def post(self, path: str, json: dict = None) -> dict:
        resp = await self._http.post(f"{self._base_url}{path}", json=json)
        if not resp.is_success:
            error_detail = resp.text[:500]
            try:
                error_detail = resp.json().get("detail", error_detail)
            except Exception:
                pass
            raise ValueError(f"Platform API error {resp.status_code}: {error_detail}")
        return resp.json()

    async def get(self, path: str, params: dict = None) -> dict:
        resp = await self._http.get(f"{self._base_url}{path}", params=params)
        if not resp.is_success:
            error_detail = resp.text[:500]
            try:
                error_detail = resp.json().get("detail", error_detail)
            except Exception:
                pass
            raise ValueError(f"Platform API error {resp.status_code}: {error_detail}")
        return resp.json()

    async def delete(self, path: str) -> dict:
        resp = await self._http.delete(f"{self._base_url}{path}")
        if not resp.is_success:
            raise ValueError(f"Platform API error {resp.status_code}: {resp.text[:500]}")
        return resp.json()

    async def close(self):
        await self._http.aclose()
