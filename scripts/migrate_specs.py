#!/usr/bin/env python3
"""
Migrate old ActionSpec Python specs → new YAML registry format.

Reads the existing anytool/specs/*.py files and generates YAML files
in registry/ with the v2 format.

Usage:
    python scripts/migrate_specs.py                  # Migrate all
    python scripts/migrate_specs.py --app freshdesk  # Migrate one app
    python scripts/migrate_specs.py --dry-run        # Preview without writing

This handles:
- Flat param specs → body_schema with JSON Schema
- request_transform → encoder hints (noted, not auto-converted)
- Path/query/body param location → correct placement in schema
- App registry metadata → auth section
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from anytool.specs.base import ActionSpec as OldActionSpec, ParamSpec
from anytool.apps.registry import APPS


# ── App metadata ─────────────────────────────────────────────────────

APP_AUTH = {
    "google": {
        "type": "oauth2",
        "scopes_note": "Scopes vary per action — see spec",
        "header": "Authorization: Bearer {access_token}",
    },
    "slack": {
        "type": "oauth2",
        "header": "Authorization: Bearer {access_token}",
    },
    "hubspot": {
        "type": "oauth2",
        "header": "Authorization: Bearer {access_token}",
    },
    "github": {
        "type": "oauth2",
        "header": "Authorization: Bearer {access_token}",
    },
    "docusign": {
        "type": "oauth2",
        "header": "Authorization: Bearer {access_token}",
        "inject_from_metadata": {"account_id": "account_id"},
    },
    "freshdesk": {
        "type": "api_key",
        "header": "Authorization: Basic {base64(api_key:X)}",
    },
    "zendesk": {
        "type": "oauth2",
        "header": "Authorization: Bearer {access_token}",
        "inject_from_metadata": {"subdomain": "subdomain"},
    },
    "whatsapp": {
        "type": "bearer",
        "header": "Authorization: Bearer {access_token}",
    },
}

# Known transforms → encoder mappings
TRANSFORM_TO_ENCODER = {
    "gmail_mime": "gmail_mime",
    # These DON'T need encoders in v2 — the LLM constructs the body directly
    # We note them as comments in the spec
    "hubspot_properties": None,  # LLM wraps in {properties: {}}
    "hubspot_search": None,      # LLM constructs filter structure
    "hubspot_note": None,        # LLM constructs note + associations
    "zendesk_ticket": None,      # LLM wraps in {ticket: {}}
    "zendesk_ticket_update": None,
    "zendesk_comment": None,
    "docusign_envelope": None,   # LLM constructs nested JSON
    "docusign_void": None,
    "docusign_resend": None,
    "whatsapp_template": None,   # LLM constructs message structure
    "whatsapp_text": None,
    "whatsapp_media": None,
    "whatsapp_reaction": None,
    "whatsapp_read": None,
    "sheets_append": None,
    "calendar_event": None,
    "docs_insert_text": None,
    "docs_replace_text": None,
}


# ── Type mapping ─────────────────────────────────────────────────────

TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "list": "array",
    "object": "object",
}


def param_to_schema_property(param: ParamSpec) -> Dict[str, Any]:
    """Convert a ParamSpec to a JSON Schema property."""
    prop: Dict[str, Any] = {
        "type": TYPE_MAP.get(param.type, "string"),
    }
    if param.description:
        prop["description"] = param.description
    if param.enum:
        prop["enum"] = param.enum
    if param.default is not None:
        prop["default"] = param.default
    if prop["type"] == "array":
        prop["items"] = {"type": "string"}  # default; may need manual refinement
    return prop


def build_body_schema(spec: OldActionSpec) -> Dict[str, Any]:
    """Build JSON Schema for the request body from old ParamSpecs."""
    body_params = [p for p in spec.params if p.location == "body"]
    if not body_params:
        return {}

    properties = {}
    required = []
    for p in body_params:
        properties[p.name] = param_to_schema_property(p)
        if p.required:
            required.append(p.name)

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def build_query_note(spec: OldActionSpec) -> str:
    """Build a note about query params (if any)."""
    query_params = [p for p in spec.params if p.location == "query"]
    if not query_params:
        return ""
    names = [p.name for p in query_params]
    return f"Query parameters: {', '.join(names)}"


def convert_spec(spec: OldActionSpec) -> Dict[str, Any]:
    """Convert an old ActionSpec to the new YAML format."""
    app_config = APPS.get(spec.app, None)
    app_auth = APP_AUTH.get(spec.app, {})

    # Auth section
    auth: Dict[str, Any] = {"type": app_auth.get("type", "oauth2")}
    if spec.scopes:
        auth["scopes"] = spec.scopes
    if app_auth.get("header"):
        auth["header"] = app_auth["header"]
    if app_auth.get("inject_from_metadata"):
        auth["inject_from_metadata"] = app_auth["inject_from_metadata"]

    # Base URL
    base_url = spec.base_url or (app_config.api_base_url if app_config else "")

    # Request section
    body_schema = build_body_schema(spec)

    # Handle GET/DELETE with query params
    if spec.method in ("GET", "DELETE"):
        query_params = [p for p in spec.params if p.location == "query"]
        if query_params:
            properties = {}
            for p in query_params:
                properties[p.name] = param_to_schema_property(p)
            body_schema = {
                "type": "object",
                "properties": properties,
            }
            required = [p.name for p in query_params if p.required]
            if required:
                body_schema["required"] = required

    # Encoder
    encoder = ""
    transform_note = ""
    if spec.request_transform:
        encoder = TRANSFORM_TO_ENCODER.get(spec.request_transform, "")
        if encoder is None:
            encoder = ""
            transform_note = (
                f"Note: Old spec used transform '{spec.request_transform}'. "
                f"In v2, the LLM constructs the exact body structure directly."
            )

    # Response
    response: Dict[str, Any] = {}
    if spec.method in ("POST", "PUT"):
        response["success_codes"] = [200, 201]
    else:
        response["success_codes"] = [200]
    if spec.response_ids:
        response["extract"] = spec.response_ids

    # Build the full YAML structure
    result: Dict[str, Any] = {
        "name": spec.name,
        "app": spec.app,
        "description": spec.description,
        "method": spec.method,
        "path": spec.path,
        "base_url": base_url,
        "auth": auth,
    }

    if encoder:
        result["encoder"] = encoder

    result["request"] = {
        "content_type": spec.content_type or "application/json",
    }
    if body_schema:
        result["request"]["body_schema"] = body_schema
    if transform_note:
        result["request"]["note"] = transform_note

    result["response"] = response

    # Tags based on app
    tag_map = {
        "google": ["google"],
        "slack": ["messaging", "chat"],
        "hubspot": ["crm", "sales"],
        "github": ["development", "git"],
        "docusign": ["esignature", "documents"],
        "freshdesk": ["support", "helpdesk"],
        "zendesk": ["support", "helpdesk"],
        "whatsapp": ["messaging", "mobile"],
    }
    result["tags"] = tag_map.get(spec.app, [])

    # Add path param info
    path_params = [p for p in spec.params if p.location == "path"]
    if path_params:
        # Add path params to body_schema so the LLM knows about them
        if "body_schema" not in result["request"]:
            result["request"]["body_schema"] = {"type": "object", "properties": {}}
        if "properties" not in result["request"].get("body_schema", {}):
            result["request"]["body_schema"]["properties"] = {}
        for p in path_params:
            # Skip injected params (they come from metadata)
            inject_keys = auth.get("inject_from_metadata", {}).keys()
            if p.name in inject_keys:
                continue
            result["request"]["body_schema"]["properties"][p.name] = param_to_schema_property(p)
            if p.required:
                result["request"]["body_schema"].setdefault("required", []).append(p.name)

    return result


def yaml_dump(data: dict) -> str:
    """Dump to YAML with nice formatting."""
    return yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )


def migrate_app(app_name: str, specs: list, output_dir: Path, dry_run: bool = False):
    """Migrate all specs for an app."""
    app_dir = output_dir / app_name
    if not dry_run:
        app_dir.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        converted = convert_spec(spec)
        yaml_content = yaml_dump(converted)

        # Build filename from action name minus app prefix
        action_name = spec.name
        if action_name.startswith(f"{app_name}_"):
            filename = action_name[len(f"{app_name}_"):] + ".yaml"
        else:
            filename = action_name + ".yaml"

        filepath = app_dir / filename

        if dry_run:
            print(f"\n{'='*60}")
            print(f"WOULD WRITE: {filepath}")
            print(f"{'='*60}")
            print(yaml_content[:500])
            if len(yaml_content) > 500:
                print(f"... ({len(yaml_content)} bytes total)")
        else:
            filepath.write_text(f"# Auto-migrated from old spec format\n# Review and enhance: add examples, refine body_schema nesting\n\n{yaml_content}")
            print(f"  ✅ {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Migrate old specs to YAML registry format")
    parser.add_argument("--app", help="Migrate specific app only")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--output", default="registry", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)

    # Import all old specs
    from anytool.specs.freshdesk import FRESHDESK_SPECS
    from anytool.specs.github import GITHUB_SPECS
    from anytool.specs.whatsapp import WHATSAPP_SPECS
    from anytool.specs.slack import SLACK_SPECS
    from anytool.specs.hubspot import HUBSPOT_SPECS
    from anytool.specs.zendesk import ZENDESK_SPECS
    from anytool.specs.docusign import DOCUSIGN_SPECS

    all_apps = {
        "freshdesk": FRESHDESK_SPECS,
        "github": GITHUB_SPECS,
        "whatsapp": WHATSAPP_SPECS,
        "slack": SLACK_SPECS[1:],  # skip send_message (already hand-crafted)
        "hubspot": HUBSPOT_SPECS[1:],  # skip create_contact (already hand-crafted)
        "zendesk": ZENDESK_SPECS[1:],  # skip create_ticket (already hand-crafted)
        "docusign": DOCUSIGN_SPECS[1:],  # skip create_envelope (already hand-crafted)
    }

    if args.app:
        if args.app not in all_apps:
            print(f"Unknown app: {args.app}. Available: {list(all_apps.keys())}")
            return
        apps = {args.app: all_apps[args.app]}
    else:
        apps = all_apps

    total = 0
    for app_name, specs in apps.items():
        print(f"\n{'─'*40}")
        print(f"Migrating {app_name}: {len(specs)} specs")
        print(f"{'─'*40}")
        migrate_app(app_name, specs, output_dir, args.dry_run)
        total += len(specs)

    print(f"\n{'='*60}")
    print(f"{'DRY RUN: ' if args.dry_run else ''}Migrated {total} specs across {len(apps)} apps")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
