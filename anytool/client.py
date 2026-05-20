"""
AnyTool client — the single entry point.

Three modes:
  1. Platform mode (recommended for production):
     api = AnyTool(api_key="at_xxxx")
     # Calls anytool platform API. Auth configs managed in dashboard.

  2. Standalone mode (self-hosted):
     api = AnyTool(token_store=MemoryTokenStore())
     api.register_app(AppCredentials(app="google", ...))

  3. Nango mode (legacy):
     api = AnyTool(nango_secret_key="nango-xxx")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from anytool.specs.base import ActionSpec

# Import all spec modules
from anytool.specs.google import GOOGLE_SPECS
from anytool.specs.docusign import DOCUSIGN_SPECS
from anytool.specs.freshdesk import FRESHDESK_SPECS
from anytool.specs.slack import SLACK_SPECS
from anytool.specs.hubspot import HUBSPOT_SPECS
from anytool.specs.github import GITHUB_SPECS
from anytool.specs.zendesk import ZENDESK_SPECS
from anytool.specs.whatsapp import WHATSAPP_SPECS

# Spec registry
_ALL_SPECS: Dict[str, ActionSpec] = {}
_APP_SPECS: Dict[str, List[ActionSpec]] = {}

for spec in GOOGLE_SPECS + DOCUSIGN_SPECS + FRESHDESK_SPECS + SLACK_SPECS + HUBSPOT_SPECS + GITHUB_SPECS + ZENDESK_SPECS + WHATSAPP_SPECS:
    _ALL_SPECS[spec.name] = spec
    _APP_SPECS.setdefault(spec.app, []).append(spec)


# Provider → Nango provider config key mapping.
_NANGO_PROVIDERS: Dict[str, str] = {
    "google": "google",
    "freshdesk": "freshdesk",
    "docusign": "docusign-sandbox",
    "slack": "slack",
    "microsoft": "microsoft",
    "github": "github",
    "hubspot": "hubspot",
    "zendesk": "zendesk",
    "whatsapp": "whatsapp",
}


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


class AnyTool:
    """Main client for anytool.

    Three modes:
      1. Platform mode:   AnyTool(api_key="at_xxxx")
      2. Standalone mode: AnyTool(token_store=...)
      3. Nango mode:      AnyTool(nango_secret_key="...")
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "http://localhost:8000/v1",
        nango_secret_key: str = "",
        nango_base_url: str = "",
        token_store=None,
    ):
        """
        Args:
            api_key: Platform API key (at_xxxx) — recommended for production
            base_url: Platform API URL (default: http://localhost:8100/v1)
            nango_secret_key: Nango Secret Key (legacy)
            nango_base_url: Override Nango API URL
            token_store: TokenStore instance (standalone mode)
        """
        self._nango = None
        self._oauth = None
        self._executor = None
        self._credentials = {}
        self._platform: Optional[_PlatformClient] = None
        self._mode = "unknown"

        if api_key:
            # Platform mode — all calls go through the anytool platform API
            self._platform = _PlatformClient(api_key, base_url)
            self._mode = "platform"
            logger.info("[anytool] Initialized in platform mode")
        elif nango_secret_key:
            # Nango mode
            from anytool.auth.nango import NangoClient
            self._nango = NangoClient(
                secret_key=nango_secret_key,
                base_url=nango_base_url,
            )
            from anytool.executor import APIExecutor
            self._executor = APIExecutor(nango=self._nango)
            self._mode = "nango"
            logger.info("[anytool] Initialized in Nango mode")
        elif token_store:
            # Standalone mode
            from anytool.auth.oauth import OAuthManager
            from anytool.executor import APIExecutor
            self._oauth = OAuthManager(token_store)
            self._executor = APIExecutor(oauth_manager=self._oauth)
            self._store = token_store
            self._mode = "standalone"
            logger.info("[anytool] Initialized in standalone mode")
        else:
            raise ValueError(
                "Provide one of: api_key (platform mode), "
                "token_store (standalone mode), or nango_secret_key (legacy)"
            )

    # ── Nango Auth ───────────────────────────────────────────────────

    async def get_connect_session(
        self,
        provider: str,
        connection_id: str,
    ) -> Dict[str, Any]:
        """Create a Nango Connect session (for frontend ConnectUI)."""
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
        account_id: str = "",
        workspace_id: str = "",
    ) -> str:
        """Get OAuth authorization URL for a user to connect an app.

        Platform mode: Calls POST /v1/connections
        Standalone mode: Uses our own OAuth manager
        """
        if self._platform:
            result = await self._platform.post("/connections", json={
                "provider": provider,
                "user_id": connection_id,
            })
            return result["auth_url"]
        elif self._nango:
            return await self._nango.get_auth_url(
                provider=_NANGO_PROVIDERS.get(provider, provider),
                connection_id=connection_id,
                callback_url=callback_url,
            )
        else:
            creds = self._get_credentials(provider)
            return await self._oauth.get_auth_url(
                creds, connection_id, extra_scopes,
                account_id=account_id, workspace_id=workspace_id,
            )

    # ── Standalone Auth ──────────────────────────────────────────────

    def set_provider_mapping(self, app: str, nango_key: str) -> None:
        """Override the Nango provider config key for an app."""
        _NANGO_PROVIDERS[app] = nango_key

    def register_app(self, credentials) -> None:
        """Register OAuth credentials (standalone mode only)."""
        self._credentials[credentials.app] = credentials
        logger.info(f"[anytool] Registered app: {credentials.app}")

    async def handle_callback(self, app: str, code: str, state: str):
        """Handle OAuth callback (standalone mode only)."""
        if self._platform:
            raise ValueError("In platform mode, the platform handles callbacks automatically")
        if self._nango:
            raise ValueError("In Nango mode, Nango handles callbacks automatically")

        if not app:
            oauth_state = await self._store.get_oauth_state(state)
            if not oauth_state:
                raise ValueError("Invalid or expired OAuth state")
            app = oauth_state.app
            await self._store.save_oauth_state(oauth_state)

        creds = self._get_credentials(app)
        return await self._oauth.handle_callback(creds, code, state)

    # ── Connection Management ────────────────────────────────────────

    async def is_connected(self, provider: str, connection_id: str) -> bool:
        """Check if a user has connected an app."""
        if self._platform:
            result = await self._platform.get("/connections/check", params={
                "provider": provider,
                "user_id": connection_id,
            })
            return result.get("connected", False)
        elif self._nango:
            conn = await self._nango.get_connection(
                _NANGO_PROVIDERS.get(provider, provider), connection_id
            )
            return bool(conn)
        else:
            tokens = await self._store.get_tokens(provider, connection_id)
            return tokens is not None

    async def list_connections(self, connection_id: str = "") -> list:
        """List connected apps, optionally filtered by user."""
        if self._platform:
            params = {"user_id": connection_id} if connection_id else {}
            result = await self._platform.get("/connections", params=params)
            return result.get("connections", [])
        elif self._nango:
            return await self._nango.list_connections(connection_id)
        else:
            return await self._store.list_connected(connection_id)

    async def disconnect(self, provider: str, connection_id: str) -> None:
        """Disconnect an app for a user."""
        if self._platform:
            await self._platform.delete(f"/connections?provider={provider}&user_id={connection_id}")
        elif self._nango:
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

        Platform mode: POST /v1/execute
        Standalone mode: Direct HTTP with managed tokens

        Example:
            result = await api.call(
                "gmail_send_email",
                connection_id="customer-123",
                to="vendor@example.com",
                subject="Follow-up",
                body="Hello",
            )
        """
        if self._platform:
            return await self._platform.post("/execute", json={
                "action": action,
                "user_id": connection_id,
                "params": params,
            })

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

    # ── Triggers ─────────────────────────────────────────────────────

    async def deploy_trigger(
        self,
        trigger_type: str,
        connection_id: str,
        webhook_url: str,
        filters: Dict[str, Any] = None,
        poll_interval_seconds: int = 90,
    ) -> Dict[str, Any]:
        """Deploy a trigger that polls for events and delivers to a webhook.

        Platform mode only.

        Example:
            trigger = await api.deploy_trigger(
                trigger_type="gmail_new_message",
                connection_id="customer-123",
                webhook_url="https://myapp.com/webhooks/inbox",
                filters={"from_contains": "vendor@example.com"},
            )
        """
        if self._platform:
            return await self._platform.post("/triggers", json={
                "trigger_type": trigger_type,
                "user_id": connection_id,
                "webhook_url": webhook_url,
                "filters": filters or {},
                "poll_interval_seconds": poll_interval_seconds,
            })
        raise ValueError("Triggers require platform mode. Use AnyTool(api_key='at_xxxx')")

    async def list_triggers(self, connection_id: str = "") -> List[Dict[str, Any]]:
        """List active triggers."""
        if self._platform:
            params = {"user_id": connection_id} if connection_id else {}
            result = await self._platform.get("/triggers", params=params)
            return result.get("triggers", [])
        raise ValueError("Triggers require platform mode")

    async def remove_trigger(self, trigger_id: str) -> Dict[str, Any]:
        """Remove a trigger."""
        if self._platform:
            return await self._platform.delete(f"/triggers/{trigger_id}")
        raise ValueError("Triggers require platform mode")

    # ── LangChain Tools ──────────────────────────────────────────────

    def get_tools(
        self,
        app: str,
        connection_id: str,
        actions: Optional[List[str]] = None,
    ) -> list:
        """Get LangChain StructuredTools for an app.

        Works in all modes. In platform mode, each tool call goes through
        the platform API (POST /v1/execute), which logs usage and
        applies rate limits.

        Returns tools ready for llm.bind_tools(tools).
        """
        from anytool.tools.langchain import build_tools

        specs = _APP_SPECS.get(app, [])
        if actions:
            specs = [s for s in specs if s.name in actions]

        if not specs:
            logger.warning(f"[anytool] No specs for app={app} actions={actions}")
            return []

        if self._platform:
            # Platform mode — build tools that call through the platform API
            return build_tools(
                executor=None,
                specs=specs,
                provider=app,
                connection_id=connection_id,
                platform_client=self._platform,
            )

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
    def list_actions(app: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available actions with full param info."""
        specs = _APP_SPECS.get(app, []) if app else list(_ALL_SPECS.values())
        return [
            {
                "name": s.name,
                "app": s.app,
                "description": s.description,
                "method": s.method,
                "params": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                        "description": p.description,
                        "location": p.location,
                        **({
                            "enum": p.enum
                        } if p.enum else {}),
                        **({
                            "default": p.default
                        } if p.default is not None else {}),
                    }
                    for p in s.params
                ],
            }
            for s in specs
        ]

    async def get_tools_schema(self, app: str) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible tool definitions from platform.

        Platform mode: calls GET /v1/tools?app=xxx
        Standalone: builds from local specs
        """
        if self._platform:
            result = await self._platform.get("/tools", params={"app": app})
            return result.get("tools", [])
        # Standalone — build from local specs
        actions = self.list_actions(app)
        tools = []
        for action in actions:
            params = action.get("params", [])
            properties = {}
            required = []
            for p in params:
                prop: Dict[str, Any] = {
                    "type": p.get("type", "string"),
                    "description": p.get("description", ""),
                }
                if p.get("enum"):
                    prop["enum"] = p["enum"]
                properties[p["name"]] = prop
                if p.get("required"):
                    required.append(p["name"])
            tools.append({
                "type": "function",
                "function": {
                    "name": action["name"],
                    "description": action["description"],
                    "parameters": {
                        "type": "object",
                        "required": required,
                        "properties": properties,
                    },
                },
            })
        return tools

    # ── Internal ─────────────────────────────────────────────────────

    def _get_credentials(self, app):
        if app not in self._credentials:
            raise ValueError(f"App '{app}' not registered. Registered: {list(self._credentials.keys())}")
        return self._credentials[app]

    async def close(self):
        if self._platform:
            await self._platform.close()
        if self._nango:
            await self._nango.close()
        if self._oauth:
            await self._oauth.close()
