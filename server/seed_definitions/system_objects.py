"""
System object definitions for anytool platform.

Each entry defines a MetaObject with its MetaFields.
Run seed_system_objects.py once on fresh deploy. Idempotent.

Hierarchy:
  Account (developer/company)
    └── Workspace (isolated environment)
          └── Users (end-users — connect apps, trigger events)
                ├── Connections (OAuth tokens per user, stored in Nango)
                ├── Triggers (polling configs, each with its own webhook_url)
                └── Usage (API calls, metered per workspace)
"""

from typing import Any, Dict, List


SYSTEM_OBJECTS: List[Dict[str, Any]] = [
    # ── Account ──────────────────────────────────────────────────────
    {
        "slug": "account",
        "label": "Account",
        "description": "Developer/company account. Top-level tenant. Owns workspaces and billing.",
        "fields": [
            {
                "api_name": "name",
                "label": "Account Name",
                "type": "string",
                "required": True,
            },
            {
                "api_name": "email",
                "label": "Email",
                "type": "email",
                "required": True,
                "unique": True,
            },
            {
                "api_name": "plan",
                "label": "Plan",
                "type": "string",
                "required": True,
                "default": "free",
                "validation_rules": {
                    "options": ["free", "pro", "enterprise"],
                },
            },
            {
                "api_name": "status",
                "label": "Status",
                "type": "string",
                "required": True,
                "default": "active",
                "validation_rules": {
                    "options": ["active", "suspended", "cancelled"],
                },
            },
            {
                "api_name": "settings",
                "label": "Account Settings",
                "type": "json",
                "default": {},
            },
        ],
    },

    # ── Workspace ────────────────────────────────────────────────────
    {
        "slug": "workspace",
        "label": "Workspace",
        "description": (
            "Isolated environment within an account. "
            "Each workspace has its own API key, usage tracking, and trigger limits. "
            "Contains multiple end-users who connect their own apps."
        ),
        "fields": [
            {
                "api_name": "name",
                "label": "Workspace Name",
                "type": "string",
                "required": True,
            },
            {
                "api_name": "account_id",
                "label": "Parent Account",
                "type": "reference",
                "required": True,
            },
            {
                "api_name": "description",
                "label": "Description",
                "type": "text",
            },
            {
                "api_name": "status",
                "label": "Status",
                "type": "string",
                "required": True,
                "default": "active",
                "validation_rules": {
                    "options": ["active", "suspended"],
                },
            },
            {
                "api_name": "calls_this_month",
                "label": "API Calls This Month",
                "type": "number",
                "default": 0,
            },
            {
                "api_name": "settings",
                "label": "Workspace Settings",
                "type": "json",
                "default": {},
            },
        ],
    },

    # ── API Key ──────────────────────────────────────────────────────
    {
        "slug": "api_key",
        "label": "API Key",
        "description": (
            "API key scoped to account + workspace. "
            "Used in Authorization header: Bearer at_xxxx. "
            "Resolves to account_id + workspace_id for request scoping."
        ),
        "fields": [
            {
                "api_name": "label",
                "label": "Key Label",
                "type": "string",
                "required": True,
            },
            {
                "api_name": "is_active",
                "label": "Active",
                "type": "boolean",
                "required": True,
                "default": True,
            },
            {
                "api_name": "last_used_at",
                "label": "Last Used At",
                "type": "datetime",
            },
            {
                "api_name": "expires_at",
                "label": "Expires At",
                "type": "datetime",
            },
        ],
    },

    # ── Trigger ──────────────────────────────────────────────────────
    {
        "slug": "trigger",
        "label": "Trigger",
        "description": (
            "Event trigger deployed for a specific user_id. "
            "Each trigger polls a user's connected app and delivers events "
            "to its own webhook_url. A single user can have multiple triggers "
            "with different webhooks."
        ),
        "fields": [
            {
                "api_name": "trigger_type",
                "label": "Trigger Type",
                "type": "string",
                "required": True,
                # gmail_new_message, slack_new_message, etc.
            },
            {
                "api_name": "provider",
                "label": "Provider",
                "type": "string",
                "required": True,
                # google, slack, freshdesk, etc.
            },
            {
                "api_name": "user_id",
                "label": "User ID",
                "type": "string",
                "required": True,
                # End-user whose connection to poll
            },
            {
                "api_name": "webhook_url",
                "label": "Webhook URL",
                "type": "url",
                "required": True,
                # Where to POST events — unique per trigger
            },
            {
                "api_name": "filters",
                "label": "Event Filters",
                "type": "json",
                "default": {},
                # from_contains, subject_contains, label_ids, etc.
            },
            {
                "api_name": "poll_interval_seconds",
                "label": "Poll Interval (seconds)",
                "type": "number",
                "required": True,
                "default": 90,
            },
            {
                "api_name": "enabled",
                "label": "Enabled",
                "type": "boolean",
                "required": True,
                "default": True,
            },
            {
                "api_name": "last_seen_id",
                "label": "Last Seen Event ID",
                "type": "string",
                "default": "",
                # For deduplication — tracks last processed event
            },
            {
                "api_name": "last_poll_at",
                "label": "Last Poll At",
                "type": "datetime",
            },
            {
                "api_name": "error_count",
                "label": "Consecutive Errors",
                "type": "number",
                "default": 0,
            },
            {
                "api_name": "last_error",
                "label": "Last Error",
                "type": "text",
            },
        ],
    },

    # ── Usage Log ────────────────────────────────────────────────────
    {
        "slug": "usage_log",
        "label": "Usage Log",
        "description": (
            "API call usage tracking per workspace. "
            "Each execute call creates a usage_log record for billing and audit."
        ),
        "fields": [
            {
                "api_name": "workspace_id",
                "label": "Workspace",
                "type": "reference",
                "required": True,
            },
            {
                "api_name": "user_id",
                "label": "User ID",
                "type": "string",
                "required": True,
            },
            {
                "api_name": "action",
                "label": "Action Name",
                "type": "string",
                "required": True,
                # gmail_send_email, slack_send_message, etc.
            },
            {
                "api_name": "provider",
                "label": "Provider",
                "type": "string",
                "required": True,
            },
            {
                "api_name": "status_code",
                "label": "HTTP Status Code",
                "type": "number",
            },
            {
                "api_name": "successful",
                "label": "Successful",
                "type": "boolean",
                "required": True,
            },
            {
                "api_name": "duration_ms",
                "label": "Duration (ms)",
                "type": "number",
            },
            {
                "api_name": "error",
                "label": "Error Message",
                "type": "text",
            },
        ],
    },

    # ── Webhook Log ──────────────────────────────────────────────────
    {
        "slug": "webhook_log",
        "label": "Webhook Log",
        "description": (
            "Trigger webhook delivery log. "
            "Tracks each webhook POST — success/failure, response code, retry count."
        ),
        "fields": [
            {
                "api_name": "trigger_id",
                "label": "Trigger",
                "type": "reference",
                "required": True,
            },
            {
                "api_name": "user_id",
                "label": "User ID",
                "type": "string",
                "required": True,
            },
            {
                "api_name": "webhook_url",
                "label": "Webhook URL",
                "type": "url",
                "required": True,
            },
            {
                "api_name": "event_type",
                "label": "Event Type",
                "type": "string",
                "required": True,
            },
            {
                "api_name": "event_data",
                "label": "Event Data",
                "type": "json",
                "required": True,
            },
            {
                "api_name": "status_code",
                "label": "Response Status Code",
                "type": "number",
            },
            {
                "api_name": "successful",
                "label": "Delivered",
                "type": "boolean",
                "required": True,
            },
            {
                "api_name": "retry_count",
                "label": "Retry Count",
                "type": "number",
                "default": 0,
            },
            {
                "api_name": "error",
                "label": "Error",
                "type": "text",
            },
        ],
    },

    # ── Session (dashboard login sessions) ───────────────────────
    {
        "slug": "session",
        "label": "Session",
        "description": (
            "Dashboard login session. Created on sign-in (Google SSO or email/password). "
            "Short-lived (7 days). Stored as sess_xxxx token."
        ),
        "fields": [
            {
                "api_name": "expires_at",
                "label": "Expires At",
                "type": "datetime",
                "required": True,
            },
        ],
    },

    # ── Auth Config (per-workspace OAuth credentials) ─────────
    {
        "slug": "auth_config",
        "label": "Auth Config",
        "description": (
            "Per-workspace OAuth app credentials. Each workspace can have "
            "multiple auth configs (one per provider). Supports managed "
            "(platform-provided) and custom (developer-provided) credentials. "
            "Client secrets stored encrypted."
        ),
        "fields": [
            {
                "api_name": "name",
                "label": "Config Name",
                "type": "string",
                "required": True,
                # e.g. "Google Production", "Slack Bot"
            },
            {
                "api_name": "provider",
                "label": "Provider",
                "type": "string",
                "required": True,
                # google, slack, hubspot, github, docusign, zendesk, freshdesk, whatsapp
            },
            {
                "api_name": "auth_scheme",
                "label": "Auth Scheme",
                "type": "string",
                "required": True,
                "default": "oauth2",
                "validation_rules": {
                    "options": ["oauth2", "api_key", "bearer"],
                },
            },
            {
                "api_name": "management",
                "label": "Management",
                "type": "string",
                "required": True,
                "default": "custom",
                "validation_rules": {
                    "options": ["managed", "custom"],
                },
                # managed = platform-provided creds (from env)
                # custom = developer-provided creds
            },
            {
                "api_name": "client_id",
                "label": "Client ID",
                "type": "string",
            },
            {
                "api_name": "client_secret_encrypted",
                "label": "Client Secret (encrypted)",
                "type": "text",
                # Fernet-encrypted. Never returned in API responses.
            },
            {
                "api_name": "scopes",
                "label": "OAuth Scopes",
                "type": "list",
                "default": [],
            },
            {
                "api_name": "redirect_uri",
                "label": "Redirect URI",
                "type": "url",
            },
            {
                "api_name": "api_key_encrypted",
                "label": "API Key (encrypted)",
                "type": "text",
                # For api_key auth (e.g. Freshdesk)
            },
            {
                "api_name": "domain",
                "label": "Domain",
                "type": "string",
                # e.g. "yourcompany.freshdesk.com" or Zendesk subdomain
            },
            {
                "api_name": "extra_config",
                "label": "Extra Config",
                "type": "json",
                "default": {},
            },
            {
                "api_name": "connections_count",
                "label": "Connected Users",
                "type": "number",
                "default": 0,
            },
            {
                "api_name": "enabled",
                "label": "Enabled",
                "type": "boolean",
                "required": True,
                "default": True,
            },
        ],
    },

    # ── OAuth Token (encrypted token storage) ─────────────────
    {
        "slug": "oauth_token",
        "label": "OAuth Token",
        "description": (
            "Encrypted OAuth tokens for end-user app connections. "
            "Keyed by 'app:user_id'. Tokens encrypted with Fernet (AES-128-CBC)."
        ),
        "fields": [
            {
                "api_name": "encrypted",
                "label": "Encrypted Token Data",
                "type": "text",
                "required": True,
            },
        ],
    },

    # ── OAuth State (transient CSRF protection) ─────────────
    {
        "slug": "oauth_state",
        "label": "OAuth State",
        "description": (
            "Transient CSRF state during OAuth authorization flow. "
            "One-time use — deleted after callback."
        ),
        "fields": [
            {
                "api_name": "app",
                "label": "App",
                "type": "string",
                "required": True,
            },
            {
                "api_name": "user_id",
                "label": "User ID",
                "type": "string",
                "required": True,
            },
            {
                "api_name": "redirect_uri",
                "label": "Redirect URI",
                "type": "url",
                "required": True,
            },
            {
                "api_name": "scopes",
                "label": "Scopes",
                "type": "list",
                "default": [],
            },
        ],
    },

    # ── Connection (metadata — tracks which users connected which apps) ──
    {
        "slug": "connection",
        "label": "Connection",
        "description": (
            "Tracks which users have connected which providers. "
            "OAuth tokens live in Nango — this is metadata only. "
            "Scoped to user_id, not workspace."
        ),
        "fields": [
            {
                "api_name": "user_id",
                "label": "User ID",
                "type": "string",
                "required": True,
                # End-user who connected
            },
            {
                "api_name": "provider",
                "label": "Provider",
                "type": "string",
                "required": True,
                # google, slack, docusign, etc.
            },
            {
                "api_name": "nango_connection_id",
                "label": "Nango Connection ID",
                "type": "string",
                # Maps to Nango's connection_id
            },
            {
                "api_name": "status",
                "label": "Status",
                "type": "string",
                "required": True,
                "default": "active",
                "validation_rules": {
                    "options": ["active", "expired", "revoked"],
                },
            },
            {
                "api_name": "connected_at",
                "label": "Connected At",
                "type": "datetime",
            },
            {
                "api_name": "scopes",
                "label": "OAuth Scopes",
                "type": "list",
                "default": [],
            },
        ],
    },
]
