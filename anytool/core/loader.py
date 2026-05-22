"""
Spec Loader — reads YAML spec files from the registry directory.

    from anytool.core.loader import SpecRegistry

    registry = SpecRegistry("registry/")
    spec = registry.get("docusign_create_envelope")
    specs = registry.list_by_app("docusign")
    all_specs = registry.all()
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml
from loguru import logger

from anytool.core.models import (
    ActionSpec, AuthSpec, RequestSpec, ResponseSpec,
    RateLimitSpec, Example,
)


def _parse_auth(raw: dict) -> AuthSpec:
    """Parse auth section from YAML."""
    if not raw:
        return AuthSpec()
    return AuthSpec(
        type=raw.get("type", "oauth2"),
        scopes=tuple(raw.get("scopes", [])),
        header=raw.get("header", "Authorization: Bearer {access_token}"),
        inject_from_metadata=raw.get("inject_from_metadata", {}),
    )


def _parse_request(raw: dict) -> RequestSpec:
    """Parse request section from YAML."""
    if not raw:
        return RequestSpec()
    return RequestSpec(
        content_type=raw.get("content_type", "application/json"),
        body_schema=raw.get("body_schema", {}),
        note=raw.get("note", ""),
    )


def _parse_response(raw: dict) -> ResponseSpec:
    """Parse response section from YAML."""
    if not raw:
        return ResponseSpec()
    return ResponseSpec(
        success_codes=tuple(raw.get("success_codes", [200])),
        success_condition=raw.get("success_condition", ""),
        body_schema=raw.get("body_schema", {}),
        extract=raw.get("extract", {}),
    )


def _parse_rate_limit(raw: dict) -> RateLimitSpec:
    """Parse rate_limit section from YAML."""
    if not raw:
        return RateLimitSpec()
    return RateLimitSpec(
        requests_per_minute=raw.get("requests_per_minute", 0),
        requests_per_second=raw.get("requests_per_second", 0),
        requests_per_hour=raw.get("requests_per_hour", 0),
        daily_limit=raw.get("daily_limit", 0),
        burst=raw.get("burst", 0),
        note=raw.get("note", ""),
    )


def _parse_example(raw: dict) -> Example:
    """Parse a single example from YAML."""
    return Example(
        name=raw.get("name", ""),
        description=raw.get("description", ""),
        request=raw.get("request", {}),
        agent_input=raw.get("agent_input", {}),
        actual_request=raw.get("actual_request", {}),
        response=raw.get("response", {}),
    )


def load_spec(path: Path) -> ActionSpec:
    """Load a single spec from a YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError(f"Empty spec file: {path}")

    return ActionSpec(
        name=raw["name"],
        app=raw["app"],
        version=raw.get("version", ""),
        description=raw.get("description", "").strip(),
        method=raw.get("method", "GET"),
        path=raw.get("path", ""),
        base_url=raw.get("base_url", ""),
        auth=_parse_auth(raw.get("auth")),
        request=_parse_request(raw.get("request")),
        encoder=raw.get("encoder", ""),
        agent_params=raw.get("agent_params", {}),
        response=_parse_response(raw.get("response")),
        errors=raw.get("errors", {}),
        rate_limit=_parse_rate_limit(raw.get("rate_limit")),
        tags=tuple(raw.get("tags", [])),
        examples=tuple(_parse_example(e) for e in raw.get("examples", [])),
        encoder_spec=raw.get("encoder_spec", {}),
    )


class SpecRegistry:
    """Registry of all loaded specs.

    Loads all YAML files from a registry directory on init.
    Provides lookup by name, by app, and listing all.
    """

    def __init__(self, registry_path: str | Path = "registry/"):
        self._specs: Dict[str, ActionSpec] = {}
        self._by_app: Dict[str, List[ActionSpec]] = {}
        self._path = Path(registry_path)

        if self._path.exists():
            self._load_all()

    def _load_all(self) -> None:
        """Load all YAML spec files from the registry directory."""
        yaml_files = sorted(self._path.rglob("*.yaml"))

        for path in yaml_files:
            try:
                spec = load_spec(path)
                self._specs[spec.name] = spec
                self._by_app.setdefault(spec.app, []).append(spec)
            except Exception as e:
                logger.warning(f"[registry] Failed to load {path}: {e}")

        logger.info(
            f"[registry] Loaded {len(self._specs)} specs from {self._path} "
            f"| apps: {list(self._by_app.keys())}"
        )

    def get(self, name: str) -> Optional[ActionSpec]:
        """Get a spec by action name."""
        return self._specs.get(name)

    def list_by_app(self, app: str) -> List[ActionSpec]:
        """Get all specs for an app."""
        return self._by_app.get(app, [])

    def all(self) -> List[ActionSpec]:
        """Get all loaded specs."""
        return list(self._specs.values())

    def apps(self) -> List[str]:
        """Get all app slugs."""
        return list(self._by_app.keys())

    def names(self) -> List[str]:
        """Get all action names."""
        return list(self._specs.keys())

    def search_by_tags(self, tags: List[str]) -> List[ActionSpec]:
        """Find specs matching any of the given tags."""
        tag_set = set(tags)
        return [s for s in self._specs.values() if tag_set & set(s.tags)]

    def register(self, spec: ActionSpec) -> None:
        """Register a spec programmatically (e.g., from auto-generation)."""
        self._specs[spec.name] = spec
        self._by_app.setdefault(spec.app, []).append(spec)

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, name: str) -> bool:
        return name in self._specs

    def __repr__(self) -> str:
        return f"SpecRegistry({len(self._specs)} specs, {len(self._by_app)} apps)"
