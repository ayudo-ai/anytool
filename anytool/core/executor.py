"""
Generic Executor — spec + body + auth → HTTP request → response.

Rules:
1. The body from the LLM is sent AS-IS to the API. No transforms.
2. Path params are substituted from the body or from auth metadata.
3. Query params are extracted from the body based on the spec schema.
4. If the spec declares an encoder, run it. Otherwise, send raw JSON.
5. Auth headers are injected automatically.
6. Retry on transient failures (429, 5xx) with exponential backoff.

    from anytool.core.executor import Executor

    executor = Executor()
    result = await executor.execute(spec, body, auth_tokens)
"""

from __future__ import annotations

import re
import time
import asyncio
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger

from anytool.core.models import ActionSpec, AuthSpec
from anytool.core.encoders import encode


# ── Result ───────────────────────────────────────────────────────────

class ExecutionResult:
    """Result of executing an API action."""

    __slots__ = ("data", "status_code", "successful", "error", "extracted_ids", "duration_ms")

    def __init__(
        self,
        data: Any = None,
        status_code: int = 0,
        successful: bool = False,
        error: str = "",
        extracted_ids: Optional[Dict[str, str]] = None,
        duration_ms: int = 0,
    ):
        self.data = data
        self.status_code = status_code
        self.successful = successful
        self.error = error
        self.extracted_ids = extracted_ids or {}
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data,
            "status_code": self.status_code,
            "successful": self.successful,
            "error": self.error,
            "extracted_ids": self.extracted_ids,
            "duration_ms": self.duration_ms,
        }


# ── Auth Tokens ──────────────────────────────────────────────────────

class AuthTokens:
    """Token container passed to the executor.

    The executor doesn't manage tokens — it receives them ready to use.
    Token refresh, storage, encryption are handled by the auth layer.
    """

    def __init__(
        self,
        access_token: str = "",
        token_type: str = "Bearer",
        api_key: str = "",
        domain: str = "",
        metadata: Optional[Dict[str, str]] = None,
    ):
        self.access_token = access_token
        self.token_type = token_type
        self.api_key = api_key
        self.domain = domain
        self.metadata = metadata or {}

    @property
    def auth_header(self) -> str:
        """Build the Authorization header value."""
        if self.api_key:
            import base64
            encoded = base64.b64encode(f"{self.api_key}:X".encode()).decode()
            return f"Basic {encoded}"
        return f"Bearer {self.access_token}"


# ── Executor ─────────────────────────────────────────────────────────

# Path placeholder pattern: {param_name}
_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")

# Retryable status codes
_RETRYABLE_CODES = {429, 500, 502, 503, 504}

# Default retry delays (seconds)
_RETRY_DELAYS = [1.0, 3.0, 10.0]


