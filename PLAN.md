# Anytool — World-Class Plan

**Goal:** Make anytool production-grade, fully replace Pipedream inside Ayudo, and deploy to `anytool.ayudo.ai`.

---

## Current State

| Area | Status |
|------|--------|
| SDK | 98 actions, 8 providers, 3 modes (platform/standalone/nango) |
| Server | 33 endpoints, 10 routers, rate limiting, billing stubs |
| Dashboard | 11 pages, dark mode, shadcn |
| Ayudo integration | `AnyToolProvider` exists but still uses **Nango for auth** |
| Production auth | **Not ready** — still depends on Nango secret key |
| Pipedream | Still the **primary path** in task engine (`app_tools.py`) |

---

## Phase 1: Make Anytool Self-Sufficient (Week 1)

**Goal:** Anytool handles its own OAuth end-to-end. No Nango. No Pipedream.

### 1.1 Deploy Anytool Server to EC2

- [ ] Generate stable `ANYTOOL_TOKEN_KEY` (Fernet key for token encryption)
- [ ] Create `anytool` schema in existing `metadb` PostgreSQL
- [ ] Pull repo to EC2, create venv, install deps
- [ ] Run seed script: `python -m server.scripts.seed_system_objects`
- [ ] Create systemd service: `uvicorn server.main:app --port 8100`
- [ ] Env vars: `DATABASE_URL`, `ANYTOOL_TOKEN_KEY`, `ANYTOOL_WEBHOOK_SECRET`, Google OAuth creds
- [ ] Smoke test: `curl https://anytool.ayudo.ai/v1/health`

### 1.2 Deploy Dashboard to CloudFront

- [ ] S3 bucket: `anytool-dashboard-prod`
- [ ] ACM cert for `anytool.ayudo.ai`
- [ ] CloudFront distribution:
  - Default behavior → S3 (dashboard)
  - `/v1/*` → EC2:8100 (API)
- [ ] Route 53 CNAME: `anytool.ayudo.ai` → CloudFront
- [ ] `npm run build` → upload `dist/` to S3 → invalidate CloudFront
- [ ] Google Cloud Console: add `anytool.ayudo.ai` to authorized origins + redirect URIs

### 1.3 Create Ayudo's Workspace + API Key

