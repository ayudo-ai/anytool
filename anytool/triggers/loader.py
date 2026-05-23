"""
Trigger Spec Loader — loads trigger definitions from YAML specs.

Same philosophy as core/loader.py for actions:
  - YAML specs are the single source of truth
  - No hardcoded trigger maps
  - Config schemas come from the spec

Usage:
    loader = TriggerSpecLoader("registry/")
    triggers = loader.list_triggers(provider="google")
    spec = loader.get_trigger("gmail_new_email")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger


class TriggerSpec:
    """A parsed trigger specification."""

    def __init__(self, data: Dict[str, Any], path: str = ""):
        self.raw = data
        self.path = path

        # Core identity
        self.trigger: str = data["trigger"]            # gmail_new_email
        self.app: str = data.get("app", "")             # google
        self.display_name: str = data.get("display_name", self.trigger.replace("_", " ").title())
        self.description: str = data.get("description", "").strip()

        # Execution mode
        self.mode: str = data.get("mode", "poll")       # poll | webhook
        self.provider: str = data.get("provider", self.app)
        self.events: List[str] = data.get("events", [])  # webhook events (e.g. ["issues"])

        # Auth
        self.auth: Dict[str, Any] = data.get("auth", {})

        # Config schema — what the user configures when deploying
        self.config: Dict[str, Any] = data.get("config", {})

        # Poll settings (for mode=poll)
        self.poll: Dict[str, Any] = data.get("poll", {})

        # Payload schema — what the trigger event contains
        self.payload: Dict[str, Any] = data.get("payload", {})

        # Tags
        self.tags: List[str] = data.get("tags", [])

    @property
    def config_schema(self) -> Dict[str, Any]:
        """Return the config schema in JSON Schema format for the UI."""
        return self.config if self.config else {}

    def to_api_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "type": self.trigger,
            "display_name": self.display_name,
            "description": self.description,
            "provider": self.provider,
            "app": self.app,
            "mode": self.mode,
            "events": self.events,
            "config_schema": self.config_schema,
            "payload_schema": self.payload,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return f"TriggerSpec({self.trigger}, app={self.app}, mode={self.mode})"


class TriggerSpecLoader:
    """Loads trigger YAML specs from the registry directory.

    Directory structure:
        registry/
        ├── google/gmail/triggers/new_email.yaml
        ├── slack/triggers/new_message.yaml
        ├── github/triggers/new_issue.yaml
        └── ...
    """

    def __init__(self, registry_path: str = "registry/"):
        self._registry = Path(registry_path)
        self._triggers: Dict[str, TriggerSpec] = {}
        self._loaded = False

    def _load(self) -> None:
        """Scan registry for trigger YAML files and load them."""
        if self._loaded:
            return

        trigger_files = list(self._registry.rglob("triggers/*.yaml"))
        for path in trigger_files:
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)

                if not data or "trigger" not in data:
                    logger.warning(f"[trigger_loader] Skipping {path}: no 'trigger' key")
                    continue

                spec = TriggerSpec(data, str(path))
                self._triggers[spec.trigger] = spec
                logger.debug(f"[trigger_loader] Loaded: {spec.trigger} ({spec.mode})")
            except Exception as e:
                logger.error(f"[trigger_loader] Failed to load {path}: {e}")

        self._loaded = True
        logger.info(
            f"[trigger_loader] Loaded {len(self._triggers)} trigger specs "
            f"from {self._registry}"
        )

    def get_trigger(self, trigger_type: str) -> Optional[TriggerSpec]:
        """Get a specific trigger spec by type name."""
        self._load()
        return self._triggers.get(trigger_type)

    def list_triggers(
        self,
        provider: Optional[str] = None,
        app: Optional[str] = None,
    ) -> List[TriggerSpec]:
        """List trigger specs, optionally filtered by provider or app."""
        self._load()
        triggers = list(self._triggers.values())

        if provider:
            triggers = [t for t in triggers if t.provider == provider]
        if app:
            triggers = [t for t in triggers if t.app == app]

        return triggers

    def all_triggers(self) -> Dict[str, TriggerSpec]:
        """Get all loaded trigger specs."""
        self._load()
        return dict(self._triggers)

    def reload(self) -> None:
        """Force reload all specs."""
        self._triggers.clear()
        self._loaded = False
        self._load()
