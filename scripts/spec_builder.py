#!/usr/bin/env python3
"""
Spec Builder — Generate anytool YAML specs from OpenAPI / Google Discovery docs.

Usage:
  # From an OpenAPI spec URL
  python scripts/spec_builder.py openapi https://api.slack.com/specs/openapi/slack_web.json --app slack --actions chat.postMessage,conversations.list

  # From a Google Discovery doc
  python scripts/spec_builder.py google calendar --actions list_events,create_event,get_event,update_event,delete_event

  # From a local OpenAPI file
  python scripts/spec_builder.py openapi ./specs/jira-v3.json --app jira --all

  # List available actions in a spec
  python scripts/spec_builder.py openapi https://api.example.com/openapi.json --app example --list
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# ── Google Discovery doc action mapping ──────────────────────────────
# Maps friendly names → Discovery doc resource.method
GOOGLE_ACTION_MAP = {
    # Calendar
    "calendar_list_calendars": {"resource": "calendarList", "method": "list", "service": "calendar", "version": "v3"},
    "calendar_list_events": {"resource": "events", "method": "list", "service": "calendar", "version": "v3"},
    "calendar_create_event": {"resource": "events", "method": "insert", "service": "calendar", "version": "v3"},
    "calendar_get_event": {"resource": "events", "method": "get", "service": "calendar", "version": "v3"},
    "calendar_update_event": {"resource": "events", "method": "update", "service": "calendar", "version": "v3"},
    "calendar_delete_event": {"resource": "events", "method": "delete", "service": "calendar", "version": "v3"},
    "calendar_quick_add": {"resource": "events", "method": "quickAdd", "service": "calendar", "version": "v3"},
    # Drive
    "drive_list_files": {"resource": "files", "method": "list", "service": "drive", "version": "v3"},
    "drive_get_file": {"resource": "files", "method": "get", "service": "drive", "version": "v3"},
    "drive_create_folder": {"resource": "files", "method": "create", "service": "drive", "version": "v3"},
    "drive_copy_file": {"resource": "files", "method": "copy", "service": "drive", "version": "v3"},
    "drive_delete_file": {"resource": "files", "method": "delete", "service": "drive", "version": "v3"},
    "drive_share_file": {"resource": "permissions", "method": "create", "service": "drive", "version": "v3"},
    "drive_search_files": {"resource": "files", "method": "list", "service": "drive", "version": "v3"},
    # Sheets
    "sheets_get_spreadsheet": {"resource": "spreadsheets", "method": "get", "service": "sheets", "version": "v4"},
    "sheets_read_range": {"resource": "spreadsheets.values", "method": "get", "service": "sheets", "version": "v4"},
    "sheets_write_range": {"resource": "spreadsheets.values", "method": "update", "service": "sheets", "version": "v4"},
    "sheets_append_rows": {"resource": "spreadsheets.values", "method": "append", "service": "sheets", "version": "v4"},
    "sheets_create_spreadsheet": {"resource": "spreadsheets", "method": "create", "service": "sheets", "version": "v4"},
    "sheets_clear_range": {"resource": "spreadsheets.values", "method": "clear", "service": "sheets", "version": "v4"},
    # Docs
    "docs_create_document": {"resource": "documents", "method": "create", "service": "docs", "version": "v1"},
    "docs_get_document": {"resource": "documents", "method": "get", "service": "docs", "version": "v1"},
    "docs_batch_update": {"resource": "documents", "method": "batchUpdate", "service": "docs", "version": "v1"},
    # Gmail (extras beyond existing specs)
    "gmail_create_draft": {"resource": "users.drafts", "method": "create", "service": "gmail", "version": "v1"},
    "gmail_list_labels": {"resource": "users.labels", "method": "list", "service": "gmail", "version": "v1"},
    "gmail_modify_message": {"resource": "users.messages", "method": "modify", "service": "gmail", "version": "v1"},
    "gmail_trash_message": {"resource": "users.messages", "method": "trash", "service": "gmail", "version": "v1"},
}

# Google API scopes per service
GOOGLE_SCOPES = {
    "calendar": ["https://www.googleapis.com/auth/calendar"],
    "drive": ["https://www.googleapis.com/auth/drive"],
    "sheets": ["https://www.googleapis.com/auth/spreadsheets"],
    "docs": ["https://www.googleapis.com/auth/documents"],
    "gmail": ["https://www.googleapis.com/auth/gmail.modify"],
}

# Google API base URLs
GOOGLE_BASE_URLS = {
    "calendar": "https://www.googleapis.com",
    "drive": "https://www.googleapis.com",
    "sheets": "https://sheets.googleapis.com",
    "docs": "https://docs.googleapis.com",
    "gmail": "https://gmail.googleapis.com",
}


def fetch_json(url: str) -> Dict:
    """Fetch JSON from a URL."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "anytool-spec-builder/1.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


