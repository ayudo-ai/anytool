"""
API Executor — constructs and sends HTTP requests from action specs.

This is the core of anyapi. Given an action spec + params + tokens,
it builds the exact HTTP request, sends it, and normalizes the response.

No wrappers. No Composio. Just HTTP.
"""

from __future__ import annotations

import base64
import json
from email.mime.text import MIMEText
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from loguru import logger

from anyapi.apps.registry import get_app_config
from anyapi.auth.models import AppCredentials, UserTokens
from anyapi.auth.oauth import OAuthManager
from anyapi.specs.base import ActionSpec


class APIExecutor:
    """Executes API actions with automatic auth injection."""

    def __init__(self, oauth_manager: OAuthManager):
        self._oauth = oauth_manager
        self._http = httpx.AsyncClient(timeout=30.0)

    async def execute(
        self,
        spec: ActionSpec,
        params: Dict[str, Any],
        credentials: AppCredentials,
        user_id: str,
    ) -> Dict[str, Any]:
        """Execute an API action.

        1. Get valid tokens (auto-refresh if expired)
        2. Build the HTTP request from spec + params
        3. Send it
        4. Normalize the response

        Returns:
            {
                "data": { ... response body ... },
                "status_code": 200,
                "successful": True,
                "extracted_ids": {"thread_id": "xxx", "message_id": "yyy"}
            }
        """
        # 1. Get tokens
        tokens = await self._oauth.get_valid_tokens(credentials, user_id)

        # 2. Build request
        url, headers, body, query = self._build_request(spec, params, tokens)

        logger.info(
            f"[anyapi.executor] {spec.method} {url} | "
            f"action={spec.name} user={user_id}"
        )

        # 3. Send
        try:
            resp = await self._http.request(
                method=spec.method,
                url=url,
                headers=headers,
                content=body if isinstance(body, (str, bytes)) else None,
                json=body if isinstance(body, dict) else None,
                params=query or None,
            )
        except httpx.TimeoutException:
            logger.error(f"[anyapi.executor] Timeout | action={spec.name}")
            return {
                "data": None,
                "status_code": 0,
                "successful": False,
                "error": f"Timeout calling {spec.name}",
            }

        # 4. Parse response
        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text[:2000]}

        # 5. Extract IDs from response
        extracted_ids = {}
        if spec.response_ids and isinstance(data, dict):
            for api_field, fact_name in spec.response_ids.items():
                value = data.get(api_field)
                if value:
                    extracted_ids[fact_name] = str(value)

        result = {
            "data": data,
            "status_code": resp.status_code,
            "successful": resp.is_success,
            "extracted_ids": extracted_ids,
        }

        if not resp.is_success:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:500]}"
            logger.warning(
                f"[anyapi.executor] {resp.status_code} | action={spec.name} | "
                f"{resp.text[:200]}"
            )

        logger.info(
            f"[anyapi.executor] {resp.status_code} | action={spec.name} | "
            f"ids={extracted_ids or 'none'}"
        )

        return result

    def _build_request(
        self,
        spec: ActionSpec,
        params: Dict[str, Any],
        tokens: UserTokens,
    ) -> tuple[str, dict, Any, dict]:
        """Build URL, headers, body, and query params from spec + params."""
        app_config = get_app_config(spec.app)

        # Base URL
        base_url = spec.base_url or app_config.api_base_url

        # Build path (substitute {placeholders})
        path = spec.path
        for param in spec.path_params:
            value = params.get(param.name, "")
            path = path.replace(f"{{{param.name}}}", str(value))

        url = f"{base_url.rstrip('/')}{path}"

        # Headers
        headers = {
            "Authorization": tokens.auth_header,
        }
        if spec.content_type:
            headers["Content-Type"] = spec.content_type

        # Query params
        query = {}
        for param in spec.query_params:
            value = params.get(param.name)
            if value is not None:
                query[param.name] = value

        # Body
        body = self._build_body(spec, params)

        return url, headers, body, query

    def _build_body(
        self,
        spec: ActionSpec,
        params: Dict[str, Any],
    ) -> Any:
        """Build the request body from spec + params."""
        if spec.method == "GET":
            return None

        # Special transforms
        if spec.request_transform == "gmail_mime":
            return self._build_gmail_mime(params)

        # Template-based body
        if spec.body_template:
            body = {}
            for key, template in spec.body_template.items():
                if isinstance(template, str) and template.startswith("{") and template.endswith("}"):
                    param_name = template[1:-1]
                    body[key] = params.get(param_name)
                else:
                    body[key] = template
            return body

        # Default: collect all body params into a dict
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

    async def close(self):
        await self._http.aclose()
