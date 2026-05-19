# anytool

**Agent-native API integration SDK. Curated specs. Direct execution. Zero wrappers.**

Give your AI agent curated API specs + OAuth tokens — it calls any API directly.

## Quick Start

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

# 1. Start OAuth → redirect user to this URL
auth_url = await api.get_auth_url("google", connection_id="user-123")

# 2. Handle callback → tokens stored + auto-refreshed
tokens = await api.handle_callback("google", code="xxx", state="xxx")

# 3. Call any API by action name
result = await api.call(
    "gmail_send_email",
    connection_id="user-123",
    to="vendor@example.com",
    subject="Invoice Follow-up",
    body="Hi, please send the updated invoice.",
)
# → {"data": {"id": "msg-123", "threadId": "thread-456"}, "successful": True}

# Get LangChain tools for an app
tools = api.get_tools("google", connection_id="user-123")
# → [gmail_send_email, gmail_search, sheets_append_row, ...]

# Or get tools for ALL apps at once
all_tools = api.get_all_tools(connection_id="user-123")
# → 98 tools across 8 apps, ready for llm.bind_tools()
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
| **Auth** | OAuth, token refresh, storage | **Built-in** OAuth manager with pluggable token store |
| **Knowledge** | Curated API specs — params, paths, descriptions | **anytool specs** (~15 lines per action) |
| **Execution** | Build HTTP request, handle API quirks, parse response | **anytool executor** (direct HTTP) |

No intermediate wrappers. No serialization layers. No third-party proxy. What the LLM constructs is what the API receives.

## Install

```bash
pip install anytool                    # Core (httpx + pydantic + loguru)
pip install anytool[langchain]         # + LangChain tool generation
```

## Supported Apps — 98 Actions

| App | Actions | Auth |
|-----|---------|------|
| **Gmail** | 7 — send, search, get, thread, reply, labels, modify | OAuth2 |
| **Google Sheets** | 2 — append row, read range | OAuth2 |
| **Google Drive** | 2 — list files, get file | OAuth2 |
| **Google Calendar** | 6 — list/get/create/update/delete events, list calendars | OAuth2 |
| **Google Docs** | 5 — get/create doc, batch update, insert/replace text | OAuth2 |
| **DocuSign** | 6 — create envelope, get status, list, recipients, void, resend | OAuth2 |
| **Freshdesk** | 10 — create/get/update/delete ticket, reply, note, list, search, conversations, agents | API Key |
| **Slack** | 7 — send/update message, channels, history, thread, reaction, lookup user | OAuth2 |
| **HubSpot** | 15 — contacts, companies, deals (CRUD + search), notes, associations, owners | OAuth2 |
| **GitHub** | 16 — issues, PRs, repos, commits, workflows, branches, search | OAuth2 |
| **Zendesk** | 13 — tickets (CRUD), comments, search, agents, groups, users | OAuth2 |
| **WhatsApp** | 9 — send template/text/image/document, reactions, read receipts | Bearer Token |

## Usage

### Standalone Mode (Recommended)

Full control. Manage OAuth yourself. No third-party dependencies.

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

# Handle callback (after user authorizes)
tokens = await api.handle_callback("google", code="xxx", state="xxx")

# Call APIs — tokens auto-refresh when expired
result = await api.call("gmail_send_email", connection_id="user-123", to="...", subject="...", body="...")
```

### LangChain Integration

```python
from anytool import AnyTool, MemoryTokenStore

api = AnyTool(token_store=MemoryTokenStore())
# ... register apps ...

# Get tools for one app
gmail_tools = api.get_tools("google", connection_id="user-123")

# Get tools for specific actions only
send_tools = api.get_tools("google", connection_id="user-123", actions=["gmail_send_email", "gmail_search"])

# Get tools for multiple apps
all_tools = api.get_all_tools(connection_id="user-123", apps=["google", "slack", "freshdesk"])

# Use with LangChain
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o")
llm_with_tools = llm.bind_tools(all_tools)
```

### Triggers (Event Detection)

Poll-based triggers that detect new events and POST to your webhook:

```python
from anytool import AnyTool, MemoryTokenStore, TriggerEngine, MemoryTriggerStore, TriggerConfig

api = AnyTool(token_store=MemoryTokenStore())
# ... register apps ...

engine = TriggerEngine(api=api, store=MemoryTriggerStore())

await engine.register(TriggerConfig(
    id="t1",
    trigger_type="gmail_new_message",
    provider="google",
    connection_id="user-123",
    webhook_url="https://your-app.com/api/webhook/trigger",
    filters={"from_contains": "vendor@example.com"},
    poll_interval_seconds=90,
))

await engine.start()
```

### Custom Token Store

Implement `TokenStore` for your database:

```python
from anytool.auth.token_store import TokenStore
from anytool.auth.models import UserTokens, OAuthState

class PostgresTokenStore(TokenStore):
    async def save_tokens(self, tokens: UserTokens) -> None:
        # Encrypt and store in your DB
        ...

    async def get_tokens(self, app: str, user_id: str) -> Optional[UserTokens]:
        # Decrypt and return from your DB
        ...

    async def delete_tokens(self, app: str, user_id: str) -> None: ...
    async def list_connected(self, user_id: str) -> list[UserTokens]: ...
    async def save_oauth_state(self, state: OAuthState) -> None: ...
    async def get_oauth_state(self, state_key: str) -> Optional[OAuthState]: ...
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
         │  Spec Registry    │  ← 98 curated ActionSpecs
         │  OAuth Manager    │  ← token refresh, CSRF
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
         ┌─────────▼─────────┐
         │  Direct HTTP      │────────▶  Gmail, Slack,
         │  (auto-injects    │◀────────  HubSpot, etc.
         │   OAuth tokens)   │
         └───────────────────┘
```

## License

MIT