_discovery_cache: Dict[str, Dict] = {}

def fetch_google_discovery(service: str, version: str) -> Dict:
    """Fetch Google Discovery document (cached per session)."""
    cache_key = f"{service}:{version}"
    if cache_key in _discovery_cache:
        return _discovery_cache[cache_key]
    url = f"https://www.googleapis.com/discovery/v1/apis/{service}/{version}/rest"
    print(f"  Fetching: {url}")
    doc = fetch_json(url)
    _discovery_cache[cache_key] = doc
    return doc


def _discovery_schema_to_json_schema(schema: Dict, schemas: Dict, depth: int = 0) -> Dict:
    """Convert Google Discovery schema to JSON Schema."""
    if depth > 5:
        return {"type": "object", "description": "Nested object (depth limit reached)"}

    if "$ref" in schema:
        ref_name = schema["$ref"]
        if ref_name in schemas:
            return _discovery_schema_to_json_schema(schemas[ref_name], schemas, depth + 1)
        return {"type": "object", "description": f"Reference to {ref_name}"}

    result: Dict[str, Any] = {}

    # Map Discovery types to JSON Schema types
    dtype = schema.get("type", "object")
    if dtype == "string":
        result["type"] = "string"
        if "format" in schema:
            fmt = schema["format"]
            if fmt == "date-time":
                result["format"] = "date-time"
            elif fmt == "int64":
                result["type"] = "string"
                result["description"] = schema.get("description", "") + " (64-bit integer as string)"
        if "enum" in schema:
            result["enum"] = schema["enum"]
    elif dtype == "integer":
        result["type"] = "integer"
        if "format" in schema:
            result["format"] = schema["format"]
    elif dtype == "number":
        result["type"] = "number"
    elif dtype == "boolean":
        result["type"] = "boolean"
    elif dtype == "array":
        result["type"] = "array"
        if "items" in schema:
            result["items"] = _discovery_schema_to_json_schema(schema["items"], schemas, depth + 1)
        else:
            result["items"] = {"type": "object"}
    elif dtype == "object":
        result["type"] = "object"
        if "properties" in schema:
            result["properties"] = {}
            for pname, pschema in schema["properties"].items():
                result["properties"][pname] = _discovery_schema_to_json_schema(pschema, schemas, depth + 1)
        if "additionalProperties" in schema:
            result["additionalProperties"] = _discovery_schema_to_json_schema(
                schema["additionalProperties"], schemas, depth + 1
            )

    if "description" in schema:
        result["description"] = schema["description"]
    if "default" in schema:
        result["default"] = schema["default"]

    return result


def _method_to_http(method_name: str) -> str:
    """Map Discovery method names to HTTP methods."""
    if method_name in ("list", "get"):
        return "GET"
    elif method_name in ("create", "insert", "quickAdd"):
        return "POST"
    elif method_name in ("update", "patch"):
        return "PUT"
    elif method_name == "delete":
        return "DELETE"
    elif method_name == "modify":
        return "POST"
    elif method_name in ("batchUpdate",):
        return "POST"
    elif method_name in ("append",):
        return "POST"
    elif method_name in ("clear",):
        return "POST"
    elif method_name in ("trash",):
        return "POST"
    return "POST"


def _make_action_name(action_key: str) -> str:
    """Normalize action name: calendar_list_events → calendar_list_events."""
    return action_key.lower().replace("-", "_").replace(".", "_")


def _find_discovery_method(doc: Dict, resource_path: str, method_name: str) -> Optional[Dict]:
    """Find a method in a Discovery document by resource path and method name.
    Handles dotted paths like 'spreadsheets.values' by traversing resources hierarchy.
    """
    parts = resource_path.split(".")
    current = doc.get("resources", {})

    for part in parts:
        if part in current:
            current = current[part]
        elif "resources" in current and part in current["resources"]:
            current = current["resources"][part]
        else:
            return None

    if "methods" in current and method_name in current["methods"]:
        return current["methods"][method_name]

    return None


