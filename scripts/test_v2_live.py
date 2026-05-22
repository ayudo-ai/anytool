#!/usr/bin/env python3
"""
Live test — v2 engine against real Gmail and Slack APIs.

Run:
    python scripts/test_v2_live.py

    # Gmail only:
    python scripts/test_v2_live.py --gmail

    # Slack only:
    python scripts/test_v2_live.py --slack

    # Specify redirect port (must match Google Cloud Console):
    python scripts/test_v2_live.py --port 8000

Flow:
    1. OAuth for Google (opens browser)
    2. Send a test email via v2 engine
    3. OAuth for Slack (opens browser)
    4. Send a test message via v2 engine

Requires .env with:
    GOOGLE_OAUTH_CLIENT_ID=xxx
    GOOGLE_OAUTH_CLIENT_SECRET=xxx
    SLACK_CLIENT_ID=xxx
    SLACK_CLIENT_SECRET=xxx
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

# ── Load .env ────────────────────────────────────────────────────────

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))

from anytool import AnyTool, MemoryTokenStore, AppCredentials
from anytool.core.engine import Engine
from anytool.core.executor import AuthTokens
from anytool.core.auth_bridge import AuthBridge

# ── Config ───────────────────────────────────────────────────────────

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID", "")
SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET", "")
TEST_EMAIL = os.environ.get("TEST_EMAIL", "")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")
USER_ID = "test-user-v2"

# ── OAuth Callback Server ────────────────────────────────────────────

_oauth_result = {}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/oauth/callback":
            params = parse_qs(parsed.query)
            _oauth_result["code"] = params.get("code", [""])[0]
            _oauth_result["state"] = params.get("state", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body style='font-family:system-ui;text-align:center;padding:60px'>"
                             b"<h1>&#9989; Connected!</h1><p>Return to terminal.</p></body></html>")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


def find_free_port(preferred: int) -> int:
    """Use preferred port if free, otherwise find a free one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", preferred)) != 0:
            return preferred
    # Port in use — find a free one
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


# ── OAuth Flow ───────────────────────────────────────────────────────

async def do_oauth(api: AnyTool, provider: str, port: int) -> bool:
    """Run OAuth. Returns True on success."""
    _oauth_result.clear()

    # Already connected?
    if await api.is_connected(provider, USER_ID):
        print(f"  ✅ Already connected to {provider}")
        return True

    # Start server
    server = HTTPServer(("localhost", port), CallbackHandler)
    Thread(target=server.handle_request, daemon=True).start()

    # Open browser
    auth_url = await api.get_auth_url(provider, connection_id=USER_ID)
    print(f"  🌐 Opening browser for {provider} OAuth...")
    print(f"     Redirect: http://localhost:{port}/oauth/callback")
    print(f"     (Make sure this URI is in your OAuth app settings!)")
    webbrowser.open(auth_url)

    # Wait
    print(f"  ⏳ Waiting for authorization...")
    for _ in range(120):
        await asyncio.sleep(1)
        if "code" in _oauth_result:
            break
    else:
        print(f"  ❌ Timeout")
        return False

    # Exchange
    try:
        tokens = await api.handle_callback(provider, _oauth_result["code"], _oauth_result["state"])
        print(f"  ✅ {provider} connected!")
        if tokens.metadata:
            for k, v in tokens.metadata.items():
                print(f"     {k}: {v}")
        return True
    except Exception as e:
        print(f"  ❌ OAuth failed: {e}")
        return False


# ── Test Functions ───────────────────────────────────────────────────

async def test_gmail(engine: Engine, bridge: AuthBridge, store: MemoryTokenStore):
    """Test gmail_send_email through v2 engine."""
    print(f"\n{'='*60}")
    print("  📧 TEST: Gmail Send Email")
    print(f"{'='*60}")

    # Resolve recipient
    tokens = await store.get_tokens("google", USER_ID)
    user_email = tokens.metadata.get("email", "") if tokens else ""
    to = TEST_EMAIL or user_email
    if not to:
        to = input("  Enter email to send test to: ").strip()
    if not to:
        print("  ❌ No recipient. Skipping.")
        return False

    # Get auth
    auth = await bridge.get_auth("google", USER_ID)

    # Build params — this is what the LLM would construct
    body = {
        "to": to,
        "subject": "anytool v2 live test 🚀",
        "body": (
            "This email was sent through anytool's v2 spec-first engine.\n\n"
            "What happened:\n"
            "  1. LLM constructed: {to, subject, body}\n"
            "  2. gmail_mime encoder: → base64url MIME message\n"
            "  3. Executor: POST to Gmail API\n\n"
            "No wrappers. No intermediate models. No data loss.\n\n"
            "— anytool v2"
        ),
    }

    print(f"\n  To: {to}")
    print(f"  Subject: {body['subject']}")
    print(f"  Encoder: gmail_mime (Tier 3)")
    print(f"  Executing...")

    result = await engine.execute("gmail_send_email", body, auth)

    print(f"\n  Status: {result.status_code} | {result.duration_ms}ms")
    if result.successful:
        print(f"  Message ID: {result.extracted_ids.get('message_id', '?')}")
        print(f"  ✅ GMAIL PASSED")
        return True
    else:
        print(f"  Error: {result.error}")
        if result.data:
            print(f"  Response: {json.dumps(result.data, indent=2)[:500]}")
        print(f"  ❌ GMAIL FAILED")
        return False


