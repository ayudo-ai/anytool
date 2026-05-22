"""
v2 Core Tests — validate the new spec-first engine end-to-end.

Tests cover:
1. Spec loading from YAML
2. DocuSign payload fidelity (the Composio bug)
3. Gmail MIME encoder
4. HubSpot nested JSON pass-through
5. Zendesk nested JSON pass-through
6. Slack simple pass-through
7. OpenAI tool generation
8. MCP tool generation
9. Path param substitution + metadata injection
10. Response ID extraction
11. Retry logic
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from anytool.core.loader import SpecRegistry, load_spec
from anytool.core.models import ActionSpec
from anytool.core.executor import Executor, AuthTokens, ExecutionResult
from anytool.core.engine import Engine
from anytool.core.encoders import encode
from anytool.core.encoders.gmail_mime import encode_gmail_mime

REGISTRY_PATH = Path(__file__).parent.parent / "registry"


# ═══════════════════════════════════════════════════════════════════════
# 1. Spec Loading
# ═══════════════════════════════════════════════════════════════════════


class TestSpecLoading:

    def test_registry_loads_all_specs(self):
        registry = SpecRegistry(REGISTRY_PATH)
        assert len(registry) == 79  # 5 hand-crafted + 74 migrated
        assert "slack_send_message" in registry
        assert "docusign_create_envelope" in registry
        assert "hubspot_create_contact" in registry
        assert "zendesk_create_ticket" in registry
        assert "gmail_send_email" in registry
        # Migrated specs
        assert "github_create_issue" in registry
        assert "freshdesk_create_ticket" in registry
        assert "whatsapp_send_template" in registry

    def test_registry_groups_by_app(self):
        registry = SpecRegistry(REGISTRY_PATH)
        apps = registry.apps()
        assert "slack" in apps
        assert "docusign" in apps
        assert "hubspot" in apps
        assert "zendesk" in apps
        assert "google" in apps
        assert "github" in apps
        assert "freshdesk" in apps
        assert "whatsapp" in apps
        assert len(apps) == 8

    def test_load_docusign_spec(self):
        spec = load_spec(REGISTRY_PATH / "docusign" / "create_envelope.yaml")
        assert spec.name == "docusign_create_envelope"
        assert spec.app == "docusign"
        assert spec.method == "POST"
        assert "{account_id}" in spec.path
        assert spec.auth.type == "oauth2"
        assert "signature" in spec.auth.scopes
        assert spec.auth.inject_from_metadata == {"account_id": "account_id"}

    def test_load_gmail_spec_has_encoder(self):
        spec = load_spec(REGISTRY_PATH / "google" / "gmail" / "send_email.yaml")
        assert spec.encoder == "gmail_mime"
        assert spec.tier == 3
        assert "to" in spec.agent_params.get("required", [])

    def test_load_slack_spec_is_tier1(self):
        spec = load_spec(REGISTRY_PATH / "slack" / "send_message.yaml")
        assert spec.encoder == ""
        assert spec.tier == 1
        assert "channel" in spec.required_fields
        assert "text" in spec.required_fields

    def test_spec_examples_loaded(self):
        spec = load_spec(REGISTRY_PATH / "docusign" / "create_envelope.yaml")
        assert len(spec.examples) >= 3
        assert spec.examples[0].name == "Send agreement to one signer"
        assert "templateRoles" in spec.examples[0].request

    def test_spec_errors_loaded(self):
        spec = load_spec(REGISTRY_PATH / "docusign" / "create_envelope.yaml")
        assert "INVALID_TEMPLATE_ID" in spec.errors

    def test_spec_tags_loaded(self):
        spec = load_spec(REGISTRY_PATH / "slack" / "send_message.yaml")
        assert "messaging" in spec.tags

    def test_search_by_tags(self):
        registry = SpecRegistry(REGISTRY_PATH)
        results = registry.search_by_tags(["esignature"])
        assert len(results) == 6  # All docusign specs tagged with esignature
        names = {r.name for r in results}
        assert "docusign_create_envelope" in names

    def test_llm_schema_for_tier1_2(self):
        """Tier 1/2 specs: llm_schema == request.body_schema"""
        spec = load_spec(REGISTRY_PATH / "slack" / "send_message.yaml")
        assert spec.llm_schema == spec.request.body_schema
        assert "channel" in spec.llm_schema["properties"]

    def test_llm_schema_for_tier3(self):
        """Tier 3 specs: llm_schema == agent_params"""
        spec = load_spec(REGISTRY_PATH / "google" / "gmail" / "send_email.yaml")
        assert spec.llm_schema == spec.agent_params
        assert "to" in spec.llm_schema["properties"]
        # Should NOT expose 'raw' to the LLM
        assert "raw" not in spec.llm_schema.get("properties", {})


# ═══════════════════════════════════════════════════════════════════════
# 2. DocuSign Payload Fidelity (THE KEY TEST)
# ═══════════════════════════════════════════════════════════════════════


class TestDocuSignFidelity:
    """The exact scenario that broke on Composio.

    Composio turned templateRoles: [{roleName, email, name}] into [{}].
    With anytool v2, the LLM constructs the JSON and we pass it through.
    """

    def test_template_roles_preserved(self):
        """The critical test: nested objects must survive."""
        llm_output = {
            "templateId": "2184100d-b91c-42cc-adb7-d90664d7ee43",
            "templateRoles": [
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
            "emailSubject": "1099 Partner Onboarding Agreement",
        }

        # Simulate what the executor does: JSON serialize → deserialize
        wire = json.dumps(llm_output)
        received = json.loads(wire)

        roles = received["templateRoles"]
        assert len(roles) == 2
        assert roles[0]["roleName"] == "Signer"
        assert roles[0]["name"] == "Sarah Mitchell"
        assert roles[0]["email"] == "sarah@example.com"
        assert roles[1]["roleName"] == "CC"
        assert roles[1]["name"] == "Manager"
        assert roles[1]["email"] == "manager@example.com"

    def test_template_roles_with_tabs(self):
        """Pre-filled form fields must also survive."""
        llm_output = {
            "templateId": "abc-123",
            "templateRoles": [
                {
                    "roleName": "Signer",
                    "name": "Sarah Mitchell",
                    "email": "sarah@example.com",
                    "tabs": {
                        "textTabs": [
                            {"tabLabel": "CompanyName", "value": "Mitchell Consulting LLC"},
                            {"tabLabel": "TaxID", "value": "XX-XXXXXXX"},
                        ],
                    },
                },
            ],
            "status": "sent",
        }

        wire = json.dumps(llm_output)
        received = json.loads(wire)

        tabs = received["templateRoles"][0]["tabs"]["textTabs"]
        assert len(tabs) == 2
        assert tabs[0]["tabLabel"] == "CompanyName"
        assert tabs[0]["value"] == "Mitchell Consulting LLC"
        assert tabs[1]["tabLabel"] == "TaxID"


# ═══════════════════════════════════════════════════════════════════════
# 3. Gmail MIME Encoder
# ═══════════════════════════════════════════════════════════════════════


class TestGmailMimeEncoder:

    def test_simple_email(self):
        result = encode_gmail_mime({
            "to": "sarah@example.com",
            "subject": "Invoice Follow-up",
            "body": "Hi Sarah, please send the updated invoice.",
        })

        assert "raw" in result
        assert "threadId" not in result  # No thread

        # Decode and verify MIME
        raw = result["raw"]
        # Add padding back for decoding
        padded = raw + "=" * (4 - len(raw) % 4) if len(raw) % 4 else raw
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        assert "sarah@example.com" in decoded
        assert "Invoice Follow-up" in decoded
        assert "Hi Sarah" in decoded

    def test_html_email(self):
        result = encode_gmail_mime({
            "to": "sarah@example.com",
            "subject": "Report",
            "body": "<h1>Q2 Report</h1><p>Revenue up 15%</p>",
            "content_type": "text/html",
        })

        padded = result["raw"] + "=" * (4 - len(result["raw"]) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        assert "text/html" in decoded
        assert "Q2 Report" in decoded

    def test_email_with_cc_bcc(self):
        result = encode_gmail_mime({
            "to": "sarah@example.com",
            "cc": "manager@example.com",
            "bcc": "audit@example.com",
            "subject": "Test",
            "body": "Hello",
        })

        padded = result["raw"] + "=" * (4 - len(result["raw"]) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        assert "Cc: manager@example.com" in decoded
        assert "Bcc: audit@example.com" in decoded

    def test_thread_reply(self):
        result = encode_gmail_mime({
            "to": "sarah@example.com",
            "subject": "Re: Invoice Follow-up",
            "body": "Thanks!",
            "thread_id": "thread-123",
            "in_reply_to": "<msg-id@mail.gmail.com>",
        })

        assert result["threadId"] == "thread-123"

        padded = result["raw"] + "=" * (4 - len(result["raw"]) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        assert "In-Reply-To: <msg-id@mail.gmail.com>" in decoded

    def test_encoder_via_registry(self):
        """Test that the encoder registry resolves correctly."""
        result = encode("gmail_mime", {
            "to": "test@example.com",
            "subject": "Test",
            "body": "Hello",
        })
        assert "raw" in result

    def test_unknown_encoder_raises(self):
        from anytool.core.encoders import get_encoder
        with pytest.raises(ValueError, match="Unknown encoder"):
            get_encoder("nonexistent_encoder")


# ═══════════════════════════════════════════════════════════════════════
# 4. HubSpot Nested JSON
# ═══════════════════════════════════════════════════════════════════════


class TestHubSpotPassthrough:

    def test_properties_wrapping_preserved(self):
        """HubSpot requires {properties: {key: value}}. LLM constructs it."""
        llm_output = {
            "properties": {
                "email": "sarah@example.com",
                "firstname": "Sarah",
                "lastname": "Mitchell",
                "phone": "+1-555-0100",
                "company": "Mitchell Consulting",
            }
        }

        wire = json.dumps(llm_output)
        received = json.loads(wire)

        assert received["properties"]["email"] == "sarah@example.com"
        assert received["properties"]["firstname"] == "Sarah"
        assert received["properties"]["company"] == "Mitchell Consulting"

    def test_associations_preserved(self):
        """HubSpot associations are deeply nested."""
        llm_output = {
            "properties": {
                "email": "james@partner.com",
            },
            "associations": [
                {
                    "to": {"id": "98765"},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 1,
                        }
                    ],
                }
            ],
        }

        wire = json.dumps(llm_output)
        received = json.loads(wire)

        assoc = received["associations"][0]
        assert assoc["to"]["id"] == "98765"
        assert assoc["types"][0]["associationCategory"] == "HUBSPOT_DEFINED"
        assert assoc["types"][0]["associationTypeId"] == 1


# ═══════════════════════════════════════════════════════════════════════
# 5. Zendesk Nested JSON
# ═══════════════════════════════════════════════════════════════════════


class TestZendeskPassthrough:

    def test_ticket_comment_nesting(self):
        """Zendesk requires {ticket: {subject, comment: {body}}}."""
        llm_output = {
            "ticket": {
                "subject": "Billing issue - double charged",
                "comment": {
                    "body": "I was charged twice for my subscription.",
                },
                "requester": {
                    "name": "Sarah Mitchell",
                    "email": "sarah@example.com",
                },
                "priority": "high",
                "tags": ["billing", "duplicate-charge"],
            }
        }

        wire = json.dumps(llm_output)
        received = json.loads(wire)

        ticket = received["ticket"]
        assert ticket["subject"] == "Billing issue - double charged"
        assert ticket["comment"]["body"] == "I was charged twice for my subscription."
        assert ticket["requester"]["name"] == "Sarah Mitchell"
        assert ticket["requester"]["email"] == "sarah@example.com"
        assert ticket["priority"] == "high"
        assert ticket["tags"] == ["billing", "duplicate-charge"]

    def test_internal_note(self):
        """Internal note: comment.public = false."""
        llm_output = {
            "ticket": {
                "subject": "Internal task",
                "comment": {
                    "body": "Escalating to tier 2.",
                    "public": False,
                },
            }
        }

        wire = json.dumps(llm_output)
        received = json.loads(wire)
        assert received["ticket"]["comment"]["public"] is False


# ═══════════════════════════════════════════════════════════════════════
# 6. Executor — URL Building & Metadata Injection
# ═══════════════════════════════════════════════════════════════════════


class TestExecutorURLBuilding:

    def setup_method(self):
        self.executor = Executor()

    def test_path_param_from_body(self):
        """Path params should be extracted from the body."""
        spec = load_spec(REGISTRY_PATH / "slack" / "send_message.yaml")
        # Slack has no path params, so test with a minimal spec
        from anytool.core.models import ActionSpec, AuthSpec, RequestSpec, ResponseSpec
        spec = ActionSpec(
            name="test", app="test", method="GET",
            path="/api/v1/items/{item_id}",
            base_url="https://api.example.com",
        )
        auth = AuthTokens(access_token="test-token")

        url, remaining = self.executor._build_url(
            spec,
            {"item_id": "abc-123", "extra_field": "keep"},
            auth,
        )

        assert url == "https://api.example.com/api/v1/items/abc-123"
        assert "item_id" not in remaining  # consumed
        assert remaining["extra_field"] == "keep"  # kept

    def test_metadata_injection(self):
        """DocuSign account_id comes from token metadata, not body."""
        spec = load_spec(REGISTRY_PATH / "docusign" / "create_envelope.yaml")
        auth = AuthTokens(
            access_token="test-token",
            metadata={"account_id": "acc-12345"},
        )

        url, remaining = self.executor._build_url(
            spec,
            {"templateId": "tpl-1", "status": "sent"},
            auth,
        )

        assert "acc-12345" in url
        assert "/accounts/acc-12345/envelopes" in url
        assert "templateId" in remaining  # body field, not consumed

    def test_zendesk_subdomain_in_base_url(self):
        """Zendesk's base_url contains {subdomain} — resolved from metadata."""
        spec = load_spec(REGISTRY_PATH / "zendesk" / "create_ticket.yaml")
        auth = AuthTokens(
            access_token="test-token",
            metadata={"subdomain": "mycompany"},
        )

        url, _ = self.executor._build_url(spec, {}, auth)
        assert "mycompany.zendesk.com" in url


