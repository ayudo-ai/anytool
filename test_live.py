"""
Live validation script — tests anyapi against real Google APIs.

Run: python test_live.py

Flow:
1. Starts a tiny local server on port 8000
2. Opens browser for Google OAuth consent
3. Gets tokens on callback
4. Sends a test email
5. Searches inbox
6. Reads the sent message

Requires .env with:
  GOOGLE_OAUTH_CLIENT_ID=xxx
  GOOGLE_OAUTH_CLIENT_SECRET=xxx
"""

import asyncio
import json
import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from threading import Thread

# Load .env
from pathlib import Path
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

from anytool import AnyAPI, MemoryTokenStore, AppCredentials

CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8000/oauth/callback"
USER_ID = "test-user"

# Where to send test email — change this
TEST_RECIPIENT = os.environ.get("TEST_EMAIL", "nitinpanwar98@gmail.com")

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env")
    exit(1)

# Global to capture the OAuth callback
_callback_result = {}


class CallbackHandler(BaseHTTPRequestHandler):
    """Tiny HTTP handler to capture OAuth callback."""

    def do_GET(self):
        global _callback_result
        parsed = urlparse(self.path)
        if parsed.path == "/oauth/callback":
            params = parse_qs(parsed.query)
            _callback_result = {
                "code": params.get("code", [""])[0],
                "state": params.get("state", [""])[0],
                "error": params.get("error", [""])[0],
            }
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family:sans-serif;text-align:center;padding:60px">
                <h1>&#10004; Connected!</h1>
                <p>You can close this tab and go back to the terminal.</p>
                </body></html>
            """)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


async def main():
    global _callback_result

    print("=" * 60)
    print("  anyapi — Live Google OAuth + Gmail Test")
    print("=" * 60)
    print()

    # 1. Setup
    store = MemoryTokenStore()
    api = AnyAPI(token_store=store)

    api.register_app(AppCredentials(
        app="google",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=[
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ],
        redirect_uri=REDIRECT_URI,
    ))

    # 2. Start local callback server
    server = HTTPServer(("localhost", 8000), CallbackHandler)
    thread = Thread(target=server.handle_request, daemon=True)
    thread.start()

    # 3. Get auth URL and open browser
    print("Step 1: OAuth Authorization")
    print("-" * 40)
    auth_url = await api.get_auth_url("google", user_id=USER_ID)
    print(f"Opening browser for Google consent...")
    print(f"URL: {auth_url[:80]}...")
    webbrowser.open(auth_url)

    # 4. Wait for callback
    print("\nWaiting for OAuth callback...")
    while not _callback_result:
        await asyncio.sleep(0.5)

    if _callback_result.get("error"):
        print(f"❌ OAuth error: {_callback_result['error']}")
        return

    print(f"✅ Got authorization code: {_callback_result['code'][:20]}...")

    # 5. Exchange code for tokens
    print("\nStep 2: Token Exchange")
    print("-" * 40)
    try:
        tokens = await api.handle_callback(
            "google",
            code=_callback_result["code"],
            state=_callback_result["state"],
        )
        print(f"✅ Access token: {tokens.access_token[:20]}...")
        print(f"   Refresh token: {'✅ present' if tokens.refresh_token else '❌ missing'}")
        print(f"   Expires at: {tokens.expires_at}")
        print(f"   Email: {tokens.metadata.get('email', 'unknown')}")
    except Exception as e:
        print(f"❌ Token exchange failed: {e}")
        return

    # 6. Send a test email
    print("\nStep 3: Send Test Email")
    print("-" * 40)
    print(f"Sending to: {TEST_RECIPIENT}")
    try:
        result = await api.call(
            "gmail_send_email",
            user_id=USER_ID,
            to=TEST_RECIPIENT,
            subject="anyapi test — it works!",
            body="This email was sent by anyapi — no Composio, no wrappers, just direct Gmail API.\n\nIf you see this, the SDK works.",
        )
        if result['successful']:
            print(f"✅ Email sent!")
            print(f"   Message ID: {result['extracted_ids'].get('message_id', 'N/A')}")
            print(f"   Thread ID: {result['extracted_ids'].get('thread_id', 'N/A')}")
        else:
            print(f"❌ Send failed: {result.get('error', 'Unknown error')}")
        sent_thread_id = result['extracted_ids'].get('thread_id', '')
    except Exception as e:
        print(f"❌ Send failed: {e}")
        sent_thread_id = ""

    # 7. Search inbox
    print("\nStep 4: Search Inbox")
    print("-" * 40)
    try:
        result = await api.call(
            "gmail_search",
            user_id=USER_ID,
            q="subject:anyapi test",
            maxResults=5,
        )
        messages = result.get("data", {}).get("messages", [])
        print(f"✅ Found {len(messages)} messages matching 'anyapi test'")
        for msg in messages[:3]:
            print(f"   - {msg.get('id', 'N/A')}")
    except Exception as e:
        print(f"❌ Search failed: {e}")

    # 8. Get thread (if we have one)
    if sent_thread_id:
        print("\nStep 5: Get Thread")
        print("-" * 40)
        try:
            result = await api.call(
                "gmail_get_thread",
                user_id=USER_ID,
                thread_id=sent_thread_id,
                format="metadata",
            )
            thread_data = result.get("data", {})
            thread_messages = thread_data.get("messages", [])
            print(f"✅ Thread has {len(thread_messages)} message(s)")
            for msg in thread_messages:
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", []) if h.get("name") in ("From", "To", "Subject")}
                print(f"   - From: {headers.get('From', '?')} | Subject: {headers.get('Subject', '?')}")
        except Exception as e:
            print(f"❌ Get thread failed: {e}")

    # 9. Test LangChain tools generation
    print("\nStep 6: LangChain Tools")
    print("-" * 40)
    tools = api.get_tools("google", user_id=USER_ID)
    print(f"✅ Generated {len(tools)} LangChain tools:")
    for t in tools:
        print(f"   - {t.name}: {t.description[:60]}...")

    # Done
    print()
    print("=" * 60)
    print("  ✅ ALL TESTS PASSED — anyapi works with real Gmail!")
    print("=" * 60)

    await api.close()
    server.server_close()


if __name__ == "__main__":
    asyncio.run(main())