- [ ] Sign in to `anytool.ayudo.ai` with Google SSO
- [ ] Default workspace auto-created
- [ ] Generate API key: `at_xxx` (this is what Ayudo's backend will use)
- [ ] Configure auth configs for all 8 providers (use existing Google/Slack/GitHub/HubSpot OAuth apps)
- [ ] Test: connect a user, execute an action via API key

---

## Phase 2: Replace Pipedream in Ayudo (Week 2)

**Goal:** Every action in Ayudo goes through anytool. Pipedream is dead code.

### 2.1 Switch AnyToolProvider to Platform Mode

Current (`_provider_anytool.py`):
```python
# Uses nango_secret_key — talks to Nango for auth
self._api = AnyTool(nango_secret_key=nango_secret_key)
```

New:
```python
# Uses API key — talks to anytool platform for everything
self._api = AnyTool(api_key="at_xxx", base_url="https://anytool.ayudo.ai/v1")
```

Changes needed:
- [ ] Update `_provider_anytool.py` → use `AnyTool(api_key=...)` instead of `AnyTool(nango_secret_key=...)`
- [ ] Update `app_provider.py` → check `ANYTOOL_API_KEY` env var instead of `NANGO_SECRET_KEY`
- [ ] Update `core/config.py` → add `ANYTOOL_API_KEY` and `ANYTOOL_BASE_URL` settings
- [ ] Remove Nango dependency from Ayudo's `requirements.txt`

### 2.2 Replace Pipedream app_tools.py

Current: Task engine has TWO action execution paths:
1. `app_tools.py` → Pipedream Connect API (primary, used by task engine)
2. `_provider_anytool.py` → anytool SDK (used by some flows)

Plan:
- [ ] Make `_provider_anytool.py` the ONLY execution path
- [ ] Delete or deprecate `app_tools.py` Pipedream code
- [ ] Update task engine `build_tools()` to always use AnyToolProvider
- [ ] Map Pipedream component keys to anytool action names:
  ```
  gmail-send-email        → gmail_send_email
  slack-send-message      → slack_send_message
  google_sheets-add-row   → sheets_append_row
  hubspot-create-contact  → hubspot_create_contact
  ```
- [ ] Add backward-compat mapping for existing playbooks that store Pipedream component keys

### 2.3 Replace Pipedream OAuth Flow

Current: Ayudo's frontend (`/connect/{app_slug}`) generates Pipedream connect tokens for user OAuth.

New:
- [ ] Update `app_integrations_router.py` → call anytool's `POST /v1/connections/connect` instead of Pipedream
- [ ] Update frontend connect flow → redirect to anytool's OAuth URL
- [ ] Callback lands back on anytool → token stored in anytool's encrypted store
- [ ] Ayudo reads connection status from anytool API

### 2.4 Replace Pipedream Triggers

Current: Pipedream deployed triggers for webhooks (new email, new Slack message, etc.)

New:
- [ ] Use anytool's 8 trigger types (already built)
- [ ] Update `deploy_trigger()` in `_provider_anytool.py` to use anytool platform API
- [ ] Webhook delivery: anytool → Ayudo's webhook endpoint → task engine resumes

### 2.5 Clean Up

- [ ] Remove `PIPEDREAM_*` env vars from Ayudo's config
- [ ] Remove `pipedream` from Ayudo's `requirements.txt`
- [ ] Remove `app/routers/pipedream.py` (or keep as legacy redirect)
- [ ] Remove `app/services/workflow_services/pipedream_auth.py`
- [ ] Remove Pipedream connect token generation code
- [ ] Update all tests referencing Pipedream

---

## Phase 3: Expand Action Coverage (Week 3)

**Goal:** Match what Ayudo playbooks need. Cover the top 20 apps customers use.

### Current: 98 actions, 8 providers

### Priority additions (based on Ayudo playbook usage):

| Provider | Actions Needed | Priority |
|----------|---------------|----------|
| **Google Calendar** | create_event, list_events, update_event, delete_event | P0 — used in scheduling playbooks |
| **Google Drive** | upload_file, list_files, create_folder, share_file | P0 — used in document playbooks |
| **Google Docs** | create_doc, get_doc, append_text | P1 |
| **Notion** | create_page, update_page, query_database, create_database | P1 — popular with customers |
| **Jira** | create_issue, update_issue, list_issues, add_comment, transition_issue | P1 — dev teams |
| **Salesforce** | create_lead, update_opportunity, search_records, create_task | P1 — sales teams |
| **Asana** | create_task, update_task, list_tasks, add_comment | P2 |
| **Trello** | create_card, move_card, add_comment | P2 |
| **Airtable** | create_record, update_record, list_records | P2 |
| **Intercom** | create_conversation, reply, tag_contact | P2 |
| **Shopify** | list_orders, update_order, create_product | P2 |
| **Stripe** | create_invoice, list_payments, create_customer | P2 |

Target: **150+ actions, 15+ providers** by end of week 3.

### How to add a new provider:

1. Create `anytool/specs/{provider}.py` with `ActionSpec` definitions
2. Add OAuth config to `anytool/apps/registry.py`
3. Add provider mapping to `server/engine.py`
4. Add default scopes to `server/routers/auth_configs.py` providers list
5. Test: connect → execute → verify response

---

## Phase 4: Production Hardening (Week 4)

### 4.1 Token Refresh

- [ ] Automatic OAuth token refresh before expiry (Google tokens expire in 1 hour)
- [ ] Refresh token rotation handling (some providers invalidate old refresh tokens)
- [ ] Token health monitoring — alert if refresh fails 3x
- [ ] Graceful degradation — return clear error to task engine if token is dead

### 4.2 Error Handling & Retries

- [ ] Retry on 429 (rate limit) with Retry-After header respect
- [ ] Retry on 5xx with exponential backoff (max 3 attempts)
- [ ] Circuit breaker per provider — if 10 consecutive failures, pause for 60s
- [ ] Structured error responses: `{error, provider, action, retryable, details}`

### 4.3 Logging & Observability

- [ ] Every action execution logged with: action, provider, user_id, latency_ms, status, error
- [ ] Dashboard: real-time execution logs with filtering
- [ ] Alert on error rate spike (>10% failure rate per provider)
- [ ] Latency tracking per provider per action

### 4.4 Security

- [ ] Rotate `ANYTOOL_TOKEN_KEY` without downtime (dual-key decryption)
- [ ] Audit log: who connected what, who executed what, when
- [ ] IP allowlist option for API keys
- [ ] Token scoping: API key can be restricted to specific providers/actions

### 4.5 Performance

- [ ] Connection pooling for outbound HTTP (reuse connections per provider)
- [ ] Response caching for read-only actions (list_contacts, get_ticket) — 60s TTL
- [ ] Batch execution endpoint: `POST /v1/execute/batch` — run multiple actions in parallel
- [ ] Async execution: `POST /v1/execute/async` → returns job_id → poll for result

---

## Phase 5: Make It World-Class (Week 5+)

### 5.1 Developer Experience

- [ ] Interactive API docs at `anytool.ayudo.ai/docs` (Swagger is already there via FastAPI)
- [ ] SDK quickstart: 5 lines from `pip install` to first action executed
- [ ] Code examples for every action in the dashboard
- [ ] Webhook testing tool: send a test webhook from the dashboard
- [ ] Connection testing: "Test this connection" button that runs a lightweight action

### 5.2 Smart Action Discovery

- [ ] `POST /v1/actions/search` — natural language search: "send an email" → `gmail_send_email`
- [ ] Action recommendations based on connected apps
- [ ] Parameter autofill from context (e.g., auto-suggest email fields from connection metadata)

### 5.3 Composite Actions

- [ ] Chain multiple actions: "Create HubSpot contact AND send welcome email" as one call
- [ ] Template actions: pre-configured action chains for common workflows
- [ ] Conditional execution: "Send email IF HubSpot contact exists, ELSE create contact first"

### 5.4 Sync Engine (Future — Nango's Strength)

- [ ] Polling-based sync: "Sync all HubSpot contacts every 5 minutes"
- [ ] Incremental sync with cursor/timestamp tracking
- [ ] Webhook-based sync: instant updates when provider supports webhooks
- [ ] Sync status dashboard: last sync time, record count, errors
- [ ] This is the hardest part. Consider partnering with Nango for this if the job/integration happens.

### 5.5 Multi-Region

- [ ] Deploy anytool server to multiple regions (US, EU)
- [ ] Route requests to nearest region
- [ ] Data residency: EU customers' tokens stored in EU only

---

## Migration Checklist (Pipedream → Anytool)

### Before flipping the switch:

- [ ] Every Pipedream action currently used in production playbooks has an anytool equivalent
- [ ] All connected accounts re-authorized through anytool OAuth
- [ ] Existing playbooks' `componentKey` fields mapped to anytool action names
- [ ] Task engine integration tested end-to-end for each provider:
  - [ ] Gmail: send, reply, list, search
  - [ ] Slack: send message, list channels
  - [ ] Google Sheets: append row, read rows
  - [ ] HubSpot: create/update contact, create deal
  - [ ] DocuSign: create envelope, send for signature
  - [ ] Freshdesk: create/update ticket
  - [ ] Zendesk: create/update ticket
  - [ ] GitHub: create issue, create PR
- [ ] Triggers re-deployed through anytool
- [ ] Rollback plan: keep Pipedream config for 2 weeks, feature flag to switch back

### After the switch:

- [ ] Monitor error rates for 48 hours
- [ ] Remove Pipedream code after 2 weeks of stable operation
- [ ] Cancel Pipedream subscription
- [ ] Update SDK default base_url to `https://anytool.ayudo.ai/v1`
- [ ] Publish anytool v0.2.0 to PyPI

---

## Timeline Summary

| Week | Phase | Outcome |
|------|-------|---------|
| 1 | Deploy anytool to production | `anytool.ayudo.ai` live, dashboard working, OAuth flowing |
| 2 | Replace Pipedream in Ayudo | All actions go through anytool, Pipedream disabled |
| 3 | Expand to 15+ providers | 150+ actions, covers all Ayudo playbook needs |
| 4 | Production hardening | Token refresh, retries, monitoring, security |
| 5+ | World-class features | Search, composites, syncs, multi-region |

**Pipedream bill stops: End of Week 2.**
