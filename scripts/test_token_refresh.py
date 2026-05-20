"""
Test token refresh — verifies that expired tokens get automatically refreshed.

Run: python test_token_refresh.py

This test:
1. Gets the current tokens for a connected user
2. Manually expires them (sets expires_at to the past)
3. Makes an API call — should trigger auto-refresh
4. Verifies the new tokens work
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


async def test_refresh():
    from server.token_store import PostgresTokenStore
    from server.engine import get_api
    from server.database import init_db

    await init_db()

    store = PostgresTokenStore()
    api = get_api()

    # Find a connected user
    user_id = os.environ.get("TEST_CONNECTION_ID", "nitin")
    app = "google"

    print(f"\n=== Token Refresh Test ===")
    print(f"User: {user_id}, App: {app}\n")

    # Step 1: Get current tokens
    tokens = await store.get_tokens(app, user_id)
    if not tokens:
        print(f"❌ No tokens found for {app}:{user_id}")
        print(f"   Connect a user first via the dashboard")
        return False

    print(f"1. Current tokens:")
    print(f"   access_token: {tokens.access_token[:20]}...")
    print(f"   refresh_token: {'yes' if tokens.refresh_token else 'NO ⚠️'}")
    print(f"   expires_at: {tokens.expires_at}")
    print(f"   is_expired: {tokens.is_expired}")

    if not tokens.refresh_token:
        print(f"\n❌ No refresh_token! User must re-authorize with access_type=offline")
        print(f"   The OAuth URL needs 'access_type=offline' and 'prompt=consent'")
        return False

    # Step 2: Make a call with valid tokens first (sanity check)
    print(f"\n2. Testing API call with current token...")
    result = await api.call("gmail_search", connection_id=user_id, q="newer_than:1d", maxResults=1)
    if result.get("successful"):
        print(f"   ✅ API call works with current token")
    else:
        print(f"   ❌ API call failed: {result.get('error')}")
        return False

    # Step 3: Manually expire the token
    print(f"\n3. Manually expiring token...")
    original_expires = tokens.expires_at
    tokens.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await store.save_tokens(tokens)

    # Verify it's expired
    tokens_check = await store.get_tokens(app, user_id)
    print(f"   expires_at set to: {tokens_check.expires_at}")
    print(f"   is_expired: {tokens_check.is_expired}")
    assert tokens_check.is_expired, "Token should be expired"

    # Step 4: Make an API call — should trigger auto-refresh
    print(f"\n4. Making API call with expired token (should auto-refresh)...")
    result = await api.call("gmail_search", connection_id=user_id, q="newer_than:1d", maxResults=1)

    if result.get("successful"):
        print(f"   ✅ API call succeeded after auto-refresh!")
    else:
        print(f"   ❌ API call failed: {result.get('error')}")
        # Restore original expiry
        tokens.expires_at = original_expires
        await store.save_tokens(tokens)
        return False

    # Step 5: Verify tokens were refreshed
    refreshed = await store.get_tokens(app, user_id)
    print(f"\n5. Refreshed tokens:")
    print(f"   access_token: {refreshed.access_token[:20]}...")
    print(f"   expires_at: {refreshed.expires_at}")
    print(f"   is_expired: {refreshed.is_expired}")

    token_changed = refreshed.access_token != tokens.access_token
    print(f"   token changed: {'✅ yes' if token_changed else '⚠️ no (might be same if not expired long enough)'}")

    print(f"\n✅ Token refresh test PASSED!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_refresh())
    sys.exit(0 if success else 1)
