"""
Core tests — verify the SDK works without real OAuth.
"""

import pytest
from anyapi import AnyAPI, MemoryTokenStore, AppCredentials, UserTokens


@pytest.fixture
def standalone_api():
    api = AnyAPI(token_store=MemoryTokenStore())
    api.register_app(AppCredentials(app="google", client_id="x", client_secret="y"))
    return api


# ── Action Discovery ─────────────────────────────────────────────────


def test_list_all_actions():
    actions = AnyAPI.list_actions()
    assert len(actions) > 0
    names = [a["name"] for a in actions]
    assert "gmail_send_email" in names
    assert "sheets_append_row" in names


def test_list_google_actions():
    actions = AnyAPI.list_actions("google")
    names = [a["name"] for a in actions]
    assert "gmail_send_email" in names
    assert all(a["app"] == "google" for a in actions)


# ── Tool Generation ──────────────────────────────────────────────────


def test_get_tools_nango_mode():
    api = AnyAPI(nango_secret_key="fake-key-for-testing")
    tools = api.get_tools("google", connection_id="test-user")
    assert len(tools) > 0
    tool_names = [t.name for t in tools]
    assert "gmail_send_email" in tool_names
    assert "sheets_append_row" in tool_names


def test_get_tools_standalone_mode(standalone_api):
    tools = standalone_api.get_tools("google", connection_id="test-user")
    assert len(tools) > 0


def test_get_tools_specific_actions():
    api = AnyAPI(nango_secret_key="fake-key")
    tools = api.get_tools("google", connection_id="test", actions=["gmail_send_email"])
    assert len(tools) == 1
    assert tools[0].name == "gmail_send_email"


# ── Token Store ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_token_store():
    store = MemoryTokenStore()
    tokens = UserTokens(app="google", user_id="user-1", access_token="abc123")
    await store.save_tokens(tokens)

    loaded = await store.get_tokens("google", "user-1")
    assert loaded is not None
    assert loaded.access_token == "abc123"

    connected = await store.list_connected("user-1")
    assert len(connected) == 1

    await store.delete_tokens("google", "user-1")
    assert await store.get_tokens("google", "user-1") is None


@pytest.mark.asyncio
async def test_token_expiry():
    from datetime import datetime, timezone, timedelta

    expired = UserTokens(
        app="google", user_id="u1", access_token="old",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    assert expired.is_expired is True

    valid = UserTokens(
        app="google", user_id="u1", access_token="new",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    assert valid.is_expired is False


# ── Specs ────────────────────────────────────────────────────────────


def test_gmail_send_spec():
    from anyapi.specs.google import GMAIL_SEND_EMAIL

    assert GMAIL_SEND_EMAIL.name == "gmail_send_email"
    assert GMAIL_SEND_EMAIL.method == "POST"
    assert GMAIL_SEND_EMAIL.request_transform == "gmail_mime"

    required = [p.name for p in GMAIL_SEND_EMAIL.required_params]
    assert "to" in required
    assert "subject" in required
    assert "body" in required


def test_gmail_mime_builder():
    from anyapi.executor import APIExecutor
    from anyapi.auth.nango import NangoClient

    nango = NangoClient(secret_key="fake")
    executor = APIExecutor(nango=nango)

    result = executor._build_gmail_mime({
        "to": "test@example.com",
        "subject": "Test",
        "body": "Hello World",
        "thread_id": "thread-123",
    })

    assert "raw" in result
    assert result["threadId"] == "thread-123"

    import base64
    decoded = base64.urlsafe_b64decode(result["raw"]).decode("utf-8")
    assert "test@example.com" in decoded
    assert "Hello World" in decoded


# ── Init Modes ───────────────────────────────────────────────────────


def test_nango_mode_init():
    api = AnyAPI(nango_secret_key="test-key")
    assert api._nango is not None
    assert api._oauth is None


def test_standalone_mode_init():
    api = AnyAPI(token_store=MemoryTokenStore())
    assert api._nango is None
    assert api._oauth is not None


def test_no_args_raises():
    with pytest.raises(ValueError, match="nango_secret_key or token_store"):
        AnyAPI()
