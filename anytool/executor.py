"""
API Executor — constructs and sends HTTP requests from action specs.

Two modes:
  1. Nango proxy mode (recommended): Nango handles auth, we build the request
  2. Direct mode (standalone): We manage tokens ourselves

Both use the same ActionSpecs. The only difference is how auth is injected.
"""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from loguru import logger

from anytool.apps.registry import get_app_config
from anytool.specs.base import ActionSpec


class APIExecutor:
    """Executes API actions. Supports Nango proxy or direct HTTP."""

    def __init__(self, nango=None, oauth_manager=None):
        """
        Args:
            nango: NangoClient instance (proxy mode — recommended)
            oauth_manager: OAuthManager instance (direct mode — standalone)
        """
        self._nango = nango
        self._oauth = oauth_manager

        if not nango and not oauth_manager:
            raise ValueError("Either nango or oauth_manager must be provided")

    async def execute(
        self,
        spec: ActionSpec,
        params: Dict[str, Any],
        provider: str,
        connection_id: str,
        credentials=None,  # Only needed for direct mode
    ) -> Dict[str, Any]:
        """Execute an API action.

        Returns:
            {
                "data": { ... response body ... },
                "status_code": 200,
                "successful": True,
                "extracted_ids": {"thread_id": "xxx", "message_id": "yyy"}
            }
        """
        app_config = get_app_config(spec.app)

        # Build URL parts
        base_url = spec.base_url or app_config.api_base_url
        path = spec.path
        for param in spec.path_params:
            value = params.get(param.name, "")
            path = path.replace(f"{{{param.name}}}", str(value))

        # Build query params
        query = {}
        for param in spec.query_params:
            value = params.get(param.name)
            if value is not None:
                query[param.name] = value

        # Build body
        body = self._build_body(spec, params)

        # Build extra headers
        headers = {}
        if spec.content_type:
            headers["Content-Type"] = spec.content_type

        logger.info(
            f"[anytool.executor] {spec.method} {base_url}{path} | "
            f"action={spec.name} connection={connection_id}"
        )

        # Execute via Nango proxy or direct
        if self._nango:
            result = await self._nango.proxy(
                method=spec.method,
                provider=provider,
                connection_id=connection_id,
                endpoint=path,
                base_url=base_url,
                data=body,
                params=query or None,
                headers=headers or None,
            )
        else:
            # Direct mode — manage tokens ourselves
            result = await self._execute_direct(
                spec, path, base_url, headers, body, query, credentials, connection_id
            )

        # Extract IDs from response
        extracted_ids = {}
        data = result.get("data", {})
        if spec.response_ids and isinstance(data, dict):
            for api_field, fact_name in spec.response_ids.items():
                value = data.get(api_field)
                if value:
                    extracted_ids[fact_name] = str(value)

        result["extracted_ids"] = extracted_ids

        logger.info(
            f"[anytool.executor] {result.get('status_code', '?')} | "
            f"action={spec.name} | ids={extracted_ids or 'none'}"
        )

        return result

    async def _execute_direct(
        self, spec, path, base_url, headers, body, query, credentials, user_id
    ):
        """Direct HTTP execution with self-managed tokens."""
        import httpx

        tokens = await self._oauth.get_valid_tokens(credentials, user_id)
        headers["Authorization"] = tokens.auth_header
        url = f"{base_url.rstrip('/')}{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.request(
                    method=spec.method,
                    url=url,
                    headers=headers,
                    json=body if isinstance(body, dict) else None,
                    content=body if isinstance(body, (str, bytes)) else None,
                    params=query or None,
                )
            except httpx.TimeoutException:
                return {"data": None, "status_code": 0, "successful": False,
                        "error": f"Timeout: {spec.method} {url}"}

        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text[:2000]}

        result = {"data": data, "status_code": resp.status_code, "successful": resp.is_success}
        if not resp.is_success:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:500]}"
        return result

    def _build_body(self, spec: ActionSpec, params: Dict[str, Any]) -> Any:
        """Build the request body from spec + params."""
        if spec.method == "GET":
            return None

        if spec.request_transform == "gmail_mime":
            return self._build_gmail_mime(params)

        if spec.request_transform == "docusign_envelope":
            return self._build_docusign_envelope(params)

        if spec.request_transform == "docusign_void":
            return {"status": "voided", "voidedReason": params.get("voided_reason", "")}

        if spec.request_transform == "docusign_resend":
            return {"resend_envelope": "true"}

        if spec.request_transform == "hubspot_properties":
            return self._build_hubspot_properties(spec, params)

        if spec.request_transform == "hubspot_search":
            return self._build_hubspot_search(params)

        if spec.request_transform == "hubspot_note":
            return self._build_hubspot_note(params)

        if spec.request_transform == "zendesk_ticket":
            return self._build_zendesk_ticket(params)

        if spec.request_transform == "zendesk_ticket_update":
            return self._build_zendesk_ticket_update(params)

        if spec.request_transform == "zendesk_comment":
            return self._build_zendesk_comment(params)

        if spec.request_transform == "calendar_event":
            return self._build_calendar_event(params)

        if spec.request_transform == "docs_batch_update":
            return {"requests": params.get("requests", [])}

        if spec.request_transform == "docs_insert_text":
            return self._build_docs_insert_text(params)

        if spec.request_transform == "docs_replace_text":
            return self._build_docs_replace_text(params)

        if spec.request_transform == "whatsapp_template":
            return self._build_whatsapp_template(params)

        if spec.request_transform == "whatsapp_text":
            return self._build_whatsapp_text(params)

        if spec.request_transform == "whatsapp_media":
            return self._build_whatsapp_media(params, "image")

        if spec.request_transform == "whatsapp_document":
            return self._build_whatsapp_media(params, "document")

        if spec.request_transform == "whatsapp_reaction":
            return self._build_whatsapp_reaction(params)

        if spec.request_transform == "whatsapp_read":
            return {"messaging_product": "whatsapp", "status": "read", "message_id": params.get("message_id", "")}

        if spec.body_template:
            body = {}
            for key, template in spec.body_template.items():
                if isinstance(template, str) and template.startswith("{") and template.endswith("}"):
                    param_name = template[1:-1]
                    body[key] = params.get(param_name)
                else:
                    body[key] = template
            return body

        body = {}
        for param in spec.body_params:
            value = params.get(param.name)
            if value is not None:
                body[param.name] = value

        return body if body else None

    def _build_gmail_mime(self, params: Dict[str, Any]) -> dict:
        """Build Gmail API send request with MIME encoding."""
        msg = MIMEText(params.get("body", ""))
        msg["to"] = params["to"]
        msg["subject"] = params.get("subject", "")

        if params.get("cc"):
            msg["cc"] = params["cc"]
        if params.get("bcc"):
            msg["bcc"] = params["bcc"]
        if params.get("in_reply_to"):
            msg["In-Reply-To"] = params["in_reply_to"]
            msg["References"] = params["in_reply_to"]

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

        body: Dict[str, Any] = {"raw": raw}
        if params.get("thread_id"):
            body["threadId"] = params["thread_id"]

        return body

    def _build_docusign_envelope(self, params: Dict[str, Any]) -> dict:
        """Build DocuSign create envelope payload.

        This is a payload where integration platforms commonly break by turning
        templateRoles: [{roleName: 'Signer', ...}] into [{}].

        We build it directly — no intermediate Pydantic models,
        no serialization that drops nested data.
        """
        body: Dict[str, Any] = {
            "templateId": params["template_id"],
            "status": params.get("status", "sent"),
        }

        # templateRoles — the field that commonly breaks with wrapper-based platforms
        # We pass it EXACTLY as the LLM constructed it.
        template_roles = params.get("template_roles", [])
        if isinstance(template_roles, str):
            import json
            try:
                template_roles = json.loads(template_roles)
            except (json.JSONDecodeError, TypeError):
                template_roles = []

        # Ensure each role has the required camelCase keys DocuSign expects
        formatted_roles = []
        for role in template_roles:
            if not isinstance(role, dict):
                continue
            formatted_role = {
                "roleName": role.get("roleName", role.get("role_name", "")),
                "name": role.get("name", ""),
                "email": role.get("email", ""),
            }
            # Optional fields
            if role.get("clientUserId") or role.get("client_user_id"):
                formatted_role["clientUserId"] = role.get("clientUserId", role.get("client_user_id", ""))
            if role.get("routingOrder") or role.get("routing_order"):
                formatted_role["routingOrder"] = str(role.get("routingOrder", role.get("routing_order", "")))
            if role.get("tabs"):
                formatted_role["tabs"] = role["tabs"]
            formatted_roles.append(formatted_role)

        body["templateRoles"] = formatted_roles

        if params.get("email_subject"):
            body["emailSubject"] = params["email_subject"]
        if params.get("email_body"):
            body["emailBlurb"] = params["email_body"]

        return body

    def _build_hubspot_properties(self, spec: "ActionSpec", params: Dict[str, Any]) -> dict:
        """Build HubSpot CRM object payload.

        HubSpot wraps all fields in {"properties": {"key": "value"}}.
        Path params (like contact_id) are excluded from properties.
        """
        path_param_names = {p.name for p in spec.path_params}
        properties = {}
        for param in spec.body_params:
            if param.name in path_param_names:
                continue
            value = params.get(param.name)
            if value is not None:
                properties[param.name] = str(value) if not isinstance(value, str) else value
        return {"properties": properties}

    def _build_hubspot_search(self, params: Dict[str, Any]) -> dict:
        """Build HubSpot search payload with filterGroups."""
        body: Dict[str, Any] = {}

        if params.get("query"):
            body["query"] = params["query"]

        if params.get("filter_property") and params.get("filter_value"):
            body["filterGroups"] = [{
                "filters": [{
                    "propertyName": params["filter_property"],
                    "operator": params.get("filter_operator", "EQ"),
                    "value": params["filter_value"],
                }]
            }]

        if params.get("limit"):
            body["limit"] = params["limit"]

        if params.get("properties"):
            props = params["properties"]
            if isinstance(props, str):
                props = [p.strip() for p in props.split(",")]
            body["properties"] = props

        return body

    def _build_hubspot_note(self, params: Dict[str, Any]) -> dict:
        """Build HubSpot note with associations."""
        body: Dict[str, Any] = {
            "properties": {
                "hs_note_body": params.get("body", ""),
            }
        }

        if params.get("hubspot_owner_id"):
            body["properties"]["hubspot_owner_id"] = params["hubspot_owner_id"]

        # Build associations
        associations = []
        assoc_map = {
            "contact_id": ("contacts", "note_to_contact"),
            "company_id": ("companies", "note_to_company"),
            "deal_id": ("deals", "note_to_deal"),
        }
        for param_name, (obj_type, assoc_type) in assoc_map.items():
            obj_id = params.get(param_name)
            if obj_id:
                associations.append({
                    "to": {"id": str(obj_id)},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": assoc_type}]
                })

        if associations:
            body["associations"] = associations

        return body

    def _build_zendesk_ticket(self, params: Dict[str, Any]) -> dict:
        """Build Zendesk create ticket payload.

        Zendesk wraps everything in {"ticket": {...}} and the first
        comment goes inside as {"comment": {"body": "..."}}.
        """
        ticket: Dict[str, Any] = {
            "subject": params.get("subject", ""),
            "comment": {"body": params.get("body", "")},
        }

        if params.get("requester_email"):
            ticket["requester"] = {"email": params["requester_email"]}
        elif params.get("requester_id"):
            ticket["requester_id"] = params["requester_id"]

        for field in ("priority", "status", "type", "assignee_id", "group_id", "tags", "custom_fields"):
            if params.get(field) is not None:
                ticket[field] = params[field]

        return {"ticket": ticket}

    def _build_zendesk_ticket_update(self, params: Dict[str, Any]) -> dict:
        """Build Zendesk update ticket payload."""
        ticket: Dict[str, Any] = {}

        for field in ("status", "priority", "assignee_id", "group_id", "subject", "tags", "custom_fields", "type"):
            if params.get(field) is not None:
                ticket[field] = params[field]

        if params.get("comment_body"):
            ticket["comment"] = {
                "body": params["comment_body"],
                "public": params.get("comment_public", True),
            }

        return {"ticket": ticket}

    def _build_zendesk_comment(self, params: Dict[str, Any]) -> dict:
        """Build Zendesk add comment payload (via ticket update)."""
        comment: Dict[str, Any] = {
            "body": params.get("body", ""),
            "public": params.get("public", True),
        }
        if params.get("author_id"):
            comment["author_id"] = params["author_id"]

        return {"ticket": {"comment": comment}}

    def _build_calendar_event(self, params: Dict[str, Any]) -> dict:
        """Build Google Calendar event payload.

        Handles dateTime vs date (all-day) and attendees list.
        """
        body: Dict[str, Any] = {}

        if params.get("summary"):
            body["summary"] = params["summary"]
        if params.get("description"):
            body["description"] = params["description"]
        if params.get("location"):
            body["location"] = params["location"]

        tz = params.get("timezone", "")

        # Start time — detect all-day (date only) vs timed event
        if params.get("start_datetime"):
            start = params["start_datetime"]
            if len(start) <= 10:  # "2024-01-15" → all-day
                body["start"] = {"date": start}
            else:
                body["start"] = {"dateTime": start}
                if tz:
                    body["start"]["timeZone"] = tz

        if params.get("end_datetime"):
            end = params["end_datetime"]
            if len(end) <= 10:
                body["end"] = {"date": end}
            else:
                body["end"] = {"dateTime": end}
                if tz:
                    body["end"]["timeZone"] = tz

        # Attendees
        if params.get("attendees"):
            attendees = params["attendees"]
            if isinstance(attendees, str):
                attendees = [a.strip() for a in attendees.split(",")]
            body["attendees"] = [{"email": email} for email in attendees]

        return body

    def _build_docs_insert_text(self, params: Dict[str, Any]) -> dict:
        """Build Google Docs insertText batchUpdate payload."""
        index = params.get("index", 1)
        return {
            "requests": [{
                "insertText": {
                    "location": {"index": index},
                    "text": params.get("text", ""),
                }
            }]
        }

    def _build_docs_replace_text(self, params: Dict[str, Any]) -> dict:
        """Build Google Docs replaceAllText batchUpdate payload."""
        return {
            "requests": [{
                "replaceAllText": {
                    "containsText": {
                        "text": params.get("find_text", ""),
                        "matchCase": params.get("match_case", True),
                    },
                    "replaceText": params.get("replace_text", ""),
                }
            }]
        }

    def _build_whatsapp_template(self, params: Dict[str, Any]) -> dict:
        """Build WhatsApp template message payload."""
        body: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": params.get("to", ""),
            "type": "template",
            "template": {
                "name": params.get("template_name", ""),
                "language": {
                    "code": params.get("language_code", "en_US"),
                },
            },
        }
        if params.get("components"):
            components = params["components"]
            if isinstance(components, str):
                import json
                try:
                    components = json.loads(components)
                except (json.JSONDecodeError, TypeError):
                    components = []
            body["template"]["components"] = components
        return body

    def _build_whatsapp_text(self, params: Dict[str, Any]) -> dict:
        """Build WhatsApp text message payload."""
        body: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": params.get("to", ""),
            "type": "text",
            "text": {
                "body": params.get("body", ""),
            },
        }
        if params.get("preview_url"):
            body["text"]["preview_url"] = True
        return body

    def _build_whatsapp_media(self, params: Dict[str, Any], media_type: str) -> dict:
        """Build WhatsApp image/document message payload."""
        body: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": params.get("to", ""),
            "type": media_type,
        }
        media: Dict[str, Any] = {}
        if media_type == "image":
            if params.get("image_url"):
                media["link"] = params["image_url"]
            elif params.get("image_id"):
                media["id"] = params["image_id"]
            if params.get("caption"):
                media["caption"] = params["caption"]
        elif media_type == "document":
            if params.get("document_url"):
                media["link"] = params["document_url"]
            elif params.get("document_id"):
                media["id"] = params["document_id"]
            if params.get("filename"):
                media["filename"] = params["filename"]
            if params.get("caption"):
                media["caption"] = params["caption"]
        body[media_type] = media
        return body

    def _build_whatsapp_reaction(self, params: Dict[str, Any]) -> dict:
        """Build WhatsApp reaction payload."""
        return {
            "messaging_product": "whatsapp",
            "to": params.get("to", ""),
            "type": "reaction",
            "reaction": {
                "message_id": params.get("message_id", ""),
                "emoji": params.get("emoji", ""),
            },
        }
