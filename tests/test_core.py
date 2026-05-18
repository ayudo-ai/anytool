"""
Core tests — verify the SDK works end-to-end without real OAuth.
"""

import pytest
from anyapi import AnyAPI, MemoryTokenStore, AppCredentials, UserTokens


@pytest.fixture
def store():
    return MemoryTokenStore()


@pytest.fixture
def api(store):
    return AnyAPI(token_store=store)


# ── Registration ─────────────────────────────────────────────────────


def test_register_app(api):
    api.register_app(AppCredentials(
        app="google",
        client_id="test-id",
        client_secret="test-secret",
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    ))
    assert "google" in api._credentials


def test_register_unknown_app_fails(api):
    with pytest.raises(ValueError, match="not registered"):
        api._get_credentials("nonexistent")


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


def test_get_tools_generates_langchain_tools(api):
    api.register_app(AppCredentials(
        app="google",
        client_id="test-id",
        client_secret="test-secret",
    ))

    tools = api.get_tools("google", user_id="test-user")
    assert len(tools) > 0

    tool_names = [t.name for t in tools]
    assert "gmail_send_email" in tool_names
    assert "gmail_search" in tool_names
    assert "sheets_append_row" in tool_names


def test_get_tools_specific_actions(api):
    api.register_app(AppCredentials(app="google", client_id="x", client_secret="y"))

    tools = api.get_tools("google", user_id="test", actions=["gmail_send_email"])
    assert len(tools) == 1
    assert tools[0].name == "gmail_send_email"


# ── Token Store ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_token_store(store):
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

    # Expired token
    expired = UserTokens(
        app="google",
        user_id="user-1",
        access_token="old",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    assert expired.is_expired is True

    # Valid token
    valid = UserTokens(
        app="google",
        user_id="user-1",
        access_token="new",
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

    optional = [p.name for p in GMAIL_SEND_EMAIL.optional_params]
    assert "cc" in optional
    assert "thread_id" in optional


def test_gmail_mime_builder():
    from anyapi.executor import APIExecutor
    from anyapi.auth.token_store import MemoryTokenStore
    from anyapi.auth.oauth import OAuthManager

    executor = APIExecutor(OAuthManager(MemoryTokenStore()))

    result = executor._build_gmail_mime({
        "to": "test@example.com",
        "subject": "Test Subject",
        "body": "Hello World",
        "thread_id": "thread-123",
    })

    assert "raw" in result
    assert result["threadId"] == "thread-123"

    # Decode and verify MIME
    import base64
    decoded = base64.urlsafe_b64decode(result["raw"]).decode("utf-8")
    assert "test@example.com" in decoded
    assert "Test Subject" in decoded
    assert "Hello World" in decoded
