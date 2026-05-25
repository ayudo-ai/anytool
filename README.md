# anytool

**Spec-first API execution for AI agents. No wrappers. No data loss.**

anytool lets AI agents call any API through curated YAML specs. The LLM sees the real API schema, constructs the exact request body, and anytool sends it through unchanged. No intermediate models. No serialization bugs. No corrupted payloads.

## Install

```bash
pip install anytool
```

## Two Ways to Use

### 1. Hosted Platform (Recommended)

Use anytool's hosted platform for managed OAuth, encrypted token storage, and zero auth headaches. Sign up at [anytool.dev](https://anytool.dev) to get your API key.

```python
from anytool import AnyTool

at = AnyTool(api_key="at_your_api_key", base_url="https://api.anytool.dev/v1")

# ── Connect a user (OAuth) ──────────────────────────────────────────
auth_url = await at.get_auth_url(
    provider="google",
    connection_id="user-123",
)
# → "https://accounts.google.com/o/oauth2/v2/auth?..."
# After user authorizes, tokens are stored encrypted on the platform.

# ── Execute actions ──────────────────────────────────────────────────
result = await at.call(
    "gmail_send_email",
    connection_id="user-123",
    to="sarah@example.com",
    subject="Invoice Follow-up",
    body="Hi Sarah, please send the updated invoice.",
)
# {"successful": true, "data": {"id": "msg-18f4a5b2c3d4e5f6", "threadId": "..."}}

# Slack
result = await at.call(
    "slack_send_message",
    connection_id="user-123",
    channel="C0123456789",
    text="Hello from anytool! :wave:",
)

# Jira
result = await at.call(
    "jira_create_issue",
    connection_id="user-123",
    fields={
        "project": {"key": "ENG"},
        "summary": "Bug: Login page broken",
        "issuetype": {"name": "Bug"},
    },
)

# Stripe
result = await at.call(
    "stripe_create_customer",
    connection_id="user-123",
    email="sarah@example.com",
    name="Sarah Chen",
)

# Salesforce
result = await at.call(
    "salesforce_query",
    connection_id="user-123",
    q="SELECT Id, Name FROM Contact WHERE Email = 'sarah@example.com'",
)

# Check connection status
connected = await at.is_connected("google", "user-123")

# List all connections
connections = await at.list_connections("user-123")
```

### 2. Self-Hosted (Full Control)

Run everything locally. You manage OAuth tokens yourself.

```python
from anytool import AnyTool, MemoryTokenStore, AppCredentials

at = AnyTool(token_store=MemoryTokenStore())

at.register_app(AppCredentials(
    app="google",
    client_id="your-google-client-id",
    client_secret="your-google-client-secret",
    scopes=["https://www.googleapis.com/auth/gmail.send"],
))

auth_url = await at.get_auth_url(
    provider="google",
    connection_id="user-123",
    callback_url="http://localhost:3000/callback",
)

# After callback:
await at.handle_callback("google", code="4/0Adeu5B...", state="...")

# Same API as hosted mode
result = await at.call(
    "gmail_send_email",
    connection_id="user-123",
    to="sarah@example.com",
    subject="Hello",
    body="Sent via self-hosted anytool!",
)
```

## Use the Engine Directly

For maximum control — no auth management, just specs and execution:

```python
from anytool import Engine, AuthTokens

engine = Engine(registry_path="registry/")

# Discover
engine.list_apps()            # ['google', 'slack', 'jira', 'stripe', ...]
engine.list_actions("slack")  # [{"name": "slack_send_message", ...}, ...]

# Get OpenAI tool definitions
tools = engine.get_openai_tools(app="slack")
# Pass directly to openai.chat.completions.create(tools=tools)

# Get MCP tool definitions
mcp_tools = engine.get_mcp_tools(app="github")

# Execute
result = await engine.execute(
    "slack_send_message",
    body={"channel": "C0123456789", "text": "Hello!"},
    auth=AuthTokens(access_token="xoxb-your-token"),
)
print(result.successful)   # True
print(result.data)         # {"ok": true, "ts": "1716300000.000100"}
print(result.status_code)  # 200
```