# Fields to exclude from request body_schema
_PRUNE_REQUEST_FIELDS = {
    # Read-only
    "kind", "etag", "created", "updated", "creator", "organizer",
    "htmlLink", "hangoutLink", "iCalUID", "recurringEventId",
    "locked", "endTimeUnspecified", "attendeesOmitted", "privateCopy",
    "sequence",
    # Deprecated
    "gadget", "anyoneCanAddSelf",
    # Rarely needed by LLMs
    "extendedProperties", "focusTimeProperties", "outOfOfficeProperties",
    "workingLocationProperties", "birthdayProperties", "source",
    "originalStartTime", "colorId", "eventType",
    "conferenceData", "attachments",  # complex nested, rarely set by LLM
    "guestsCanInviteOthers", "guestsCanModify", "guestsCanSeeOtherGuests",
    "transparency", "visibility",
    # Drive read-only
    "thumbnailLink", "iconLink", "hasThumbnail", "webViewLink",
    "webContentLink", "owners", "lastModifyingUser", "isAppAuthorized",
    "spaces", "permissionIds", "fullFileExtension", "fileExtension",
    "md5Checksum", "size", "quotaBytesUsed", "headRevisionId",
    "imageMediaMetadata", "videoMediaMetadata", "capabilities",
    "exportLinks", "copyRequiresWriterPermission", "writersCanShare",
    "viewedByMe", "viewedByMeTime", "modifiedByMe", "modifiedByMeTime",
    "createdTime", "modifiedTime", "version", "originalFilename",
    "ownedByMe", "shared", "trashed", "trashedTime", "explicitlyTrashed",
    "resourceKey", "linkShareMetadata", "labelInfo", "sha1Checksum",
    "sha256Checksum", "shortcutDetails",
    # Sheets read-only
    "spreadsheetUrl", "spreadsheetId",
}

# Fields to keep in response (whitelist approach — only include useful fields)
_RESPONSE_KEEP_FIELDS = {
    # Calendar
    "id", "summary", "description", "location", "start", "end",
    "status", "htmlLink", "hangoutLink", "attendees", "recurrence",
    "reminders", "items", "nextPageToken", "kind",
    # Drive
    "name", "mimeType", "parents", "webViewLink", "files",
    # Sheets
    "spreadsheetId", "spreadsheetUrl", "values", "updatedRows",
    "updatedColumns", "updatedCells", "updates", "sheets", "properties",
    "title", "replies", "range", "majorDimension",
    # Docs
    "documentId", "title", "body", "revisionId",
    # Gmail
    "labels", "messages", "labelIds", "threadId",
    # Generic
    "ok", "error", "message",
}


def _prune_schema(schema: Dict, is_request: bool = True) -> Dict:
    """Remove read-only/deprecated fields from schema to keep specs lean.
    Request: blacklist approach (remove known noisy fields).
    Response: whitelist approach (only keep useful fields).
    """
    if schema.get("type") != "object" or "properties" not in schema:
        return schema

    pruned_props = {}
    for name, prop in schema["properties"].items():
        if is_request:
            # Blacklist: skip known noisy fields
            if name in _PRUNE_REQUEST_FIELDS:
                continue
            desc = prop.get("description", "")
            if "Read-only" in desc and "read" not in name.lower():
                continue
            if "Deprecated" in desc[:20]:
                continue
        else:
            # Whitelist: only keep known useful fields
            if name not in _RESPONSE_KEEP_FIELDS:
                continue

        # Recurse into nested objects (but limit depth)
        if prop.get("type") == "object" and "properties" in prop:
            prop = _prune_schema(prop, is_request)
        pruned_props[name] = prop

    schema = dict(schema)
    schema["properties"] = pruned_props
    return schema


