# anyapi

**Agent-native API execution. No wrappers. No Composio. No Pipedream.**

Give your AI agent curated API specs + OAuth tokens — it calls any API directly.

## Quick Start

```python
from anyapi import AnyAPI

# Nango mode (recommended) — Nango handles all OAuth
api = AnyAPI(nango_secret_key="nango-secret-xxx")

# Call any API by action name
result = await api.call(
    "gmail_send_email",
    connection_id="workspace-123",
    to="vendor@example.com",
    subject="Invoice Follow-up",
    body="Hi, please send the updated invoice.",
)
# → {"data": {"id": "msg-123", "threadId": "thread-456"}, "status_code": 200, "successful": True, "extracted_ids": {"message_id": "msg-123", "thread_id": "thread-456"}}

# Get LangChain tools for an app
tools = api.get_tools("google", connection_id="workspace-123")
# → [gmail_send_email, gmail_search, gmail_get_thread, sheets_append_row, ...]

# Or get tools for ALL apps at once
all_tools = api.get_all_tools(connection_id="workspace-123")
# → 49 tools across 5 apps, ready for llm.bind_tools()
```

## Why

Every integration platform (Composio, Pipedream) pre-builds wrappers for each API action. These wrappers:
- **Break silently** — DocuSign `templateRoles: [{roleName, email, name}]` → Composio sends `[{}]`
- **Lose data** — Python repr instead of JSON, nested objects dropped
- **Version hell** — `composio-client>=1.39.0` requires Python 3.13, but your server runs 3.12
- **Limit tools** — default 20 tools returned, no way to know what's missing
- **Add latency** — your server → their server → API → back

**anyapi takes a different approach:**

| Layer | What | Who |
|-------|------|-----|
| **Auth** | OAuth, token refresh, storage | **Nango** (700+ apps) |
| **Knowledge** | Curated API specs (params, paths, descriptions) | **anyapi** |
| **Execution** | Build HTTP request, handle quirks, parse response | **anyapi** |

No intermediate wrappers. What the LLM constructs is what the API receives.

## Install

```bash
pip install anyapi                    # Core
pip install anyapi[langchain]         # + LangChain tools
pip install anyapi[all]               # Everything
```

Or from git:
```bash
pip install git+https://github.com/ayudo-ai/anyapi.git
```

Or install locally (for development):
```bash
pip install -e /path/to/anyapi[all]
```

## Supported Apps — 49 Actions

| App | Actions | Auth | Status |
|-----|---------|------|--------|
| **Gmail** | 7 — send, search, get, thread, reply, labels, modify | OAuth2 (Google) | ✅ Live tested |
| **Google Sheets** | 2 — append row, read range | OAuth2 (Google) | ✅ |
| **Google Drive** | 2 — list files, get file | OAuth2 (Google) | ✅ |
| **DocuSign** | 6 — create envelope, get status, list, recipients, void, resend | OAuth2 | ✅ Live tested |
| **Freshdesk** | 10 — create/get/update/delete ticket, reply, note, list, search, conversations, agents | API Key | ✅ |
| **Slack** | 7 — send/update message, channels, history, thread, reaction, lookup user | OAuth2 | ✅ |
| **HubSpot** | 15 — contacts, companies, deals (CRUD + search), notes, associations, owners | OAuth2 | ✅ |

## Two Modes

### Mode 1: Nango (Recommended)

Nango handles OAuth for 700+ apps. You configure integrations in Nango's dashboard, then anyapi calls APIs through Nango's proxy (which auto-injects tokens).

```python
from anyapi import AnyAPI

api = AnyAPI(nango_secret_key="nango-secret-xxx")

# Check connection
connected = await api.is_connected("google", "workspace-123")

# Call API
result = await api.call("gmail_search", connection_id="workspace-123", q="from:vendor@example.com is:unread")

# Get LangChain tools
tools = api.get_tools("google", connection_id="workspace-123")
```

### Mode 2: Standalone

Manage OAuth yourself. Bring your own token store.

