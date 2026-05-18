"""
API Executor — constructs and sends HTTP requests from action specs.

Two modes:
  1. Nango proxy mode (recommended): Nango handles auth, we build the request
  2. Direct mode (standalone): We manage tokens ourselves

Both use the same ActionSpecs. The only difference is how auth is injected.
"""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from loguru import logger

from anyapi.apps.registry import get_app_config
from anyapi.specs.base import ActionSpec


class APIExecutor:
    """Executes API actions. Supports Nango proxy or direct HTTP."""

    def __init__(self, nango=None, oauth_manager=None):
        """
        Args:
            nango: NangoClient instance (proxy mode — recommended)
            oauth_manager: OAuthManager instance (direct mode — standalone)
        """
        self._nango = nango
        self._oauth = oauth_manager

        if not nango and not oauth_manager:
            raise ValueError("Either nango or oauth_manager must be provided")

    async def execute(
        self,
        spec: ActionSpec,
        params: Dict[str, Any],
        provider: str,
        connection_id: str,
        credentials=None,  # Only needed for direct mode
    ) -> Dict[str, Any]:
        """Execute an API action.

        Returns:
            {
                "data": { ... response body ... },
                "status_code": 200,
                "successful": True,
                "extracted_ids": {"thread_id": "xxx", "message_id": "yyy"}
            }
        """
        app_config = get_app_config(spec.app)

        # Build URL parts
        base_url = spec.base_url or app_config.api_base_url
        path = spec.path
        for param in spec.path_params:
            value = params.get(param.name, "")
            path = path.replace(f"{{{param.name}}}", str(value))

        # Build query params
        query = {}
        for param in spec.query_params:
            value = params.get(param.name)
            if value is not None:
                query[param.name] = value

        # Build body
        body = self._build_body(spec, params)

        # Build extra headers
        headers = {}
        if spec.content_type:
            headers["Content-Type"] = spec.content_type

        logger.info(
            f"[anyapi.executor] {spec.method} {base_url}{path} | "
            f"action={spec.name} connection={connection_id}"
        )

        # Execute via Nango proxy or direct
        if self._nango:
            result = await self._nango.proxy(
                method=spec.method,
                provider=provider,
                connection_id=connection_id,
                endpoint=path,
                base_url=base_url,
                data=body,
                params=query or None,
                headers=headers or None,
            )
        else:
            # Direct mode — manage tokens ourselves
            result = await self._execute_direct(
                spec, path, base_url, headers, body, query, credentials, connection_id
            )

        # Extract IDs from response
        extracted_ids = {}
        data = result.get("data", {})
        if spec.response_ids and isinstance(data, dict):
            for api_field, fact_name in spec.response_ids.items():
                value = data.get(api_field)
                if value:
                    extracted_ids[fact_name] = str(value)

        result["extracted_ids"] = extracted_ids

        logger.info(
            f"[anyapi.executor] {result.get('status_code', '?')} | "
            f"action={spec.name} | ids={extracted_ids or 'none'}"
        )

        return result

    async def _execute_direct(
        self, spec, path, base_url, headers, body, query, credentials, user_id
    ):
        """Direct HTTP execution with self-managed tokens."""
        import httpx

        tokens = await self._oauth.get_valid_tokens(credentials, user_id)
        headers["Authorization"] = tokens.auth_header
        url = f"{base_url.rstrip('/')}{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.request(
                    method=spec.method,
                    url=url,
                    headers=headers,
                    json=body if isinstance(body, dict) else None,
                    content=body if isinstance(body, (str, bytes)) else None,
                    params=query or None,
                )
            except httpx.TimeoutException:
                return {"data": None, "status_code": 0, "successful": False,
                        "error": f"Timeout: {spec.method} {url}"}

        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text[:2000]}

        result = {"data": data, "status_code": resp.status_code, "successful": resp.is_success}
        if not resp.is_success:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:500]}"
        return result

    def _build_body(self, spec: ActionSpec, params: Dict[str, Any]) -> Any:
        """Build the request body from spec + params."""
        if spec.method == "GET":
            return None

        if spec.request_transform == "gmail_mime":
            return self._build_gmail_mime(params)

        if spec.body_template:
            body = {}
            for key, template in spec.body_template.items():
                if isinstance(template, str) and template.startswith("{") and template.endswith("}"):
                    param_name = template[1:-1]
                    body[key] = params.get(param_name)
                else:
                    body[key] = template
            return body

        body = {}
        for param in spec.body_params:
            value = params.get(param.name)
            if value is not None:
                body[param.name] = value

        return body if body else None

    def _build_gmail_mime(self, params: Dict[str, Any]) -> dict:
        """Build Gmail API send request with MIME encoding."""
        msg = MIMEText(params.get("body", ""))
        msg["to"] = params["to"]
        msg["subject"] = params.get("subject", "")

        if params.get("cc"):
            msg["cc"] = params["cc"]
        if params.get("bcc"):
            msg["bcc"] = params["bcc"]
        if params.get("in_reply_to"):
            msg["In-Reply-To"] = params["in_reply_to"]
            msg["References"] = params["in_reply_to"]

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

        body: Dict[str, Any] = {"raw": raw}
        if params.get("thread_id"):
            body["threadId"] = params["thread_id"]

        return body