## Use with OpenAI

```python
import json
import openai
from anytool import Engine, AuthTokens

engine = Engine()
client = openai.OpenAI()

tools = engine.get_openai_tools(actions=[
    "gmail_send_email",
    "slack_send_message",
    "jira_create_issue",
])

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Send Sarah an email about the invoice"}],
    tools=tools,
)

if response.choices[0].message.tool_calls:
    call = response.choices[0].message.tool_calls[0]
    result = await engine.execute(
        call.function.name,
        body=json.loads(call.function.arguments),
        auth=AuthTokens(access_token="ya29.a0..."),
    )
```

## Use with LangChain

```python
from anytool import Engine, AuthTokens
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

engine = Engine()
auth = AuthTokens(access_token="xoxb-...")

def make_tool(tool_def):
    func = tool_def["function"]
    async def execute(**kwargs):
        result = await engine.execute(func["name"], body=kwargs, auth=auth)
        return result.data if result.successful else f"Error: {result.error}"
    return StructuredTool.from_function(
        coroutine=execute,
        name=func["name"],
        description=func["description"],
    )

tools = [make_tool(t) for t in engine.get_openai_tools(app="slack")]
agent = create_react_agent(ChatOpenAI(model="gpt-4o"), tools)
```

## 225 Specs Across 26 Apps

| App | Actions | Auth | App | Actions | Auth |
|-----|---------|------|-----|---------|------|
| GitHub | 18 | OAuth2 | Stripe | 16 | API Key |
| HubSpot | 15 | OAuth2 | Zendesk | 13 | API Key |
| Jira | 11 | OAuth2 | Freshdesk | 10 | API Key |
| Salesforce | 10 | OAuth2 | Intercom | 10 | Bearer |
| Asana | 9 | OAuth2 | WhatsApp | 9 | API Key |
| Trello | 9 | OAuth | Notion | 8 | Bearer |
| ClickUp | 8 | Bearer | Gmail | 7 | OAuth2 |
| Calendar | 7 | OAuth2 | Drive | 7 | OAuth2 |
| Slack | 7 | OAuth2 | Linear | 7 | Bearer |
| Airtable | 7 | Bearer | Sheets | 6 | OAuth2 |
| DocuSign | 6 | OAuth2 | Twilio | 6 | Basic |
| Monday | 6 | Bearer | Calendly | 6 | Bearer |
| Shopify | 4 | OAuth2 | Docs | 3 | OAuth2 |

## Why Not Composio?

| | Composio | anytool |
|---|---------|---------|
| **Architecture** | Wrapper models over APIs | YAML specs → pass-through execution |
| **Nested payloads** | Corrupted (DocuSign, HubSpot) | Preserved — body goes through AS-IS |
| **Reliability** | Third-party dependency | Self-hosted or hosted, you control uptime |
| **Adding an app** | Request from vendor, wait | Write a YAML spec in 10 minutes |
| **Open source** | Partial | Full — ELv2 license |

## Adding a New App

```bash
# From OpenAPI
python scripts/spec_builder.py openapi https://api.example.com/openapi.json --app myapp --all

# From Google Discovery
python scripts/spec_builder.py google calendar --all

# Validate all specs
python scripts/spec_builder.py validate
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

## Architecture

```
anytool/
├── core/
│   ├── engine.py       # Load specs, execute, generate tool definitions
│   ├── executor.py     # HTTP execution, URL building, type coercion, retries
│   ├── loader.py       # YAML spec loading
│   ├── models.py       # ActionSpec, RequestSpec, ResponseSpec
│   ├── encoders/       # Tier 3 encoders (gmail_mime)
│   └── adapters/       # OpenAI + MCP tool format adapters
├── auth/               # OAuth flows, token storage
├── triggers/           # Polling + webhook triggers
├── apps/registry.py    # OAuth configs per provider
└── client.py           # High-level client (AnyTool class)

registry/               # 225 YAML action specs
scripts/spec_builder.py # Generate specs from OpenAPI / Google Discovery
```

## License

[Elastic License 2.0 (ELv2)](LICENSE) — free to use, self-host, and modify. Cannot be offered as a competing hosted service.