def build_google_spec(action_key: str, action_info: Dict) -> Optional[Dict]:
    """Build an anytool spec from a Google Discovery document."""
    service = action_info["service"]
    version = action_info["version"]
    resource_path = action_info["resource"]
    method_name = action_info["method"]

    doc = fetch_google_discovery(service, version)
    schemas = doc.get("schemas", {})

    method_doc = _find_discovery_method(doc, resource_path, method_name)
    if not method_doc:
        print(f"  ⚠ Method {resource_path}.{method_name} not found in Discovery doc")
        return None

    http_method = method_doc.get("httpMethod", _method_to_http(method_name))
    flat_path = method_doc.get("flatPath") or method_doc.get("path", "")

    # Build full path
    # Use baseUrl from Discovery doc (includes service path prefix)
    base_url = doc.get("baseUrl", "").rstrip("/") or GOOGLE_BASE_URLS.get(service, "https://www.googleapis.com")

    # For Sheets/Docs, the path may already include the service prefix
    if not flat_path.startswith("/"):
        flat_path = "/" + flat_path

    # Convert {+spreadsheetId} → {spreadsheetId} (Discovery uses + for reserved expansion)
    flat_path = re.sub(r'\{\+(\w+)\}', r'{\1}', flat_path)

    # Build path parameters and query parameters
    params = method_doc.get("parameters", {})
    path_params = {}
    query_params = {}

    for pname, pinfo in params.items():
        location = pinfo.get("location", "query")
        param_schema = {
            "type": pinfo.get("type", "string"),
        }
        if "description" in pinfo:
            param_schema["description"] = pinfo["description"]
        if "enum" in pinfo:
            param_schema["enum"] = pinfo["enum"]
        if "default" in pinfo:
            param_schema["default"] = pinfo["default"]
        if pinfo.get("required"):
            param_schema["required"] = True

        if location == "path":
            path_params[pname] = param_schema
        else:
            query_params[pname] = param_schema

    # Build request body schema (pruned — remove read-only/deprecated fields)
    body_schema = None
    request_ref = method_doc.get("request", {}).get("$ref")
    if request_ref and request_ref in schemas:
        body_schema = _discovery_schema_to_json_schema(schemas[request_ref], schemas)
        body_schema = _prune_schema(body_schema, is_request=True)

    # Build response schema (pruned lighter — keep more fields)
    response_schema = None
    response_ref = method_doc.get("response", {}).get("$ref")
    if response_ref and response_ref in schemas:
        response_schema = _discovery_schema_to_json_schema(schemas[response_ref], schemas)
        response_schema = _prune_schema(response_schema, is_request=False)

    # Description
    description = method_doc.get("description", f"{method_name} {resource_path}")

    # Build the spec
    spec: Dict[str, Any] = {
        "name": _make_action_name(action_key),
        "app": "google",
        "version": "1",
        "description": description,
        "method": http_method,
        "path": flat_path,
        "base_url": base_url,
        "auth": {
            "type": "oauth2",
            "scopes": GOOGLE_SCOPES.get(service, []),
            "header": "Authorization: Bearer {access_token}",
        },
    }

    # Request section
    request_section: Dict[str, Any] = {}
    if query_params:
        request_section["query_params"] = query_params
    if body_schema:
        request_section["content_type"] = "application/json"
        request_section["body_schema"] = body_schema
    if request_section:
        spec["request"] = request_section

    # Response section
    if response_schema:
        spec["response"] = {
            "success_codes": [200],
            "body_schema": response_schema,
        }
    else:
        spec["response"] = {"success_codes": [200, 204]}

    # Tags
    spec["tags"] = ["google", service]

    # Generate a basic example
    spec["examples"] = [_build_example(spec, path_params, query_params, body_schema)]

    return spec


def _build_example(spec: Dict, path_params: Dict, query_params: Dict, body_schema: Optional[Dict]) -> Dict:
    """Build a basic example for a spec."""
    example: Dict[str, Any] = {
        "name": f"Basic {spec['name'].replace('_', ' ')}",
    }

    request = {}
    # Add required path params
    for pname, pinfo in path_params.items():
        if pinfo.get("required"):
            if pname in ("calendarId",):
                request[pname] = "primary"
            elif "Id" in pname:
                request[pname] = f"<{pname}>"
            else:
                request[pname] = f"<{pname}>"

    # Add required body fields
    if body_schema and "properties" in body_schema:
        required = body_schema.get("required", [])
        for fname in required:
            finfo = body_schema["properties"].get(fname, {})
            ftype = finfo.get("type", "string")
            if ftype == "string":
                request[fname] = f"<{fname}>"
            elif ftype == "integer":
                request[fname] = 1
            elif ftype == "boolean":
                request[fname] = True

    example["request"] = request if request else {}
    example["response"] = {"status": "success"}
    return example


