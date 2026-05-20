# Anytool E2E Test — Gmail Only

**Scope:** Gmail trigger (new email every 60s) + Gmail action (send email). All local. No deployment.

---

## The Developer Flow (What We're Testing)

```
Developer (you, pretending to be a customer):

1. pip install anytool
2. Go to http://localhost:5174 → sign up → get API key
3. Connect Gmail for an end-user via SDK
4. Deploy a trigger: "poll every 60s for new emails"
5. Execute an action: "send an email"
6. See everything in the dashboard UI — logs, connections, triggers
```

---

## What Works Today

| Step | Status | Notes |
|------|--------|-------|
| Server runs on :8100 | ✅ | `python -m server.main` |
| Dashboard runs on :5174 | ✅ | `cd web && npm run dev` |
| Google SSO login | ✅ | Gets session token + API key |
| API key auth | ✅ | `at_xxx` works for all endpoints |
| POST /v1/connections (start OAuth) | ✅ | Returns auth_url |
| OAuth callback | ⚠️ | Needs ngrok — Google won't redirect to `localhost` |
| POST /v1/execute | ✅ | Executes action, logs to DB |
| POST /v1/triggers | ✅ | Deploys trigger, starts polling |
| Trigger engine polls | ✅ | Background loop runs every 5s, checks schedules |
| Webhook delivery | ✅ | POSTs to webhook_url with HMAC |
| Dashboard logs page | ✅ | Shows execute logs |
| Dashboard connections page | ✅ | Shows connected users |
| Dashboard triggers page | ✅ | Shows active triggers |

## What's Missing / Needs Fixing

| Gap | Impact | Fix |
|-----|--------|-----|
| **No "Try Action" in UI** | Can't send email from dashboard | Add execute dialog to Actions page |
| **No "Connect User" in UI** | Can't start OAuth from dashboard | Add connect dialog to Connections page |
| **No trigger poll logs in UI** | Can't see if trigger is polling | Add trigger logs/events to Triggers page |
| **OAuth callback URL** | Google needs HTTPS callback | Use ngrok for local testing |
| **Trigger logs not in usage_log** | Only execute calls logged, not trigger polls | Log trigger events to usage_log too |
| **No webhook log viewer** | Can't see what webhook received | Add webhook logs to Triggers page |

---

## Step-by-Step Fix Plan

### Step 0: Ngrok Setup
- Start ngrok: `ngrok http 8100`
- Get URL like `https://abc123.ngrok-free.app`
- Set `BASE_URL=https://abc123.ngrok-free.app` in `.env`
- Add to Google Cloud Console:
  - Authorized JavaScript origins: `https://abc123.ngrok-free.app`
  - Authorized redirect URIs: `https://abc123.ngrok-free.app/v1/connections/callback`

### Step 1: Add "Connect User" to Connections Page
- Button: "Connect User" → dialog with provider dropdown + user_id input
- Calls `POST /v1/connections` → opens auth_url in new tab
- After callback, connection shows in the table

### Step 2: Add "Try Action" to Actions Page
- Each action card gets a "Try it" button
- Opens dialog with:
  - user_id dropdown (from connected users)
  - Auto-generated form fields from action params
  - "Execute" button → calls `POST /v1/execute`
  - Shows response JSON (success/error)
- Execution immediately visible in Logs page

### Step 3: Add Trigger Deploy from UI
- Triggers page already has deploy — verify it works
- Add: show `last_poll_at` updating in real-time (auto-refresh every 30s)
- Add: trigger event log (recent events delivered by this trigger)

### Step 4: Log Trigger Events to DB
- When trigger engine delivers a webhook, also write to `usage_log` or new `webhook_log`
- Fields: trigger_id, trigger_type, event_data, delivery_status, delivered_at
- Shows up in Logs page

### Step 5: Test the Full Flow
```
1. Open dashboard → sign in
2. Connections page → "Connect User" → provider: gmail, user_id: test-user-1
3. Authorize in Google → redirected back → "Connected!" 
4. Connections page → see test-user-1 : google : active
5. Triggers page → "Deploy Trigger" → gmail_new_message, user_id: test-user-1, poll: 60s
6. Triggers page → see trigger active, last_poll_at updating every 60s
7. Send yourself an email from another account
8. Within 60s: trigger fires → webhook_log shows the event
9. Actions page → gmail_send_email → "Try it" → user_id: test-user-1, to: your@email.com
10. Email arrives → Logs page shows the execution with duration_ms, status
```

---

## Order of Work

1. **Ngrok + OAuth callback** (15 min) — make connect flow work locally
2. **"Connect User" dialog on Connections page** (30 min)
3. **"Try Action" dialog on Actions page** (45 min) — the big one
4. **Trigger poll logging + UI refresh** (30 min)
5. **Full E2E test** (30 min)

**Total: ~2.5 hours**

After this works, we have confidence that:
- OAuth connect → works
- Token storage + refresh → works  
- Action execution → works
- Trigger polling → works
- Everything visible in dashboard → works

Then we add more apps.
