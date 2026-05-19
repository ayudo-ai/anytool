"""
Nango integration — handles OAuth and proxied API requests.

Nango manages:
- OAuth flows for 700+ providers
- Token storage and encryption
- Auto-refresh
- Proxy requests with auto-injected auth

We just need:
- Secret Key (from Nango dashboard)
- Provider Config Key (e.g. "google" — configured in Nango)
- Connection ID (= user_id / workspace_id in Ayudo)

API Reference:
  Proxy: POST https://api.nango.dev/proxy/{endpoint}
  Token: GET  https://api.nango.dev/connection/{connectionId}
  Auth:  POST https://api.nango.dev/auth/session
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from loguru import logger


class NangoClient:
    """Nango REST API client for Python.

    Usage:
        nango = NangoClient(secret_key="nango-secret-xxx")

        # Start OAuth flow
        url = await nango.get_connect_url(
            provider="google",
            connection_id="workspace-123",
            callback_url="http://localhost:8000/oauth/callback",
        )

        # Make authenticated API calls (Nango injects tokens)
        result = await nango.proxy(
            method="POST",
            provider="google",
            connection_id="workspace-123",
            endpoint="/gmail/v1/users/me/messages/send",
            data={"raw": "base64..."},
        )

        # Get connection info
        conn = await nango.get_connection("google", "workspace-123")
    """

    BASE_URL = "https://api.nango.dev"

    def __init__(self, secret_key: str, base_url: str = ""):
        self._secret_key = secret_key
        self._base_url = base_url or self.BASE_URL
        self._http = httpx.AsyncClient(timeout=30.0)

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Content-Type": "application/json",
        }

    # ── OAuth Flow ───────────────────────────────────────────────────

    async def create_connect_session(
        self,
        provider: str,
        connection_id: str,
        callback_url: str = "",
    ) -> Dict[str, Any]:
        """Create a session token for Nango's Connect UI.

        Returns a session token that you pass to Nango's frontend ConnectUI,
        or use to build a direct OAuth URL.

        For server-side OAuth (no frontend), use get_auth_url() instead.
        """
        body: Dict[str, Any] = {
            "end_user": {
                "id": connection_id,
            },
            "allowed_integrations": [provider],
        }

        resp = await self._http.post(
            f"{self._base_url}/connect/sessions",
            headers=self._headers,
            json=body,
        )

        if not resp.is_success:
            logger.error(f"[nango] Create session failed: {resp.status_code} {resp.text[:300]}")
            raise ValueError(f"Nango session creation failed: {resp.text[:300]}")

        data = resp.json()
        logger.info(f"[nango] Connect session created | provider={provider} connection={connection_id}")
        return data

    async def get_auth_url(
        self,
        provider: str,
        connection_id: str,
        callback_url: str = "",
    ) -> str:
        """Get a direct OAuth URL for server-side flows.

        Starts the OAuth flow and returns the redirect URL.
        """
        params: Dict[str, str] = {
            "connection_id": connection_id,
        }
        if callback_url:
            params["redirect_uri"] = callback_url

        resp = await self._http.get(
            f"{self._base_url}/auth/{provider}",
            headers=self._headers,
            params=params,
            follow_redirects=False,
        )

        # Nango returns a 302 redirect to the OAuth provider
        if resp.status_code in (302, 301):
            url = resp.headers.get("location", "")
            logger.info(f"[nango] Auth URL generated | provider={provider} connection={connection_id}")
            return url

        # Or it might return JSON with the URL
        if resp.is_success:
            data = resp.json()
            return data.get("url", data.get("auth_url", ""))

        logger.error(f"[nango] Auth URL failed: {resp.status_code} {resp.text[:300]}")
        raise ValueError(f"Nango auth failed: {resp.text[:300]}")

    # ── Connection Management ────────────────────────────────────────

    async def get_connection(
        self,
        provider: str,
        connection_id: str,
    ) -> Dict[str, Any]:
        """Get connection details including credentials.

        Returns the connection object with access_token, refresh_token, etc.
        """
        resp = await self._http.get(
            f"{self._base_url}/connection/{connection_id}",
            headers=self._headers,
            params={"provider_config_key": provider},
        )

        if not resp.is_success:
            if resp.status_code == 404:
                return {}
            logger.error(f"[nango] Get connection failed: {resp.status_code}")
            return {}

        return resp.json()

    async def list_connections(
        self,
        connection_id: Optional[str] = None,
    ) -> list:
        """List all connections, optionally filtered by connection_id."""
        params = {}
        if connection_id:
            params["connectionId"] = connection_id

        resp = await self._http.get(
            f"{self._base_url}/connection",
            headers=self._headers,
            params=params,
        )

        if not resp.is_success:
            return []

        data = resp.json()
        return data.get("connections", data if isinstance(data, list) else [])

    async def delete_connection(
        self,
        provider: str,
        connection_id: str,
    ) -> bool:
        """Delete a connection (disconnect an app)."""
        resp = await self._http.delete(
            f"{self._base_url}/connection/{connection_id}",
            headers=self._headers,
            params={"provider_config_key": provider},
        )

        if resp.is_success:
            logger.info(f"[nango] Disconnected | provider={provider} connection={connection_id}")
            return True

        logger.error(f"[nango] Delete failed: {resp.status_code}")
        return False

    # ── Proxy (the core feature) ─────────────────────────────────────

    async def proxy(
        self,
        method: str,
        provider: str,
        connection_id: str,
        endpoint: str,
        base_url: str = "",
        data: Any = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated API request through Nango's proxy.

        Nango automatically:
        - Injects the OAuth token
        - Refreshes if expired
        - Handles rate limiting
        - Retries on transient failures

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            provider: Provider config key (e.g. "google")
            connection_id: The user's connection ID
            endpoint: API endpoint path (e.g. "/gmail/v1/users/me/messages/send")
            base_url: Override base URL (optional)
            data: Request body (dict or string)
            params: Query parameters
            headers: Extra headers
        """
        proxy_headers = {
            **self._headers,
            "Provider-Config-Key": provider,
            "Connection-Id": connection_id,
        }
        if base_url:
            proxy_headers["Base-Url"] = base_url
        if headers:
            proxy_headers.update(headers)

        url = f"{self._base_url}/proxy{endpoint}"

        try:
            resp = await self._http.request(
                method=method,
                url=url,
                headers=proxy_headers,
                json=data if isinstance(data, dict) else None,
                content=data if isinstance(data, (str, bytes)) else None,
                params=params,
            )
        except httpx.TimeoutException:
            return {"error": f"Timeout: {method} {endpoint}", "status_code": 0, "successful": False}

        try:
            response_data = resp.json()
        except Exception:
            response_data = {"raw_text": resp.text[:2000]}

        result = {
            "data": response_data,
            "status_code": resp.status_code,
            "successful": resp.is_success,
        }

        if not resp.is_success:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:500]}"
            logger.warning(f"[nango.proxy] {resp.status_code} | {method} {endpoint} | {resp.text[:200]}")
        else:
            logger.info(f"[nango.proxy] {resp.status_code} | {method} {endpoint}")

        return result

    async def close(self):
        await self._http.aclose()