# ── Spec Validation ──────────────────────────────────────────────────

def validate_spec(spec: Dict, strict: bool = True) -> List[str]:
    """Validate a spec dict. Returns list of errors (empty = valid)."""
    errors = []

    # Required fields
    for field in ["name", "app", "method", "path", "base_url"]:
        if not spec.get(field):
            errors.append(f"Missing required field: {field}")

    # base_url must be a valid URL
    base_url = spec.get("base_url", "")
    if base_url and not base_url.startswith("https://"):
        errors.append(f"base_url must start with https:// — got: {base_url}")

    # Full URL must not have unresolved placeholders in base_url
    # Exception: {domain}, {subdomain} are resolved at runtime for API-key providers
    _ALLOWED_BASE_URL_VARS = {"domain", "subdomain"}
    import re as _re
    base_url_vars = set(_re.findall(r'\{(\w+)\}', base_url))
    unexpected_vars = base_url_vars - _ALLOWED_BASE_URL_VARS
    if unexpected_vars:
        errors.append(f"base_url contains unresolved placeholder: {base_url} (unexpected: {unexpected_vars})")

    # path must start with /
    path = spec.get("path", "")
    if path and not path.startswith("/"):
        errors.append(f"path must start with / — got: {path}")

    # Smoke test: construct full URL and check it looks right
    full_url = f"{base_url.rstrip('/')}{path}"
    if "%7B" in full_url or "%7b" in full_url:
        errors.append(f"URL has encoded braces (should be literal): {full_url}")

    # Verify the URL would hit the right API (not a generic googleapis.com 404)
    if "googleapis.com" in base_url and base_url.rstrip("/") == "https://www.googleapis.com":
        # This is almost always wrong — needs service path like /calendar/v3
        errors.append(
            f"base_url is bare googleapis.com without service path. "
            f"Should include version path like /calendar/v3. Got: {base_url}"
        )

    # Method must be valid
    method = spec.get("method", "")
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        errors.append(f"Invalid method: {method}")

    # Auth section
    auth = spec.get("auth", {})
    if not auth.get("type"):
        errors.append("Missing auth.type")
    if not auth.get("header"):
        errors.append("Missing auth.header")

    # GET requests shouldn't have body_schema (warning only — some specs use it for query params)
    # Not treated as an error since hand-written specs use this convention

    # POST/PUT/PATCH should have body_schema (unless it's a simple action)
    if strict and method in ("POST", "PUT", "PATCH"):
        if not spec.get("request", {}).get("body_schema") and not spec.get("encoder"):
            # Allow some actions without body (like trash)
            pass

    # Name should match app prefix
    name = spec.get("name", "")
    app = spec.get("app", "")
    if name and app and not any(name.startswith(p) for p in [f"{app}_", "gmail_", "calendar_", "drive_", "sheets_", "docs_"]):
        errors.append(f"Action name '{name}' doesn't match expected prefix for app '{app}'")

    return errors


def validate_yaml_file(filepath: str) -> List[str]:
    """Validate a YAML spec file. Returns list of errors."""
    try:
        with open(filepath) as f:
            spec = yaml.safe_load(f)
        if not spec or not isinstance(spec, dict):
            return [f"Invalid YAML or empty file: {filepath}"]
        return validate_spec(spec)
    except Exception as e:
        return [f"Failed to parse {filepath}: {e}"]


def validate_all_specs(registry_dir: Path) -> int:
    """Validate all YAML specs in the registry. Returns error count."""
    total_errors = 0
    total_specs = 0
    for yaml_file in sorted(registry_dir.rglob("*.yaml")):
        if "/triggers/" in str(yaml_file):
            continue
        total_specs += 1
        errors = validate_yaml_file(str(yaml_file))
        if errors:
            total_errors += len(errors)
            rel_path = yaml_file.relative_to(registry_dir)
            print(f"  ✗ {rel_path}")
            for e in errors:
                print(f"    → {e}")

    if total_errors == 0:
        print(f"  ✓ All {total_specs} specs valid")
    else:
        print(f"\n  ✗ {total_errors} errors in {total_specs} specs")
    return total_errors


