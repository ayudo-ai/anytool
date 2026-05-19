"""
Live trigger test — polls Gmail for new messages and delivers to a local webhook.

Flow:
1. Starts a local webhook server (port 9000)
2. Registers a Gmail trigger
3. Runs one poll cycle
4. Waits for you to send an email to the connected Gmail account
5. Polls again — should detect the new email and deliver to webhook
6. Shows the delivered event

Run: python test_triggers_live.py

Requires .env:
  NANGO_SECRET_KEY=xxx
  NANGO_CONNECTION_ID=xxx
"""

import asyncio
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread

# Load .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

from anytool import AnyAPI, TriggerConfig, TriggerEngine, MemoryTriggerStore

NANGO_SECRET_KEY = os.environ.get("NANGO_SECRET_KEY", "")
CONNECTION_ID = os.environ.get("NANGO_CONNECTION_ID", "test-user")

if not NANGO_SECRET_KEY:
    print("❌ Set NANGO_SECRET_KEY in .env")
    exit(1)

# Capture webhook deliveries
_received_events = []


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            event = json.loads(body)
            _received_events.append(event)
            print(f"\n📨 WEBHOOK RECEIVED:")
            print(f"   Type:    {event.get('trigger_type', '?')}")
            print(f"   From:    {event.get('data', {}).get('from', '?')}")
            print(f"   Subject: {event.get('data', {}).get('subject', '?')}")
            print(f"   Thread:  {event.get('data', {}).get('thread_id', '?')}")
        except Exception as e:
            print(f"   ❌ Parse error: {e}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

    def log_message(self, format, *args):
        pass


async def main():
    print("=" * 60)
    print("  anyapi — Live Gmail Trigger Test")
    print("=" * 60)
    print()

    # 1. Start local webhook server
    server = HTTPServer(("localhost", 9000), WebhookHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print("✅ Webhook server running on http://localhost:9000")

    # 2. Initialize
    api = AnyAPI(nango_secret_key=NANGO_SECRET_KEY)
    store = MemoryTriggerStore()
    engine = TriggerEngine(api=api, store=store)

    # 3. Register Gmail trigger
    trigger = TriggerConfig(
        id="test-gmail-trigger",
        trigger_type="gmail_new_message",
        provider="google",
        connection_id=CONNECTION_ID,
        webhook_url="http://localhost:9000/webhook",
        poll_interval_seconds=30,
        filters={},  # No filters — catch all new unread emails
    )
    await engine.register(trigger)
    print(f"✅ Trigger registered | connection={CONNECTION_ID}")

    # 4. First poll — establishes baseline
    print()
    print("Step 1: Initial poll (establishing baseline)")
    print("-" * 40)
    events = await engine.poll_once()
    print(f"   Found {len(events)} events (these are existing unread emails, now baselined)")

    # 5. Wait for user to send an email
    print()
    print("=" * 60)
    print(f"  Now send an email TO the Gmail account connected")
    print(f"  in Nango (connection: {CONNECTION_ID}).")
    print()
    print(f"  The poller will check every 30 seconds.")
    print(f"  Press Ctrl+C to stop.")
    print("=" * 60)
    print()

    # 6. Poll loop
    poll_count = 0
    try:
        while True:
            await asyncio.sleep(30)
            poll_count += 1
            print(f"🔄 Poll #{poll_count}...")
            events = await engine.poll_once()
            if events:
                print(f"   ✅ {len(events)} new email(s) detected and delivered!")
            else:
                print(f"   No new emails")
    except KeyboardInterrupt:
        print()
        print(f"\nStopped. Total webhook events received: {len(_received_events)}")

    # Cleanup
    server.shutdown()
    await engine.close()
    await api.close()


if __name__ == "__main__":
    asyncio.run(main())
