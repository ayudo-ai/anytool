# anytool

**Agent-native API integration SDK. Curated specs. Direct execution. Zero wrappers.**

Give your AI agent curated API specs + OAuth tokens — it calls any API directly.

## Quick Start

```python
from anytool import AnyTool

api = AnyTool(nango_secret_key="nango-secret-xxx")

# Call any API by action name
result = await api.call(
    "gmail_send_email",
    connection_id="workspace-123",
    to="vendor@example.com",
    subject="Invoice Follow-up",
    body="Hi, please send the updated invoice.",
)
# → {"data": {"id": "msg-123", "threadId": "thread-456"}, "successful": True, "extracted_ids": {"message_id": "msg-123", "thread_id": "thread-456"}}

# Get LangChain tools for an app
tools = api.get_tools("google", connection_id="workspace-123")
# → [gmail_send_email, gmail_search, gmail_get_thread, sheets_append_row, ...]

# Or get tools for ALL apps at once
all_tools = api.get_all_tools(connection_id="workspace-123")
# → 49 tools across 5 apps, ready for llm.bind_tools()
```

## The Problem

Existing integration platforms pre-build wrappers for each API action. These wrappers:

- **Drop nested data** — complex payloads like `templateRoles: [{roleName, email, name}]` arrive at the API as `[{}]`
- **Break across versions** — SDK updates introduce Python version incompatibilities that crash your production server
- **Return non-standard formats** — responses come back as Python repr strings instead of JSON, requiring custom parsing
- **Silently limit results** — only 20 tools returned by default, with no indication that actions are missing
- **Add unnecessary latency** — every request routes through a third-party proxy before reaching the actual API

## How anytool Works

| Layer | What | How |
|-------|------|-----|
| **Auth** | OAuth, token refresh, storage | **Nango** (700+ apps, open-source) |
| **Knowledge** | Curated API specs — params, paths, descriptions | **anytool specs** (~15 lines per action) |
| **Execution** | Build HTTP request, handle API quirks, parse response | **anytool executor** (direct HTTP) |

No intermediate wrappers. No serialization layers. What the LLM constructs is what the API receives.

## Install

```bash
pip install anytool                    # Core (httpx + pydantic + loguru)
pip install anytool[langchain]         # + LangChain tool generation
```

## Supported Apps — 49 Actions

| App | Actions | Auth |
|-----|---------|------|
| **Gmail** | 7 — send, search, get, thread, reply, labels, modify | OAuth2 |
| **Google Sheets** | 2 — append row, read range | OAuth2 |
| **Google Drive** | 2 — list files, get file | OAuth2 |
| **DocuSign** | 6 — create envelope, get status, list, recipients, void, resend | OAuth2 |
| **Freshdesk** | 10 — create/get/update/delete ticket, reply, note, list, search, conversations, agents | API Key |
| **Slack** | 7 — send/update message, channels, history, thread, reaction, lookup user | OAuth2 |
| **HubSpot** | 15 — contacts, companies, deals (CRUD + search), notes, associations, owners | OAuth2 |

## Two Modes

### Mode 1: Nango (Recommended)

[Nango](https://nango.dev) handles OAuth for 700+ apps. anytool calls APIs through Nango's proxy which auto-injects tokens.

```python
from anytool import AnyTool

api = AnyTool(nango_secret_key="nango-secret-xxx")

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
from anytool import AnyTool, MemoryTokenStore, AppCredentials

api = AnyTool(token_store=MemoryTokenStore())

api.register_app(AppCredentials(
    app="google",
    client_id="xxx.apps.googleusercontent.com",
    client_secret="GOCSPX-xxx",
    scopes=["https://www.googleapis.com/auth/gmail.send"],
    redirect_uri="http://localhost:8000/oauth/callback",
))

# Start OAuth flow
auth_url = await api.get_auth_url("google", connection_id="user-123")

# Handle callback
tokens = await api.handle_callback("google", code="xxx", state="xxx")

# Call APIs
result = await api.call("gmail_send_email", connection_id="user-123", to="...", subject="...", body="...")
```

## LangChain Integration

```python
from anytool import AnyTool

api = AnyTool(nango_secret_key="xxx")

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
from anytool import AnyTool, TriggerEngine, MemoryTriggerStore, TriggerConfig

api = AnyTool(nango_secret_key="xxx")
engine = TriggerEngine(api=api, store=MemoryTriggerStore())

await engine.register(TriggerConfig(
    id="t1",
    trigger_type="gmail_new_message",
    provider="google",
    connection_id="workspace-123",
    webhook_url="https://your-app.com/api/webhook/trigger",
    filters={"from_contains": "vendor@example.com"},
    poll_interval_seconds=90,
))

await engine.start()
```

## Adding a New App

1. **`apps/registry.py`** — Add `AppConfig` (OAuth URLs, base URL)
2. **`specs/newapp.py`** — Write `ActionSpec` per endpoint (~15 lines each)
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
         │  anytool client   │
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
         │  Build body       │  ← request transforms for quirky APIs
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