def google_spec_to_yaml(action_key: str) -> Optional[str]:
    """Generate YAML spec for a Google API action."""
    if action_key not in GOOGLE_ACTION_MAP:
        print(f"  ✗ Unknown action: {action_key}")
        print(f"    Available: {', '.join(sorted(GOOGLE_ACTION_MAP.keys()))}")
        return None

    action_info = GOOGLE_ACTION_MAP[action_key]
    print(f"  Building spec for: {action_key}")
    spec = build_google_spec(action_key, action_info)
    if not spec:
        return None

    # Validate before writing
    errors = validate_spec(spec)
    if errors:
        print(f"  ✗ VALIDATION FAILED for {action_key}:")
        for e in errors:
            print(f"    → {e}")
        return None

    # Add header comment
    service = action_info["service"]
    tier = "Tier 1" if spec.get("method") == "GET" else "Tier 1"
    header = (
        f"# {'─' * 70}\n"
        f"# Google {service.title()} — {spec['name'].replace('_', ' ').title()}\n"
        f"# {tier}: Auto-generated from Google Discovery doc.\n"
        f"# Review and adjust descriptions/examples before use.\n"
        f"# {'─' * 70}\n\n"
    )

    return header + yaml.dump(spec, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)


def write_google_specs(actions: List[str], output_dir: Path, dry_run: bool = False) -> List[str]:
    """Generate and write YAML specs for Google API actions."""
    written = []
    for action_key in actions:
        yaml_str = google_spec_to_yaml(action_key)
        if not yaml_str:
            continue

        # Determine output path: registry/google/{service}/{action}.yaml
        info = GOOGLE_ACTION_MAP[action_key]
        service = info["service"]
        action_name = action_key.replace(f"{service}_" if action_key.startswith(f"{service}_") else "", "")
        # Keep full action name for the file
        file_name = action_key.replace(f"{service}_", "") + ".yaml"

        out_path = output_dir / "google" / service / file_name

        if dry_run:
            print(f"\n{'=' * 60}")
            print(f"  Would write: {out_path}")
            print(f"{'=' * 60}")
            print(yaml_str[:500] + "..." if len(yaml_str) > 500 else yaml_str)
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(yaml_str)
            print(f"  ✓ Written: {out_path}")
            written.append(str(out_path))

    return written


# ── OpenAPI spec builder ─────────────────────────────────────────────

def _resolve_ref(ref: str, spec: Dict) -> Dict:
    """Resolve a $ref in an OpenAPI spec."""
    parts = ref.lstrip("#/").split("/")
    current = spec
    for part in parts:
        current = current.get(part, {})
    return current


def _openapi_schema_to_json_schema(schema: Dict, spec: Dict, depth: int = 0) -> Dict:
    """Convert OpenAPI schema to JSON Schema."""
    if depth > 5:
        return {"type": "object"}

    if "$ref" in schema:
        resolved = _resolve_ref(schema["$ref"], spec)
        return _openapi_schema_to_json_schema(resolved, spec, depth + 1)

    result: Dict[str, Any] = {}
    schema_type = schema.get("type", "object")

    if "allOf" in schema:
        # Merge all schemas
        merged: Dict[str, Any] = {"type": "object", "properties": {}}
        for sub in schema["allOf"]:
            resolved = _openapi_schema_to_json_schema(sub, spec, depth + 1)
            if "properties" in resolved:
                merged["properties"].update(resolved["properties"])
            if "required" in resolved:
                merged.setdefault("required", []).extend(resolved["required"])
        return merged

    if "oneOf" in schema or "anyOf" in schema:
        variants = schema.get("oneOf") or schema.get("anyOf", [])
        if variants:
            return _openapi_schema_to_json_schema(variants[0], spec, depth + 1)

    result["type"] = schema_type
    if "description" in schema:
        result["description"] = schema["description"]
    if "enum" in schema:
        result["enum"] = schema["enum"]
    if "default" in schema:
        result["default"] = schema["default"]

    if schema_type == "array" and "items" in schema:
        result["items"] = _openapi_schema_to_json_schema(schema["items"], spec, depth + 1)
    elif schema_type == "object" and "properties" in schema:
        result["properties"] = {}
        for pname, pschema in schema["properties"].items():
            result["properties"][pname] = _openapi_schema_to_json_schema(pschema, spec, depth + 1)
        if "required" in schema:
            result["required"] = schema["required"]

    return result