class Executor:
    """Generic API executor. Spec + body + auth → HTTP → result.

    Zero custom logic per API. The spec drives everything.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self._timeout = timeout
        self._max_retries = max_retries

    async def execute(
        self,
        spec: ActionSpec,
        body: Dict[str, Any],
        auth: AuthTokens,
    ) -> ExecutionResult:
        """Execute an API action.

        Args:
            spec: The action spec (loaded from YAML).
            body: The request body as constructed by the LLM.
                  For Tier 1/2: the exact JSON to send.
                  For Tier 3: the agent_params (encoder transforms them).
            auth: Auth tokens for the request.

        Returns:
            ExecutionResult with data, status, extracted IDs.
        """
        start = time.monotonic()

        try:
            # 1. Apply encoder if this is a Tier 3 action
            request_body = body
            if spec.encoder:
                request_body = encode(spec.encoder, body)
                logger.debug(f"[executor] Encoded with {spec.encoder}")

            # 1b. Apply schema defaults + coerce types BEFORE URL building
            # so path params with defaults (e.g. calendarId='primary') are available
            request_body = self._coerce_types(spec, request_body)

            # 2. Build the URL (consumes path params from body)
            url, remaining_body = self._build_url(spec, request_body, auth)

            # 3. Separate query params from body
            query_params, final_body = self._split_query_params(spec, remaining_body)

            # 4. Build headers
            headers = self._build_headers(spec, auth)

            logger.debug(f"[executor] {spec.method} {url} | auth_domain={auth.domain} | body_keys={list(final_body.keys()) if final_body else 'none'}")

            # 5. Execute with retries
            result = await self._execute_with_retries(
                method=spec.method,
                url=url,
                headers=headers,
                body=final_body if spec.method not in ("GET", "DELETE") else None,
                query=query_params or None,
            )

            # 6. Extract IDs from response
            result.extracted_ids = self._extract_ids(spec, result.data)

        except Exception as e:
            result = ExecutionResult(
                successful=False,
                error=f"Execution error: {e}",
            )

        result.duration_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            f"[executor] {spec.method} {spec.name} | "
            f"status={result.status_code} | "
            f"{result.duration_ms}ms | "
            f"ids={result.extracted_ids or 'none'}"
        )

        return result

    def _build_url(
        self,
        spec: ActionSpec,
        body: Dict[str, Any],
        auth: AuthTokens,
    ) -> Tuple[str, Dict[str, Any]]:
        """Build the full URL, substituting path parameters.

        Path params come from:
        1. auth.inject_from_metadata (e.g., DocuSign account_id)
        2. The request body (consumed — removed from body)

        Returns (url, remaining_body_without_path_params).
        """
        path = spec.path
        remaining = dict(body)  # shallow copy

        # Find all {placeholder} names in the path
        placeholders = set(_PATH_PARAM_RE.findall(path))

        for placeholder in placeholders:
            value = None

            # First: check metadata injection
            if placeholder in spec.auth.inject_from_metadata:
                meta_key = spec.auth.inject_from_metadata[placeholder]
                value = auth.metadata.get(meta_key, "")

            # Second: check the body
            if not value and placeholder in remaining:
                value = remaining.pop(placeholder)

            if value:
                path = path.replace(f"{{{placeholder}}}", str(value))
            else:
                logger.warning(
                    f"[executor] Path param '{placeholder}' not found "
                    f"in body or metadata for {spec.name}"
                )

        # Resolve dynamic base_url (e.g., {domain}.freshdesk.com)
        base_url = spec.base_url
        for placeholder in _PATH_PARAM_RE.findall(base_url):
            # Check auth.domain first (API key providers), then metadata
            if placeholder in ("domain", "subdomain") and auth.domain:
                value = auth.domain
            else:
                value = auth.metadata.get(placeholder, "")
            if value:
                # Prevent double-suffix: if base_url has "{domain}.freshdesk.com"
                # and value is already "ayudo.freshdesk.com", strip the suffix
                suffix_after = base_url.split(f"{{{placeholder}}}", 1)[-1].split("/")[0]
                if suffix_after and value.endswith(suffix_after):
                    value = value[: -len(suffix_after)]
                base_url = base_url.replace(f"{{{placeholder}}}", value)

        url = f"{base_url.rstrip('/')}{path}"
        return url, remaining

    def _split_query_params(
        self,
        spec: ActionSpec,
        body: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Separate query params from body params based on the spec schema.

        For GET/DELETE: everything becomes query params.
        For POST/PUT/PATCH: only fields explicitly in query_param_names go to query.

        We detect query params by checking if the spec's body_schema
        has top-level properties — anything NOT in those properties
        and present in the body goes to query.

        But a simpler rule: for most APIs, the body IS the body.
        Query params are rare in POST requests. We handle the common
        case of GET endpoints where everything is query.
        """
        if spec.method in ("GET", "DELETE"):
            # For GET/DELETE: everything goes as query params
            return body, {}

        # For POST/PUT/PATCH: body stays as body
        # Query params would need to be explicitly separated in the spec
        # For now, send everything as body (covers 99% of cases)
        return {}, body

    def _coerce_types(self, spec: ActionSpec, body: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce body values to match the schema types and apply defaults.

        The dashboard and some LLMs send everything as strings.
        Freshdesk/Zendesk need integers for status/priority, booleans, etc.
        Also fills in schema defaults for missing required fields.
        """
        if body is None:
            body = {}
        schema = spec.request.body_schema or {}
        props = schema.get("properties", {})
        if not props:
            return body

        coerced = {}

        # 1. Apply defaults for missing fields
        for field_name, field_schema in props.items():
            if field_name not in body and "default" in field_schema:
                coerced[field_name] = field_schema["default"]

        # 2. Coerce provided values
        for key, value in body.items():
            field_schema = props.get(key, {})
            field_type = field_schema.get("type", "")
            try:
                if field_type == "integer" and isinstance(value, str) and value.strip():
                    coerced[key] = int(value)
                elif field_type == "number" and isinstance(value, str) and value.strip():
                    coerced[key] = float(value)
                elif field_type == "boolean" and isinstance(value, str):
                    coerced[key] = value.lower() in ("true", "1", "yes")
                elif field_type == "array" and isinstance(value, str):
                    import json
                    try:
                        coerced[key] = json.loads(value)
                    except json.JSONDecodeError:
                        coerced[key] = [v.strip() for v in value.split(",") if v.strip()]
                elif field_type == "object" and isinstance(value, str):
                    import json
                    try:
                        coerced[key] = json.loads(value)
                    except json.JSONDecodeError:
                        coerced[key] = value
                else:
                    coerced[key] = value
            except (ValueError, TypeError):
                coerced[key] = value
        return coerced

    def _build_headers(self, spec: ActionSpec, auth: AuthTokens) -> Dict[str, str]:
        """Build request headers."""
        headers: Dict[str, str] = {
            "Authorization": auth.auth_header,
        }
        if spec.request.content_type and spec.method not in ("GET", "DELETE"):
            headers["Content-Type"] = spec.request.content_type
        return headers

    async def _execute_with_retries(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[Dict[str, Any]],
        query: Optional[Dict[str, Any]],
    ) -> ExecutionResult:
        """Execute HTTP request with retry on transient failures."""

        last_error = ""
        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=body,
                        params=query,
                    )
            except httpx.TimeoutException:
                last_error = f"Timeout: {method} {url}"
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(_RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)])
                    continue
                return ExecutionResult(successful=False, error=last_error)
            except httpx.ConnectError as e:
                last_error = f"Connection error: {e}"
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(_RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)])
                    continue
                return ExecutionResult(successful=False, error=last_error)

            # Parse response
            try:
                data = resp.json()
            except Exception:
                data = {"raw_text": resp.text[:5000]}

            # Success
            if resp.is_success:
                return ExecutionResult(
                    data=data,
                    status_code=resp.status_code,
                    successful=True,
                )

            # Retryable error
            if resp.status_code in _RETRYABLE_CODES and attempt < self._max_retries - 1:
                # Respect Retry-After header
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                else:
                    delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]

                logger.warning(
                    f"[executor] {resp.status_code} on {method} {url} | "
                    f"retry {attempt + 1}/{self._max_retries} in {delay}s"
                )
                await asyncio.sleep(delay)
                continue

            # Non-retryable error
            return ExecutionResult(
                data=data,
                status_code=resp.status_code,
                successful=False,
                error=f"HTTP {resp.status_code}: {resp.text[:500]}",
            )

        return ExecutionResult(
            successful=False,
            error=f"Exhausted {self._max_retries} retries. Last error: {last_error}",
        )

    def _extract_ids(self, spec: ActionSpec, data: Any) -> Dict[str, str]:
        """Extract key IDs from the response using spec.response.extract mapping.

        Supports dotted paths like 'ticket.id'.
        """
        if not spec.response.extract or not isinstance(data, dict):
            return {}

        extracted = {}
        for friendly_name, json_path in spec.response.extract.items():
            value = data
            for key in json_path.split("."):
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    value = None
                    break
            if value is not None:
                extracted[friendly_name] = str(value)

        return extracted
