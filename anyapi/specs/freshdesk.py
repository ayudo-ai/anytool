"""
Freshdesk API v2 specs.

Auth: API key (Base64 encoded as `{api_key}:X` in Basic auth header).
Nango handles this — Freshdesk integration uses API key auth.

Base URL: https://{domain}.freshdesk.com/api/v2
The domain comes from the Nango connection config.

Key actions for AI ops automation:
- Create ticket (customer reports issue)
- Reply to ticket (agent sends response)
- Update ticket (change status, priority, assignee)
- Get ticket (check current state)
- List tickets (filter by status, requester, etc.)
- Add note (internal comment)
- List agents (for assignment)
- Search tickets (full-text search)
"""

from __future__ import annotations

from anyapi.specs.base import ActionSpec, ParamSpec


# ── Create Ticket ────────────────────────────────────────────────────

FRESHDESK_CREATE_TICKET = ActionSpec(
    name="freshdesk_create_ticket",
    app="freshdesk",
    description=(
        "Create a new support ticket. Requires either email or requester_id. "
        "Set status: 2=Open, 3=Pending, 4=Resolved, 5=Closed. "
        "Set priority: 1=Low, 2=Medium, 3=High, 4=Urgent."
    ),
    method="POST",
    path="/api/v2/tickets",
    content_type="application/json",
    params=[
        ParamSpec(name="subject", type="string", required=True,
                  description="Ticket subject line"),
        ParamSpec(name="description", type="string", required=True,
                  description="Ticket description (HTML supported)"),
        ParamSpec(name="email", type="string", required=False,
                  description="Requester's email address"),
        ParamSpec(name="requester_id", type="integer", required=False,
                  description="Requester's Freshdesk user ID (alternative to email)"),
        ParamSpec(name="status", type="integer", required=False,
                  description="2=Open, 3=Pending, 4=Resolved, 5=Closed. Default: 2"),
        ParamSpec(name="priority", type="integer", required=False,
                  description="1=Low, 2=Medium, 3=High, 4=Urgent. Default: 1"),
        ParamSpec(name="type", type="string", required=False,
                  description="Ticket type (e.g. 'Question', 'Incident', 'Problem')"),
        ParamSpec(name="group_id", type="integer", required=False,
                  description="Group to assign ticket to"),
        ParamSpec(name="responder_id", type="integer", required=False,
                  description="Agent to assign ticket to"),
        ParamSpec(name="tags", type="list", required=False,
                  description="List of tags, e.g. ['billing', 'urgent']"),
        ParamSpec(name="cc_emails", type="list", required=False,
                  description="CC email addresses"),
    ],
    response_ids={"id": "ticket_id"},
)


# ── Get Ticket ───────────────────────────────────────────────────────

FRESHDESK_GET_TICKET = ActionSpec(
    name="freshdesk_get_ticket",
    app="freshdesk",
    description=(
        "Get a ticket by ID. Returns subject, description, status, priority, "
        "requester, assignee, timestamps, and custom fields."
    ),
    method="GET",
    path="/api/v2/tickets/{ticket_id}",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Freshdesk ticket ID"),
        ParamSpec(name="include", type="string", required=False, location="query",
                  description="Include extra data: 'conversations', 'requester', 'stats'"),
    ],
    response_ids={"id": "ticket_id"},
)


# ── Update Ticket ────────────────────────────────────────────────────

FRESHDESK_UPDATE_TICKET = ActionSpec(
    name="freshdesk_update_ticket",
    app="freshdesk",
    description=(
        "Update a ticket's status, priority, assignee, or other fields. "
        "Status: 2=Open, 3=Pending, 4=Resolved, 5=Closed. "
        "Priority: 1=Low, 2=Medium, 3=High, 4=Urgent."
    ),
    method="PUT",
    path="/api/v2/tickets/{ticket_id}",
    content_type="application/json",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Freshdesk ticket ID"),
        ParamSpec(name="status", type="integer", required=False,
                  description="2=Open, 3=Pending, 4=Resolved, 5=Closed"),
        ParamSpec(name="priority", type="integer", required=False,
                  description="1=Low, 2=Medium, 3=High, 4=Urgent"),
        ParamSpec(name="responder_id", type="integer", required=False,
                  description="Agent ID to assign to"),
        ParamSpec(name="group_id", type="integer", required=False,
                  description="Group ID to assign to"),
        ParamSpec(name="type", type="string", required=False,
                  description="Ticket type"),
        ParamSpec(name="subject", type="string", required=False,
                  description="Updated subject"),
        ParamSpec(name="tags", type="list", required=False,
                  description="Replace all tags"),
    ],
    response_ids={"id": "ticket_id"},
)


# ── Reply to Ticket ──────────────────────────────────────────────────

