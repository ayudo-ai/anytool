"""
Base spec models — defines the structure of an API action spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParamSpec:
    """A single parameter for an API action."""

    name: str
    type: str = "string"  # string, integer, boolean, list, object
    required: bool = False
    description: str = ""
    location: str = "body"  # body, query, path, header
    default: Any = None
    enum: List[str] = field(default_factory=list)  # allowed values


@dataclass
class ActionSpec:
    """A single API action — one endpoint, one HTTP call.

    This is the agent-friendly description of what an API endpoint does,
    what parameters it needs, and how to parse the response.
    """

    name: str  # Tool name: "gmail_send_email"
    app: str  # App slug: "google"
    description: str  # For LLM tool description
    method: str  # HTTP method: GET, POST, PUT, DELETE, PATCH
    path: str  # URL path with {placeholders}: "/gmail/v1/users/me/messages/{id}"

    # Optional overrides
    base_url: str = ""  # Override app's default base URL
    content_type: str = ""  # Request content type
    params: List[ParamSpec] = field(default_factory=list)

    # Request construction helpers
    request_transform: str = ""  # Special transform: "gmail_mime", "base64", etc.
    body_template: Optional[Dict[str, Any]] = None  # Static body structure

    # Response parsing
    response_ids: Dict[str, str] = field(default_factory=dict)  # API field → fact name

    @property
    def required_params(self) -> List[ParamSpec]:
        return [p for p in self.params if p.required]

    @property
    def optional_params(self) -> List[ParamSpec]:
        return [p for p in self.params if not p.required]

    @property
    def path_params(self) -> List[ParamSpec]:
        return [p for p in self.params if p.location == "path"]

    @property
    def query_params(self) -> List[ParamSpec]:
        return [p for p in self.params if p.location == "query"]

    @property
    def body_params(self) -> List[ParamSpec]:
        return [p for p in self.params if p.location == "body"]