async def test_slack(engine: Engine, bridge: AuthBridge):
    """Test slack_send_message through v2 engine."""
    print(f"\n{'='*60}")
    print("  💬 TEST: Slack Send Message")
    print(f"{'='*60}")

    channel = SLACK_CHANNEL
    if not channel:
        channel = input("  Enter Slack channel ID (e.g. C0123456789): ").strip()
    if not channel:
        print("  ❌ No channel. Skipping.")
        return False

    # Get auth
    auth = await bridge.get_auth("slack", USER_ID)

    # Build params — this is the EXACT body Slack API receives (Tier 1 pass-through)
    body = {
        "channel": channel,
        "text": (
            "🚀 *anytool v2 live test*\n\n"
            "This message was sent through the v2 spec-first engine.\n"
            "• Spec: `registry/slack/send_message.yaml`\n"
            "• Tier 1: body sent AS-IS to Slack API\n"
            "• No wrappers, no transforms"
        ),
    }

    print(f"\n  Channel: {channel}")
    print(f"  Body passes through unchanged (Tier 1)")
    print(f"  Executing...")

    result = await engine.execute("slack_send_message", body, auth)

    print(f"\n  Status: {result.status_code} | {result.duration_ms}ms")
    if result.successful:
        # Slack returns ok=true in the data
        data = result.data or {}
        if data.get("ok"):
            print(f"  Message TS: {result.extracted_ids.get('message_ts', data.get('ts', '?'))}")
            print(f"  ✅ SLACK PASSED")
            return True
        else:
            print(f"  Slack error: {data.get('error', 'unknown')}")
            print(f"  ❌ SLACK FAILED (Slack API returned ok=false)")
            return False
    else:
        print(f"  Error: {result.error}")
        if result.data:
            print(f"  Response: {json.dumps(result.data, indent=2)[:500]}")
        print(f"  ❌ SLACK FAILED")
        return False


# ── Main ─────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="anytool v2 live test")
    parser.add_argument("--gmail", action="store_true", help="Test Gmail only")
    parser.add_argument("--slack", action="store_true", help="Test Slack only")
    parser.add_argument("--port", type=int, default=8000, help="OAuth callback port (default: 8000)")
    args = parser.parse_args()

    test_both = not args.gmail and not args.slack
    do_gmail = args.gmail or test_both
    do_slack = args.slack or test_both

    # Find port
    port = find_free_port(args.port)
    if port != args.port:
        print(f"⚠️  Port {args.port} in use. Using {port} instead.")
        print(f"   Add http://localhost:{port}/oauth/callback to your Google Cloud Console!")
    redirect_uri = f"http://localhost:{port}/oauth/callback"

    print("=" * 60)
    print("  anytool v2 — Live Test")
    print(f"  Callback: {redirect_uri}")
    print("=" * 60)

    # Setup
    store = MemoryTokenStore()
    api = AnyTool(token_store=store)

    if do_gmail:
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            print("❌ Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env")
            return
        api.register_app(AppCredentials(
            app="google",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=[
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/userinfo.email",
            ],
            redirect_uri=redirect_uri,
        ))

    if do_slack:
        if not SLACK_CLIENT_ID or not SLACK_CLIENT_SECRET:
            print("❌ Set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET in .env")
            return
        api.register_app(AppCredentials(
            app="slack",
            client_id=SLACK_CLIENT_ID,
            client_secret=SLACK_CLIENT_SECRET,
            scopes=["chat:write", "channels:read"],
            redirect_uri=redirect_uri,
        ))

    engine = Engine(registry_path=Path(__file__).parent.parent / "registry")
    bridge = AuthBridge(oauth_manager=api._oauth, credentials=api._credentials)

    print(f"\n  Engine: {len(engine.registry)} specs, {len(engine.list_apps())} apps")

    results = {}

    # Gmail
    if do_gmail:
        print(f"\n{'─'*50}")
        print(f"  Step 1: Connect Google")
        print(f"{'─'*50}")
        if await do_oauth(api, "google", port):
            results["gmail"] = await test_gmail(engine, bridge, store)
        else:
            results["gmail"] = False

    # Slack
    if do_slack:
        print(f"\n{'─'*50}")
        print(f"  Step 2: Connect Slack")
        print(f"{'─'*50}")
        if await do_oauth(api, "slack", port):
            results["slack"] = await test_slack(engine, bridge)
        else:
            results["slack"] = False

    # Summary
    print(f"\n{'='*60}")
    print("  Results")
    print(f"{'='*60}")
    for test, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test}: {status}")
    print()

    await api.close()


if __name__ == "__main__":
    asyncio.run(main())