FRESHDESK_REPLY_TICKET = ActionSpec(
    name="freshdesk_reply_ticket",
    app="freshdesk",
    description=(
        "Send a public reply to a ticket. The reply is visible to the customer. "
        "Use freshdesk_add_note for internal-only comments."
    ),
    method="POST",
    path="/api/v2/tickets/{ticket_id}/reply",
    content_type="application/json",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Freshdesk ticket ID"),
        ParamSpec(name="body", type="string", required=True,
                  description="Reply body (HTML supported)"),
        ParamSpec(name="cc_emails", type="list", required=False,
                  description="CC email addresses"),
        ParamSpec(name="bcc_emails", type="list", required=False,
                  description="BCC email addresses"),
    ],
    response_ids={"id": "conversation_id"},
)


# ── Add Note ─────────────────────────────────────────────────────────

FRESHDESK_ADD_NOTE = ActionSpec(
    name="freshdesk_add_note",
    app="freshdesk",
    description=(
        "Add a note to a ticket. By default notes are private (internal). "
        "Set private=false to make it visible to the customer."
    ),
    method="POST",
    path="/api/v2/tickets/{ticket_id}/notes",
    content_type="application/json",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Freshdesk ticket ID"),
        ParamSpec(name="body", type="string", required=True,
                  description="Note body (HTML supported)"),
        ParamSpec(name="private", type="boolean", required=False,
                  description="True for internal note, False for public. Default: True"),
    ],
    response_ids={"id": "note_id"},
)


# ── List Tickets ─────────────────────────────────────────────────────

FRESHDESK_LIST_TICKETS = ActionSpec(
    name="freshdesk_list_tickets",
    app="freshdesk",
    description=(
        "List tickets with optional filters. "
        "Filter by requester, status, or updated date. "
        "Returns up to 30 tickets per page."
    ),
    method="GET",
    path="/api/v2/tickets",
    params=[
        ParamSpec(name="email", type="string", required=False, location="query",
                  description="Filter by requester email"),
        ParamSpec(name="requester_id", type="integer", required=False, location="query",
                  description="Filter by requester ID"),
        ParamSpec(name="updated_since", type="string", required=False, location="query",
                  description="Tickets updated after this date (ISO 8601)"),
        ParamSpec(name="order_by", type="string", required=False, location="query",
                  description="Order by: created_at, due_by, updated_at, status. Default: created_at"),
        ParamSpec(name="order_type", type="string", required=False, location="query",
                  description="'asc' or 'desc'. Default: desc"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number (30 tickets per page)"),
        ParamSpec(name="include", type="string", required=False, location="query",
                  description="Include extra: 'requester', 'stats', 'description'"),
    ],
)


# ── Search Tickets ───────────────────────────────────────────────────

FRESHDESK_SEARCH_TICKETS = ActionSpec(
    name="freshdesk_search_tickets",
    app="freshdesk",
    description=(
        "Search tickets using Freshdesk query language. "
        "Example queries: \"status:2 AND priority:4\", "
        "\"tag:'billing'\", \"requester_email:'user@example.com'\". "
        "Returns up to 30 results."
    ),
    method="GET",
    path="/api/v2/search/tickets",
    params=[
        ParamSpec(name="query", type="string", required=True, location="query",
                  description=(
                      "Freshdesk search query in quotes. Examples: "
                      "\"status:2 AND priority:4\", "
                      "\"tag:'urgent'\", "
                      "\"requester_email:'john@example.com'\""
                  )),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)


# ── Get Ticket Conversations ─────────────────────────────────────────

FRESHDESK_GET_CONVERSATIONS = ActionSpec(
    name="freshdesk_get_conversations",
    app="freshdesk",
    description=(
        "Get all conversations (replies and notes) for a ticket. "
        "Returns the full thread history."
    ),
    method="GET",
    path="/api/v2/tickets/{ticket_id}/conversations",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Freshdesk ticket ID"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)


# ── List Agents ──────────────────────────────────────────────────────

FRESHDESK_LIST_AGENTS = ActionSpec(
    name="freshdesk_list_agents",
    app="freshdesk",
    description=(
        "List all agents in the Freshdesk account. "
        "Useful for finding agent IDs for ticket assignment."
    ),
    method="GET",
    path="/api/v2/agents",
    params=[
        ParamSpec(name="email", type="string", required=False, location="query",
                  description="Filter by agent email"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)


# ── Delete Ticket ────────────────────────────────────────────────────

FRESHDESK_DELETE_TICKET = ActionSpec(
    name="freshdesk_delete_ticket",
    app="freshdesk",
    description="Delete (trash) a ticket. Can be restored from trash within 30 days.",
    method="DELETE",
    path="/api/v2/tickets/{ticket_id}",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Freshdesk ticket ID to delete"),
    ],
)


# ── Export ────────────────────────────────────────────────────────────

FRESHDESK_SPECS = [
    FRESHDESK_CREATE_TICKET,
    FRESHDESK_GET_TICKET,
    FRESHDESK_UPDATE_TICKET,
    FRESHDESK_REPLY_TICKET,
    FRESHDESK_ADD_NOTE,
    FRESHDESK_LIST_TICKETS,
    FRESHDESK_SEARCH_TICKETS,
    FRESHDESK_GET_CONVERSATIONS,
    FRESHDESK_LIST_AGENTS,
    FRESHDESK_DELETE_TICKET,
]