def build_openapi_specs(
    spec_source: str,
    app_name: str,
    actions: Optional[List[str]] = None,
    list_only: bool = False,
    output_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> List[str]:
    """Build anytool specs from an OpenAPI document."""
    # Load spec
    if spec_source.startswith("http"):
        openapi_spec = fetch_json(spec_source)
    else:
        with open(spec_source) as f:
            if spec_source.endswith(".yaml") or spec_source.endswith(".yml"):
                openapi_spec = yaml.safe_load(f)
            else:
                openapi_spec = json.load(f)

    base_url = ""
    servers = openapi_spec.get("servers", [])
    if servers:
        base_url = servers[0].get("url", "")

    # Collect all operations
    operations = []
    paths = openapi_spec.get("paths", {})
    for path, methods in paths.items():
        for method, op in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                continue
            op_id = op.get("operationId", f"{method}_{path}")
            operations.append({
                "operationId": op_id,
                "method": method.upper(),
                "path": path,
                "summary": op.get("summary", ""),
                "description": op.get("description", ""),
                "parameters": op.get("parameters", []),
                "requestBody": op.get("requestBody"),
                "responses": op.get("responses", {}),
                "tags": op.get("tags", []),
            })

    if list_only:
        print(f"\nAvailable operations in {app_name} ({len(operations)} total):\n")
        for op in sorted(operations, key=lambda x: x["operationId"]):
            print(f"  {op['method']:6s} {op['path']}")
            print(f"         {op['operationId']} — {op['summary'][:80]}")
        return []

    # Filter to requested actions
    if actions:
        action_set = set(a.lower() for a in actions)
        operations = [op for op in operations if op["operationId"].lower() in action_set]

    if not operations:
        print("No matching operations found.")
        return []

    written = []
    for op in operations:
        spec = _build_openapi_action_spec(op, app_name, base_url, openapi_spec)
        yaml_str = _spec_to_yaml(spec, app_name)

        if output_dir:
            file_name = _make_action_name(f"{app_name}_{op['operationId']}") + ".yaml"
            file_name = file_name.replace(f"{app_name}_{app_name}_", f"")  # avoid double prefix
            out_path = output_dir / app_name / file_name
            if dry_run:
                print(f"\n  Would write: {out_path}")
                print(yaml_str[:400] + "...")
            else:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(yaml_str)
                print(f"  ✓ Written: {out_path}")
                written.append(str(out_path))
        else:
            print(yaml_str)

    return written


def _build_openapi_action_spec(op: Dict, app_name: str, base_url: str, openapi_spec: Dict) -> Dict:
    """Build an anytool spec dict from an OpenAPI operation."""
    op_id = op["operationId"]
    action_name = _make_action_name(f"{app_name}_{op_id}")

    spec: Dict[str, Any] = {
        "name": action_name,
        "app": app_name,
        "version": "1",
        "description": op.get("description") or op.get("summary", ""),
        "method": op["method"],
        "path": op["path"],
        "base_url": base_url,
        "auth": {
            "type": "oauth2",
            "header": "Authorization: Bearer {access_token}",
        },
    }

    # Request
    request_section: Dict[str, Any] = {}

    # Query / path params
    query_params = {}
    for param in op.get("parameters", []):
        if "$ref" in param:
            param = _resolve_ref(param["$ref"], openapi_spec)
        location = param.get("in", "query")
        pschema = param.get("schema", {"type": "string"})
        resolved = _openapi_schema_to_json_schema(pschema, openapi_spec)
        if "description" in param:
            resolved["description"] = param["description"]
        if param.get("required"):
            resolved["required"] = True
        if location == "query":
            query_params[param["name"]] = resolved

    if query_params:
        request_section["query_params"] = query_params

    # Request body
    req_body = op.get("requestBody")
    if req_body:
        if "$ref" in req_body:
            req_body = _resolve_ref(req_body["$ref"], openapi_spec)
        content = req_body.get("content", {})
        json_content = content.get("application/json", {})
        if json_content and "schema" in json_content:
            body_schema = _openapi_schema_to_json_schema(json_content["schema"], openapi_spec)
            request_section["content_type"] = "application/json"
            request_section["body_schema"] = body_schema

    if request_section:
        spec["request"] = request_section

    # Response
    responses = op.get("responses", {})
    success_resp = responses.get("200") or responses.get("201") or responses.get("204")
    if success_resp:
        content = success_resp.get("content", {})
        json_content = content.get("application/json", {})
        if json_content and "schema" in json_content:
            resp_schema = _openapi_schema_to_json_schema(json_content["schema"], openapi_spec)
            spec["response"] = {
                "success_codes": [200],
                "body_schema": resp_schema,
            }
        else:
            spec["response"] = {"success_codes": [200, 204]}
    else:
        spec["response"] = {"success_codes": [200]}

    spec["tags"] = op.get("tags", [app_name])

    return spec


def _spec_to_yaml(spec: Dict, app_name: str) -> str:
    """Convert spec dict to YAML string with header comment."""
    header = (
        f"# {'─' * 70}\n"
        f"# {app_name.title()} — {spec['name'].replace('_', ' ').title()}\n"
        f"# Auto-generated from OpenAPI spec. Review before use.\n"
        f"# {'─' * 70}\n\n"
    )
    return header + yaml.dump(spec, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Anytool Spec Builder — generate YAML specs from API docs")
    subparsers = parser.add_subparsers(dest="source", required=True)

    # Validate
    validate_parser = subparsers.add_parser("validate", help="Validate all specs in registry")
    validate_parser.add_argument("--dir", default="registry", help="Registry directory (default: registry)")

    # Google Discovery
    google_parser = subparsers.add_parser("google", help="Generate from Google Discovery docs")
    google_parser.add_argument("service", help="Google service (calendar, drive, sheets, docs, gmail)")
    google_parser.add_argument("--actions", help="Comma-separated action names (e.g. calendar_list_events,calendar_create_event)")
    google_parser.add_argument("--all", action="store_true", help="Generate all mapped actions for this service")
    google_parser.add_argument("--list", action="store_true", help="List available actions")
    google_parser.add_argument("--dry-run", action="store_true", help="Print specs without writing")
    google_parser.add_argument("--output", default="registry", help="Output directory (default: registry)")

    # OpenAPI
    openapi_parser = subparsers.add_parser("openapi", help="Generate from OpenAPI spec")
    openapi_parser.add_argument("spec", help="OpenAPI spec URL or file path")
    openapi_parser.add_argument("--app", required=True, help="App name (e.g. jira, salesforce)")
    openapi_parser.add_argument("--actions", help="Comma-separated operationIds")
    openapi_parser.add_argument("--all", action="store_true", help="Generate all operations")
    openapi_parser.add_argument("--list", action="store_true", help="List available operations")
    openapi_parser.add_argument("--dry-run", action="store_true", help="Print specs without writing")
    openapi_parser.add_argument("--output", default="registry", help="Output directory (default: registry)")

    args = parser.parse_args()

    if args.source == "validate":
        print(f"\nValidating all specs in {args.dir}/...\n")
        error_count = validate_all_specs(Path(args.dir))
        sys.exit(1 if error_count > 0 else 0)

    elif args.source == "google":
        service = args.service.lower()

        if args.list:
            matching = {k: v for k, v in GOOGLE_ACTION_MAP.items() if v["service"] == service}
            if not matching:
                print(f"No actions mapped for service: {service}")
                print(f"Available services: calendar, drive, sheets, docs, gmail")
                return
            print(f"\nAvailable {service} actions:\n")
            for key in sorted(matching.keys()):
                info = matching[key]
                print(f"  {key:35s}  ({info['resource']}.{info['method']})")
            return

        # Determine which actions to build
        if args.all:
            actions = [k for k, v in GOOGLE_ACTION_MAP.items() if v["service"] == service]
        elif args.actions:
            actions = [a.strip() for a in args.actions.split(",")]
        else:
            print("Specify --actions or --all")
            return

        print(f"\nGenerating {len(actions)} specs for Google {service.title()}...\n")
        output_dir = Path(args.output)
        written = write_google_specs(actions, output_dir, dry_run=args.dry_run)
        print(f"\n✓ Generated {len(written)} specs")

    elif args.source == "openapi":
        actions = None
        if args.actions:
            actions = [a.strip() for a in args.actions.split(",")]
        elif not args.all and not args.list:
            print("Specify --actions, --all, or --list")
            return

        output_dir = Path(args.output) if not args.list else None
        build_openapi_specs(
            args.spec,
            args.app,
            actions=actions,
            list_only=args.list,
            output_dir=output_dir,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
