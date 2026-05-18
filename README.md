# anyapi

**Agent-native API execution. No wrappers. No Composio. No Pipedream.**

Give your AI agent OAuth tokens and API specs — it calls any API directly.

```python
from anyapi import AnyAPI

api = AnyAPI(token_store=your_db)

# Connect an app (one-time OAuth)
auth_url = api.get_auth_url("google", scopes=["gmail.send", "gmail.readonly"])
# User completes OAuth → tokens stored automatically

# Agent calls any API — no pre-built wrappers
tools = api.get_tools("google")  # Returns LangChain tools
# Tools: gmail_send_email, gmail_search, gmail_get_thread, sheets_append_row, ...

# Or go raw
result = await api.call(
    app="google",
    action="gmail.send",
    params={"to": "vendor@example.com", "subject": "Follow-up", "body": "..."}
)
```

## Why

Every integration platform (Composio, Pipedream, Nango) pre-builds wrappers for each API. These wrappers:
- Break when APIs change
- Lose nested data (DocuSign `templateRoles: [{}]` bug)
- Silently truncate results (20 tool limit)
- Return non-standard formats (Python repr instead of JSON)
- Add latency (your server → their server → API → back)
- Cost money per execution

**anyapi takes a different approach.** Instead of human-built wrappers, it gives your AI agent:
1. **OAuth tokens** — managed, auto-refreshed, per-user
2. **API knowledge** — curated specs the agent can understand
3. **A direct HTTP executor** — agent constructs the exact request, anyapi handles auth

## Supported Apps

| App | Auth | Status |
|-----|------|--------|
| Gmail | OAuth2 (Google) | ✅ |
| Google Sheets | OAuth2 (Google) | ✅ |
| Google Drive | OAuth2 (Google) | ✅ |
| Freshdesk | API Key | ✅ |
| DocuSign | OAuth2 | 🚧 |
| Slack | OAuth2 | 🚧 |
| Microsoft (Outlook/Teams) | OAuth2 (Azure AD) | Planned |

## Install

```bash
pip install anyapi
```

## Architecture

```
Your Agent (LangChain / CrewAI / raw)
    │
    ├── api.get_tools("google")     → LangChain StructuredTools
    │   ├── gmail_send_email        → knows Gmail API spec
    │   ├── gmail_search            → knows search params
    │   └── sheets_append_row       → knows Sheets API spec
    │
    ├── api.call(app, action, params)  → direct HTTP call
    │   ├── auto-injects OAuth token
    │   ├── auto-refreshes if expired
    │   └── normalizes response
    │
    └── Token Store (your DB)
        ├── google: {access_token, refresh_token, expiry}
        ├── freshdesk: {api_key, domain}
        └── docusign: {access_token, refresh_token, account_id}
```

## License

MIT
