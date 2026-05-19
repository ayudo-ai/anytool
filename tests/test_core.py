"""
Core tests — verify the SDK works without real OAuth.
"""

import pytest
from anytool import AnyAPI, MemoryTokenStore, AppCredentials, UserTokens


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
    from anytool.specs.google import GMAIL_SEND_EMAIL

    assert GMAIL_SEND_EMAIL.name == "gmail_send_email"
    assert GMAIL_SEND_EMAIL.method == "POST"
    assert GMAIL_SEND_EMAIL.request_transform == "gmail_mime"

    required = [p.name for p in GMAIL_SEND_EMAIL.required_params]
    assert "to" in required
    assert "subject" in required
    assert "body" in required


def test_gmail_mime_builder():
    from anytool.executor import APIExecutor
    from anytool.auth.nango import NangoClient

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


# ── DocuSign Specs ───────────────────────────────────────────────────


def test_docusign_specs_registered():
    actions = AnyAPI.list_actions("docusign")
    names = [a["name"] for a in actions]
    assert "docusign_create_envelope" in names
    assert "docusign_get_envelope" in names
    assert "docusign_void_envelope" in names
    assert len(actions) == 6


def test_docusign_tools_generated():
    api = AnyAPI(nango_secret_key="fake-key")
    tools = api.get_tools("docusign", connection_id="test")
    assert len(tools) == 6
    tool_names = [t.name for t in tools]
    assert "docusign_create_envelope" in tool_names


def test_docusign_envelope_builder():
    """The exact scenario that was broken on Composio.

    Composio turned templateRoles: [{roleName: 'Signer', ...}] into [{}]
    Our builder must preserve the nested objects exactly.
    """
    from anytool.executor import APIExecutor
    from anytool.auth.nango import NangoClient

    nango = NangoClient(secret_key="fake")
    executor = APIExecutor(nango=nango)

    result = executor._build_docusign_envelope({
        "template_id": "2184100d-b91c-42cc-adb7-d90664d7ee43",
        "template_roles": [
            {
                "roleName": "Signer",
                "name": "Sarah Mitchell",
                "email": "sarah@example.com",
            },
            {
                "roleName": "CC",
                "name": "Manager",
                "email": "manager@example.com",
            },
        ],
        "status": "sent",
        "email_subject": "1099 Partner Onboarding Agreement - Sarah Mitchell",
    })

    # Verify the exact payload DocuSign expects
    assert result["templateId"] == "2184100d-b91c-42cc-adb7-d90664d7ee43"
    assert result["status"] == "sent"
    assert result["emailSubject"] == "1099 Partner Onboarding Agreement - Sarah Mitchell"

    # THE KEY TEST: templateRoles must have full data, NOT [{}]
    roles = result["templateRoles"]
    assert len(roles) == 2
    assert roles[0]["roleName"] == "Signer"
    assert roles[0]["name"] == "Sarah Mitchell"
    assert roles[0]["email"] == "sarah@example.com"
    assert roles[1]["roleName"] == "CC"
    assert roles[1]["name"] == "Manager"


def test_docusign_envelope_builder_handles_snake_case():
    """LLM might use snake_case instead of camelCase."""
    from anytool.executor import APIExecutor
    from anytool.auth.nango import NangoClient

    executor = APIExecutor(nango=NangoClient(secret_key="fake"))

    result = executor._build_docusign_envelope({
        "template_id": "abc-123",
        "template_roles": [
            {"role_name": "Signer", "name": "John", "email": "john@test.com"},
        ],
        "status": "sent",
    })

    roles = result["templateRoles"]
    assert roles[0]["roleName"] == "Signer"  # Converted from role_name


def test_docusign_envelope_builder_handles_json_string():
    """LLM might pass template_roles as a JSON string."""
    from anytool.executor import APIExecutor
    from anytool.auth.nango import NangoClient

    executor = APIExecutor(nango=NangoClient(secret_key="fake"))

    result = executor._build_docusign_envelope({
        "template_id": "abc-123",
        "template_roles": '[{"roleName": "Signer", "name": "Jane", "email": "jane@test.com"}]',
        "status": "sent",
    })

    roles = result["templateRoles"]
    assert len(roles) == 1
    assert roles[0]["roleName"] == "Signer"
    assert roles[0]["name"] == "Jane"