```python
from anyapi import AnyAPI, MemoryTokenStore, AppCredentials

api = AnyAPI(token_store=MemoryTokenStore())

api.register_app(AppCredentials(
    app="google",
    client_id="xxx.apps.googleusercontent.com",
    client_secret="GOCSPX-xxx",
    scopes=["https://www.googleapis.com/auth/gmail.send"],
    redirect_uri="http://localhost:8000/oauth/callback",
))

# Start OAuth flow
auth_url = await api.get_auth_url("google", connection_id="user-123")
# → redirect user to auth_url

# Handle callback
tokens = await api.handle_callback("google", code="xxx", state="xxx")

# Now call APIs
result = await api.call("gmail_send_email", connection_id="user-123", to="...", subject="...", body="...")
```

## LangChain Integration

```python
from anyapi import AnyAPI

api = AnyAPI(nango_secret_key="xxx")

# Get tools for one app
gmail_tools = api.get_tools("google", connection_id="workspace-123")

# Get tools for specific actions only
send_tools = api.get_tools("google", connection_id="workspace-123", actions=["gmail_send_email", "gmail_search"])

# Get tools for multiple apps
all_tools = api.get_all_tools(connection_id="workspace-123", apps=["google", "slack", "freshdesk"])

# Use with LangChain
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o")
llm_with_tools = llm.bind_tools(all_tools)
```

## Triggers (Event Detection)

Poll-based triggers that detect new events and POST to your webhook:

```python
from anyapi import AnyAPI, TriggerEngine, MemoryTriggerStore, TriggerConfig

api = AnyAPI(nango_secret_key="xxx")
engine = TriggerEngine(api=api, store=MemoryTriggerStore())

# Watch for new emails from a vendor
await engine.register(TriggerConfig(
    id="t1",
    trigger_type="gmail_new_message",
    provider="google",
    connection_id="workspace-123",
    webhook_url="https://your-app.com/api/webhook/trigger",
    filters={"from_contains": "vendor@example.com"},
    poll_interval_seconds=90,
))

# Start background polling
await engine.start()  # Runs forever, delivers events to webhook_url
```

Webhook payload:
```json
{
    "trigger_id": "t1",
    "trigger_type": "gmail_new_message",
    "provider": "google",
    "connection_id": "workspace-123",
    "data": {
        "message_id": "18f3a2b...",
        "thread_id": "18f3a2b...",
        "from": "vendor@example.com",
        "to": "you@company.com",
        "subject": "Updated Invoice #1234",
        "snippet": "Please find attached..."
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

## Discovery

```python
# List all available actions
AnyAPI.list_actions()
# → [{"name": "gmail_send_email", "app": "google", "method": "POST", "params": ["to", "subject", "body"]}, ...]

# List actions for one app
AnyAPI.list_actions("freshdesk")
# → 10 Freshdesk actions

# Override Nango provider mapping
api.set_provider_mapping("docusign", "docusign-prod")
```

## Adding a New App

1. **`apps/registry.py`** — Add `AppConfig` (OAuth URLs, base URL)
2. **`specs/newapp.py`** — Write `ActionSpec` for each endpoint (~15 lines each)
3. **`client.py`** — Import and register specs
4. **`executor.py`** — Add `_build_*` method only if the API has payload quirks
5. **`tests/test_core.py`** — Add tests

## Architecture

```
┌─────────────────────────────────────────────┐
│  Your AI Agent (LangChain / CrewAI / raw)   │
│                                             │
│  tools = api.get_tools("google", conn_id)   │
│  result = await api.call("gmail_send_email")│
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │   anyapi client   │
         │                   │
         │  Spec Registry    │  ← 49 curated ActionSpecs
         │  Provider Mapping │  ← app slug → Nango key
         └─────────┬─────────┘
                   │
         ┌─────────▼─────────┐
         │   API Executor    │
         │                   │
         │  Build URL/path   │
         │  Build query      │
         │  Build body       │  ← request_transforms for quirky APIs
         │  Extract IDs      │  ← response_ids mapping
         └─────────┬─────────┘
                   │
         ┌─────────▼─────────┐         ┌──────────────┐
         │  Nango Proxy      │────────▶│  Real API    │
         │  (auth injection) │◀────────│  (Gmail etc) │
         └───────────────────┘         └──────────────┘
```

## License

MIT
