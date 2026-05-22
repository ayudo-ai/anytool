"""
Spec models — internal representation of a YAML spec file.

These are loaded from registry/*.yaml by the loader.
They're immutable data objects, not ORM models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class AuthSpec:
    """Auth requirements for an API action."""
    type: str = "oauth2"                          # oauth2, api_key, bearer
    scopes: tuple[str, ...] = ()
    header: str = "Authorization: Bearer {access_token}"
    inject_from_metadata: Dict[str, str] = field(default_factory=dict)
    # e.g. {"account_id": "account_id"} → injects token metadata into path


@dataclass(frozen=True)
class RequestSpec:
    """Request specification."""
    content_type: str = "application/json"
    body_schema: Dict[str, Any] = field(default_factory=dict)  # Full JSON Schema
    note: str = ""


@dataclass(frozen=True)
class ResponseSpec:
    """Response specification."""
    success_codes: tuple[int, ...] = (200,)
    success_condition: str = ""                    # e.g. "data.ok == true"
    body_schema: Dict[str, Any] = field(default_factory=dict)
    extract: Dict[str, str] = field(default_factory=dict)  # friendly_name → json_path


@dataclass(frozen=True)
class RateLimitSpec:
    """Rate limit info."""
    requests_per_minute: int = 0
    requests_per_second: int = 0
    requests_per_hour: int = 0
    daily_limit: int = 0
    burst: int = 0
    note: str = ""


@dataclass(frozen=True)
class Example:
    """A request/response example."""
    name: str
    description: str = ""
    request: Dict[str, Any] = field(default_factory=dict)    # For Tier 1/2
    agent_input: Dict[str, Any] = field(default_factory=dict)  # For Tier 3
    actual_request: Dict[str, Any] = field(default_factory=dict)  # What goes on wire
    response: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionSpec:
    """Complete specification for a single API action.

    Loaded from a YAML file in the registry.
    This is the single source of truth for what the API expects.
    """

    # Identity
    name: str                       # "docusign_create_envelope"
    app: str                        # "docusign"
    version: str = ""               # "2.1"
    description: str = ""

    # HTTP
    method: str = "GET"             # GET, POST, PUT, PATCH, DELETE
    path: str = ""                  # "/restapi/v2.1/accounts/{account_id}/envelopes"
    base_url: str = ""              # "https://demo.docusign.net"

    # Auth
    auth: AuthSpec = field(default_factory=AuthSpec)

    # Request
    request: RequestSpec = field(default_factory=RequestSpec)
    encoder: str = ""               # Encoder name for Tier 3 (e.g. "gmail_mime")
    agent_params: Dict[str, Any] = field(default_factory=dict)  # LLM-facing params for Tier 3

    # Response
    response: ResponseSpec = field(default_factory=ResponseSpec)

    # Metadata
    errors: Dict[str, str] = field(default_factory=dict)
    rate_limit: RateLimitSpec = field(default_factory=RateLimitSpec)
    tags: tuple[str, ...] = ()
    examples: tuple[Example, ...] = ()

    # Encoder spec (documentation for the encoder logic)
    encoder_spec: Dict[str, Any] = field(default_factory=dict)

    @property
    def tier(self) -> int:
        """1 = flat pass-through, 2 = nested pass-through, 3 = needs encoder."""
        if self.encoder:
            return 3
        return 2 if self._nesting_depth > 2 else 1

    @property
    def _nesting_depth(self) -> int:
        """Max nesting depth of the body schema."""
        return _schema_depth(self.request.body_schema)

    @property
    def llm_schema(self) -> Dict[str, Any]:
        """The schema the LLM should use to construct the payload.

        For Tier 1/2: request.body_schema
        For Tier 3: agent_params
        """
        if self.encoder and self.agent_params:
            return self.agent_params
        return self.request.body_schema

    @property
    def required_fields(self) -> List[str]:
        """Required fields from the LLM-facing schema."""
        return self.llm_schema.get("required", [])

    @property
    def has_metadata_injection(self) -> bool:
        """Whether this spec needs values injected from auth metadata."""
        return bool(self.auth.inject_from_metadata)


def _schema_depth(schema: Dict[str, Any], depth: int = 0) -> int:
    """Calculate max nesting depth of a JSON Schema."""
    if not isinstance(schema, dict):
        return depth
    props = schema.get("properties", {})
    items = schema.get("items", {})
    depths = [depth]
    for v in props.values():
        depths.append(_schema_depth(v, depth + 1))
    if items:
        depths.append(_schema_depth(items, depth + 1))
    return max(depths)