# ── Freshdesk Specs ──────────────────────────────────────────────────


def test_freshdesk_specs_registered():
    actions = AnyAPI.list_actions("freshdesk")
    names = [a["name"] for a in actions]
    assert "freshdesk_create_ticket" in names
    assert "freshdesk_reply_ticket" in names
    assert "freshdesk_search_tickets" in names
    assert len(actions) == 10


def test_freshdesk_tools_generated():
    api = AnyAPI(nango_secret_key="fake-key")
    tools = api.get_tools("freshdesk", connection_id="test")
    assert len(tools) == 10


# ── Slack Specs ─────────────────────────────────────────────────────


def test_slack_specs_registered():
    actions = AnyAPI.list_actions("slack")
    names = [a["name"] for a in actions]
    assert "slack_send_message" in names
    assert "slack_list_channels" in names
    assert "slack_lookup_user" in names
    assert len(actions) == 7


def test_slack_tools_generated():
    api = AnyAPI(nango_secret_key="fake-key")
    tools = api.get_tools("slack", connection_id="test")
    assert len(tools) == 7


# ── All Apps Summary ────────────────────────────────────────────────


# ── HubSpot Specs ────────────────────────────────────────────────────


def test_hubspot_specs_registered():
    actions = AnyAPI.list_actions("hubspot")
    names = [a["name"] for a in actions]
    assert "hubspot_create_contact" in names
    assert "hubspot_create_deal" in names
    assert "hubspot_create_note" in names
    assert "hubspot_associate" in names
    assert "hubspot_list_owners" in names
    assert len(actions) == 15


def test_hubspot_tools_generated():
    api = AnyAPI(nango_secret_key="fake-key")
    tools = api.get_tools("hubspot", connection_id="test")
    assert len(tools) == 15


def test_hubspot_properties_builder():
    """HubSpot wraps all fields in {properties: {}}."""
    from anytool.executor import APIExecutor
    from anytool.auth.nango import NangoClient
    from anytool.specs.hubspot import HUBSPOT_CREATE_CONTACT

    executor = APIExecutor(nango=NangoClient(secret_key="fake"))
    result = executor._build_hubspot_properties(HUBSPOT_CREATE_CONTACT, {
        "email": "john@acme.com",
        "firstname": "John",
        "lastname": "Doe",
        "phone": "+1-555-0100",
    })
    assert result == {
        "properties": {
            "email": "john@acme.com",
            "firstname": "John",
            "lastname": "Doe",
            "phone": "+1-555-0100",
        }
    }


def test_hubspot_search_builder():
    from anytool.executor import APIExecutor
    from anytool.auth.nango import NangoClient

    executor = APIExecutor(nango=NangoClient(secret_key="fake"))
    result = executor._build_hubspot_search({
        "filter_property": "email",
        "filter_operator": "EQ",
        "filter_value": "john@acme.com",
        "limit": 5,
        "properties": ["email", "firstname", "lastname"],
    })
    assert result["filterGroups"][0]["filters"][0]["propertyName"] == "email"
    assert result["filterGroups"][0]["filters"][0]["value"] == "john@acme.com"
    assert result["limit"] == 5
    assert result["properties"] == ["email", "firstname", "lastname"]


def test_hubspot_note_builder():
    from anytool.executor import APIExecutor
    from anytool.auth.nango import NangoClient

    executor = APIExecutor(nango=NangoClient(secret_key="fake"))
    result = executor._build_hubspot_note({
        "body": "Called customer, resolved billing issue.",
        "contact_id": "12345",
        "deal_id": "67890",
    })
    assert result["properties"]["hs_note_body"] == "Called customer, resolved billing issue."
    assert len(result["associations"]) == 2
    assert result["associations"][0]["to"]["id"] == "12345"


# ── All Apps Summary ─────────────────────────────────────────────────


def test_total_specs_count():
    """Verify total spec count across all apps."""
    all_actions = AnyAPI.list_actions()
    # Google: 11, DocuSign: 6, Freshdesk: 10, Slack: 7, HubSpot: 15 = 49
    assert len(all_actions) == 49
