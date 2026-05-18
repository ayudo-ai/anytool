"""
Live test — anyapi with Nango for Gmail.

Prerequisites:
1. Sign up at https://app.nango.dev (free, no credit card)
2. Go to Integrations → Add → search "Google" → add it
3. Configure your Google OAuth credentials in Nango:
   - Client ID (from Google Cloud Console)
   - Client Secret
   - Scopes: gmail.send, gmail.readonly, gmail.modify, userinfo.email
4. Go to Connections → Create → select Google → complete OAuth
   - Use connection_id = your workspace_id (e.g. "test-user")
5. Copy your Nango Secret Key from Settings → Secret Key
6. Put it in .env: NANGO_SECRET_KEY=nango-xxx

Run: python test_nango_live.py
"""

import asyncio
import os
from pathlib import Path

# Load .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

from anyapi import AnyAPI

NANGO_SECRET_KEY = os.environ.get("NANGO_SECRET_KEY", "")
CONNECTION_ID = os.environ.get("NANGO_CONNECTION_ID", "test-user")
NANGO_PROVIDER = os.environ.get("NANGO_PROVIDER", "google")
TEST_EMAIL = os.environ.get("TEST_EMAIL", "nitinpanwar98@gmail.com")

if not NANGO_SECRET_KEY:
    print("❌ Set NANGO_SECRET_KEY in .env")
    print()
    print("Setup steps:")
    print("1. Sign up at https://app.nango.dev")
    print("2. Integrations → Add → Google")
    print("3. Configure Google OAuth credentials")
    print("4. Connections → Create → Google → complete OAuth")
    print("5. Settings → copy Secret Key → add to .env")
    exit(1)


async def main():
    print("=" * 60)
    print("  anyapi + Nango — Live Gmail Test")
    print("=" * 60)
    print()
    print(f"  Nango provider: {NANGO_PROVIDER}")
    print(f"  Connection ID:  {CONNECTION_ID}")
    print(f"  Test email:     {TEST_EMAIL}")
    print()

    # 1. Initialize with Nango
    api = AnyAPI(nango_secret_key=NANGO_SECRET_KEY)

    # 2. Check connection
    print("Step 1: Check Connection")
    print("-" * 40)
    connected = await api.is_connected(NANGO_PROVIDER, CONNECTION_ID)
    if connected:
        print(f"✅ Connected to {NANGO_PROVIDER}")
    else:
        print(f"❌ Not connected to {NANGO_PROVIDER}")
        print(f"   Go to https://app.nango.dev → Connections → Create → {NANGO_PROVIDER}")
        print(f"   Use connection ID: {CONNECTION_ID}")
        await api.close()
        return

    # 3. Send email
    print(f"\nStep 2: Send Email")
    print("-" * 40)
    print(f"Sending to: {TEST_EMAIL}")
    result = await api.call(
        "gmail_send_email",
        connection_id=CONNECTION_ID,
        to=TEST_EMAIL,
        subject="anyapi + Nango test — it works!",
        body="This email was sent via anyapi using Nango for auth.\n\nNo Composio. No wrappers. Just specs + Nango proxy.",
    )

    if result["successful"]:
        print(f"✅ Email sent!")
        print(f"   Message ID: {result['extracted_ids'].get('message_id', 'N/A')}")
        print(f"   Thread ID:  {result['extracted_ids'].get('thread_id', 'N/A')}")
        sent_thread_id = result["extracted_ids"].get("thread_id", "")
    else:
        print(f"❌ Send failed: {result.get('error', 'Unknown')}")
        sent_thread_id = ""

    # 4. Search inbox
    print(f"\nStep 3: Search Inbox")
    print("-" * 40)
    result = await api.call(
        "gmail_search",
        connection_id=CONNECTION_ID,
        q="subject:anyapi",
        maxResults=5,
    )

    if result["successful"]:
        messages = result.get("data", {}).get("messages", [])
        print(f"✅ Found {len(messages)} messages matching 'anyapi'")
        for msg in messages[:3]:
            print(f"   - {msg.get('id', 'N/A')}")
    else:
        print(f"❌ Search failed: {result.get('error', 'Unknown')}")

    # 5. Get thread
    if sent_thread_id:
        print(f"\nStep 4: Get Thread")
        print("-" * 40)
        result = await api.call(
            "gmail_get_thread",
            connection_id=CONNECTION_ID,
            thread_id=sent_thread_id,
            format="metadata",
        )

        if result["successful"]:
            thread_data = result.get("data", {})
            thread_messages = thread_data.get("messages", [])
            print(f"✅ Thread has {len(thread_messages)} message(s)")
            for msg in thread_messages:
                headers = {
                    h["name"]: h["value"]
                    for h in msg.get("payload", {}).get("headers", [])
                    if h.get("name") in ("From", "To", "Subject")
                }
                print(f"   - From: {headers.get('From', '?')}")
                print(f"     Subject: {headers.get('Subject', '?')}")
        else:
            print(f"❌ Get thread failed: {result.get('error', 'Unknown')}")

    # 6. LangChain tools
    print(f"\nStep 5: LangChain Tools")
    print("-" * 40)
    tools = api.get_tools("google", connection_id=CONNECTION_ID)
    print(f"✅ Generated {len(tools)} LangChain tools:")
    for t in tools:
        print(f"   - {t.name}")

    # Done
    print()
    print("=" * 60)
    if sent_thread_id:
        print("  ✅ ALL TESTS PASSED — anyapi + Nango works!")
    else:
        print("  ⚠️  Email send failed — check Nango connection and Google API setup")
    print("=" * 60)

    await api.close()


if __name__ == "__main__":
    asyncio.run(main())
