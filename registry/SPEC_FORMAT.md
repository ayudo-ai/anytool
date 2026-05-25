# Anytool Spec Format

Every API action is described in a single YAML file inside `registry/`.

## Directory Structure

```
registry/
├── SPEC_FORMAT.md          ← this file
├── slack/
│   ├── send_message.yaml
│   ├── update_message.yaml
│   └── list_channels.yaml
├── docusign/
│   ├── create_envelope.yaml
│   └── get_envelope.yaml
├── hubspot/
│   ├── create_contact.yaml
│   └── search_contacts.yaml
├── zendesk/
│   ├── create_ticket.yaml
│   └── add_comment.yaml
└── google/
    ├── gmail/
    │   ├── send_email.yaml       ← has encoder (Tier 3)
    │   └── list_messages.yaml
    └── calendar/
        └── create_event.yaml
```

## The Three Tiers

### Tier 1: Direct Pass-Through (most APIs)
- LLM constructs the exact JSON body from `request.body_schema`
- Executor sends it unchanged
- Example: Slack, GitHub, Freshdesk

### Tier 2: Complex JSON (LLM constructs it, executor sends it)
- Body has nested objects, arrays-of-objects, wrapping
- The body_schema describes the full nesting — LLM constructs it directly
- NO code transforms needed. The spec teaches the LLM the structure.
- Example: DocuSign, HubSpot, Zendesk

### Tier 3: Encoding Required (rare — needs encoder function)
- The API requires non-JSON encoding (MIME, multipart, etc.)
- Spec declares `encoder: gmail_mime` (or similar)
- Spec has `agent_params` (what LLM sees) separate from `request.body_schema` (what API receives)
- A small encoder function bridges them
- Example: Gmail send, file uploads (~5 actions total)

## Spec Fields

```yaml
# ── Required ──────────────────────────────────

name: string           # Unique action name: "slack_send_message"
app: string            # App slug: "slack", "google", "docusign"
description: string    # What this action does (LLM reads this)
method: string         # HTTP method: GET, POST, PUT, PATCH, DELETE
path: string           # URL path with {placeholders}
base_url: string       # API base URL

# ── Auth ──────────────────────────────────────

auth:
  type: string         # oauth2, api_key, bearer
  scopes: [string]     # Required OAuth scopes
  header: string       # How to set the auth header
  inject_from_metadata:  # Path params that come from token metadata
    path_param: metadata_key

# ── Request ───────────────────────────────────

request:
  content_type: string
  body_schema:         # Full JSON Schema of the request body
    type: object
    required: [...]
    properties: {...}  # Nested to any depth — no flattening!

# ── For Tier 3 only (encoder actions) ─────────

encoder: string        # Name of encoder function
agent_params:          # What the LLM sees instead of body_schema
  type: object
  properties: {...}
encoder_spec:          # Documents what the encoder does
  name: string
  logic: string

# ── Response ──────────────────────────────────

response:
  success_codes: [int]
  body_schema:         # JSON Schema of the response
    type: object
    properties: {...}
  extract:             # Fields to extract from response
    friendly_name: json_path

# ── Metadata ──────────────────────────────────

errors:                # Common error codes and explanations
  ERROR_CODE: "Human-readable explanation"

rate_limit:
  requests_per_minute: int
  note: string

tags: [string]         # For semantic search / discovery

examples:              # Real request/response examples
  - name: string
    description: string  # optional
    request: {...}       # or agent_input for Tier 3
    response: {...}

version: string        # API version
```

## Key Design Decisions

### 1. body_schema IS the API spec
The `request.body_schema` describes the EXACT JSON structure the API expects.
No flattening, no simplification. Nested objects stay nested.
This is what the LLM sees. This is what it constructs.
The executor sends it through unchanged.

### 2. Examples are first-class
Every spec MUST have at least one example with a real request/response.
Examples teach LLMs better than descriptions alone.

### 3. Encoders are the exception, not the rule
Only ~5 actions across all APIs need encoders.
If you're writing an encoder for a new action, you're probably
doing it wrong — the LLM should construct the body directly.

### 4. Auth metadata injection is explicit
Path params that come from OAuth metadata (like DocuSign's account_id)
are declared in `auth.inject_from_metadata`. No magic. No guessing.

### 5. YAML files are the source of truth
Not Python code. Not generated code. YAML files that are:
- Version-controlled and diffable
- CI-testable (validate schema, check examples)
- Human-readable and community-contributable
- Auto-generatable from OpenAPI/Discovery docs
```
