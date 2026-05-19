"""
DocuSign eSign API specs.

This is the exact integration that was BROKEN on Composio —
templateRoles nested objects were serialized as [{}].

With anyapi, we build the exact JSON payload. No intermediate
Pydantic models. No serialization bugs. What you pass is what
DocuSign receives.

Key detail: DocuSign requires account_id in every URL path.
The account_id comes from the OAuth userinfo response and is
stored in token metadata by Nango (or our standalone OAuth).
We use a special request_transform="docusign_account_id" to
inject it at runtime.

Demo base: https://demo.docusign.net/restapi/v2.1
Prod base: https://na1.docusign.net/restapi/v2.1 (varies by account)
"""

from __future__ import annotations

from anyapi.specs.base import ActionSpec, ParamSpec


# ── Create Envelope from Template ────────────────────────────────────
# This is THE action that was broken on Composio.
# Composio turned templateRoles: [{roleName: "Signer", ...}] into [{}]

DOCUSIGN_CREATE_ENVELOPE = ActionSpec(
    name="docusign_create_envelope",
    app="docusign",
    description=(
        "Create and send a DocuSign envelope from a template. "
        "Specify template_roles with roleName, name, and email for each signer. "
        "Set status='sent' to send immediately, or 'created' to save as draft."
    ),
    method="POST",
    path="/restapi/v2.1/accounts/{account_id}/envelopes",
    content_type="application/json",
    params=[
        ParamSpec(
            name="account_id",
            type="string",
            required=True,
            location="path",
            description="DocuSign account ID (from connection metadata)",
        ),
        ParamSpec(
            name="template_id",
            type="string",
            required=True,
            description="Template ID to create envelope from",
        ),
        ParamSpec(
            name="template_roles",
            type="list",
            required=True,
            description=(
                "List of template role assignments. Each must have: "
                "roleName (must match template role), name (signer full name), "
                "email (signer email). Example: "
                '[{"roleName": "Signer", "name": "John Doe", "email": "john@example.com"}]'
            ),
        ),
        ParamSpec(
            name="status",
            type="string",
            required=False,
            description="'sent' to send immediately, 'created' for draft. Default: 'sent'",
        ),
        ParamSpec(
            name="email_subject",
            type="string",
            required=False,
            description="Custom email subject line for the envelope",
        ),
        ParamSpec(
            name="email_body",
            type="string",
            required=False,
            description="Custom email body message",
        ),
    ],
    request_transform="docusign_envelope",
    response_ids={"envelopeId": "envelope_id"},
)


# ── Get Envelope Status ──────────────────────────────────────────────

DOCUSIGN_GET_ENVELOPE = ActionSpec(
    name="docusign_get_envelope",
    app="docusign",
    description=(
        "Get the status and details of a DocuSign envelope. "
        "Returns status (sent, delivered, completed, voided, declined), "
        "recipient info, and timestamps."
    ),
    method="GET",
    path="/restapi/v2.1/accounts/{account_id}/envelopes/{envelope_id}",
    params=[
        ParamSpec(name="account_id", type="string", required=True, location="path",
                  description="DocuSign account ID"),
        ParamSpec(name="envelope_id", type="string", required=True, location="path",
                  description="Envelope ID to check"),
    ],
    response_ids={"envelopeId": "envelope_id"},
)


# ── List Envelopes ───────────────────────────────────────────────────

DOCUSIGN_LIST_ENVELOPES = ActionSpec(
    name="docusign_list_envelopes",
    app="docusign",
    description=(
        "List envelopes in the account. Filter by date, status, or search text. "
        "Returns envelope IDs, subjects, statuses, and timestamps."
    ),
    method="GET",
    path="/restapi/v2.1/accounts/{account_id}/envelopes",
    params=[
        ParamSpec(name="account_id", type="string", required=True, location="path",
                  description="DocuSign account ID"),
        ParamSpec(name="from_date", type="string", required=False, location="query",
                  description="Start date (ISO 8601, e.g. '2024-01-01T00:00:00Z')"),
        ParamSpec(name="status", type="string", required=False, location="query",
                  description="Filter by status: sent, delivered, completed, voided, declined"),
        ParamSpec(name="search_text", type="string", required=False, location="query",
                  description="Search in envelope subjects and recipient names"),
        ParamSpec(name="count", type="integer", required=False, location="query",
                  description="Max envelopes to return (default 10)"),
    ],
)


# ── Get Envelope Recipients ──────────────────────────────────────────

DOCUSIGN_GET_RECIPIENTS = ActionSpec(
    name="docusign_get_recipients",
    app="docusign",
    description=(
        "Get recipient details for an envelope. "
        "Returns each signer's name, email, status (sent, delivered, completed, declined), "
        "and when they signed."
    ),
    method="GET",
    path="/restapi/v2.1/accounts/{account_id}/envelopes/{envelope_id}/recipients",
    params=[
        ParamSpec(name="account_id", type="string", required=True, location="path",
                  description="DocuSign account ID"),
        ParamSpec(name="envelope_id", type="string", required=True, location="path",
                  description="Envelope ID"),
    ],
)


# ── Void Envelope ────────────────────────────────────────────────────

DOCUSIGN_VOID_ENVELOPE = ActionSpec(
    name="docusign_void_envelope",
    app="docusign",
    description=(
        "Void (cancel) a sent envelope. The envelope must not be completed. "
        "Requires a reason for voiding."
    ),
    method="PUT",
    path="/restapi/v2.1/accounts/{account_id}/envelopes/{envelope_id}",
    content_type="application/json",
    params=[
        ParamSpec(name="account_id", type="string", required=True, location="path",
                  description="DocuSign account ID"),
        ParamSpec(name="envelope_id", type="string", required=True, location="path",
                  description="Envelope ID to void"),
        ParamSpec(name="voided_reason", type="string", required=True,
                  description="Reason for voiding the envelope"),
    ],
    request_transform="docusign_void",
)


# ── Resend Envelope ──────────────────────────────────────────────────

DOCUSIGN_RESEND_ENVELOPE = ActionSpec(
    name="docusign_resend_envelope",
    app="docusign",
    description=(
        "Resend notifications for a sent envelope. "
        "Sends a new email to recipients who haven't completed signing."
    ),
    method="PUT",
    path="/restapi/v2.1/accounts/{account_id}/envelopes/{envelope_id}/recipients",
    content_type="application/json",
    params=[
        ParamSpec(name="account_id", type="string", required=True, location="path",
                  description="DocuSign account ID"),
        ParamSpec(name="envelope_id", type="string", required=True, location="path",
                  description="Envelope ID to resend"),
    ],
    request_transform="docusign_resend",
)


# ── Export ────────────────────────────────────────────────────────────

DOCUSIGN_SPECS = [
    DOCUSIGN_CREATE_ENVELOPE,
    DOCUSIGN_GET_ENVELOPE,
    DOCUSIGN_LIST_ENVELOPES,
    DOCUSIGN_GET_RECIPIENTS,
    DOCUSIGN_VOID_ENVELOPE,
    DOCUSIGN_RESEND_ENVELOPE,
]