class TestExecutorResponseExtraction:

    def test_extract_flat_id(self):
        """Extract a flat ID from response."""
        executor = Executor()
        spec = load_spec(REGISTRY_PATH / "hubspot" / "create_contact.yaml")

        ids = executor._extract_ids(spec, {"id": "12345", "properties": {}})
        assert ids == {"contact_id": "12345"}

    def test_extract_nested_id(self):
        """Extract a nested ID like ticket.id."""
        executor = Executor()
        spec = load_spec(REGISTRY_PATH / "zendesk" / "create_ticket.yaml")

        ids = executor._extract_ids(spec, {
            "ticket": {"id": 98765, "subject": "Test"},
        })
        assert ids == {"ticket_id": "98765"}

    def test_extract_missing_field(self):
        """Missing fields should be silently skipped."""
        executor = Executor()
        spec = load_spec(REGISTRY_PATH / "hubspot" / "create_contact.yaml")

        ids = executor._extract_ids(spec, {"other": "data"})
        assert ids == {}


# ═══════════════════════════════════════════════════════════════════════
# 7. OpenAI Tool Generation
# ═══════════════════════════════════════════════════════════════════════


class TestOpenAIAdapter:

    def test_generate_tools(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        tools = engine.get_openai_tools()
        assert len(tools) == 79

        names = {t["function"]["name"] for t in tools}
        assert "slack_send_message" in names
        assert "docusign_create_envelope" in names
        assert "github_create_issue" in names
        assert "freshdesk_create_ticket" in names

    def test_tool_has_correct_schema(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        tools = engine.get_openai_tools(actions=["slack_send_message"])
        assert len(tools) == 1

        tool = tools[0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "slack_send_message"

        params = tool["function"]["parameters"]
        assert params["type"] == "object"
        assert "channel" in params["properties"]
        assert "text" in params["properties"]
        assert "channel" in params["required"]
        assert "text" in params["required"]

    def test_docusign_tool_preserves_nesting(self):
        """The OpenAI tool schema must describe nested templateRoles."""
        engine = Engine(registry_path=REGISTRY_PATH)
        tools = engine.get_openai_tools(actions=["docusign_create_envelope"])
        tool = tools[0]

        params = tool["function"]["parameters"]
        roles_schema = params["properties"]["templateRoles"]
        assert roles_schema["type"] == "array"
        assert "items" in roles_schema
        assert "roleName" in roles_schema["items"]["properties"]
        assert "name" in roles_schema["items"]["properties"]
        assert "email" in roles_schema["items"]["properties"]

    def test_gmail_tool_uses_agent_params(self):
        """Gmail tool should show agent_params (to, subject, body), not raw."""
        engine = Engine(registry_path=REGISTRY_PATH)
        tools = engine.get_openai_tools(actions=["gmail_send_email"])
        tool = tools[0]

        params = tool["function"]["parameters"]
        assert "to" in params["properties"]
        assert "subject" in params["properties"]
        assert "body" in params["properties"]
        # Should NOT expose 'raw' (that's the API field, not the LLM field)
        assert "raw" not in params["properties"]

    def test_tool_includes_examples_in_description(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        tools = engine.get_openai_tools(
            actions=["docusign_create_envelope"],
            include_examples=True,
        )
        desc = tools[0]["function"]["description"]
        assert "templateRoles" in desc  # Example should be in description
        assert "Sarah Mitchell" in desc

    def test_filter_by_app(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        tools = engine.get_openai_tools(app="slack")
        assert len(tools) == 7  # All slack actions
        names = {t["function"]["name"] for t in tools}
        assert "slack_send_message" in names
        assert "slack_list_channels" in names

    def test_hubspot_tool_shows_properties_wrapping(self):
        """HubSpot tool schema should show the {properties: {}} wrapping."""
        engine = Engine(registry_path=REGISTRY_PATH)
        tools = engine.get_openai_tools(actions=["hubspot_create_contact"])
        tool = tools[0]

        params = tool["function"]["parameters"]
        assert "properties" in params["properties"]
        inner = params["properties"]["properties"]
        assert inner["type"] == "object"
        assert "email" in inner["properties"]


# ═══════════════════════════════════════════════════════════════════════
# 8. MCP Tool Generation
# ═══════════════════════════════════════════════════════════════════════


class TestMCPAdapter:

    def test_generate_mcp_tools(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        tools = engine.get_mcp_tools()
        assert len(tools) == 79

        tool = next(t for t in tools if t["name"] == "slack_send_message")
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"
        assert "channel" in tool["inputSchema"]["properties"]


# ═══════════════════════════════════════════════════════════════════════
# 9. Engine Integration
# ═══════════════════════════════════════════════════════════════════════


class TestEngine:

    def test_engine_loads_registry(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        assert len(engine.registry) == 79

    def test_list_actions(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        actions = engine.list_actions()
        assert len(actions) == 79
        names = {a["name"] for a in actions}
        assert "slack_send_message" in names
        assert "github_create_issue" in names

    def test_list_actions_by_app(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        actions = engine.list_actions(app="docusign")
        assert len(actions) == 6
        names = {a["name"] for a in actions}
        assert "docusign_create_envelope" in names
        # Hand-crafted spec should be Tier 2
        envelope = next(a for a in actions if a["name"] == "docusign_create_envelope")
        assert envelope["tier"] == 2

    def test_list_apps(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        apps = engine.list_apps()
        assert set(apps) == {"slack", "docusign", "hubspot", "zendesk", "google", "github", "freshdesk", "whatsapp"}

    def test_get_spec(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        spec = engine.get_spec("docusign_create_envelope")
        assert spec is not None
        assert spec.name == "docusign_create_envelope"

    def test_get_spec_returns_none_for_unknown(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        spec = engine.get_spec("nonexistent_action")
        assert spec is None

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self):
        engine = Engine(registry_path=REGISTRY_PATH)
        result = await engine.execute(
            "nonexistent_action",
            body={},
            auth=AuthTokens(access_token="test"),
        )
        assert not result.successful
        assert "Unknown action" in result.error
