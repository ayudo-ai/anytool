"""
Zendesk Support API v2 specs.

Auth: OAuth2 via Nango (or API token).
Base URL: https://{subdomain}.zendesk.com/api/v2

Key actions for AI ops automation:
- Tickets: create, get, update, list, search, comment
- Users: get, search, list
- Organizations: get, list
"""

from __future__ import annotations

from anytool.specs.base import ActionSpec, ParamSpec


# ══════════════════════════════════════════════════════════════════════
#  TICKETS
# ══════════════════════════════════════════════════════════════════════

ZENDESK_CREATE_TICKET = ActionSpec(
    name="zendesk_create_ticket",
    app="zendesk",
    description=(
        "Create a new Zendesk support ticket. "
        "Priority: 'low', 'normal', 'high', 'urgent'. "
        "Type: 'problem', 'incident', 'question', 'task'. "
        "Status: 'new', 'open', 'pending', 'hold', 'solved', 'closed'."
    ),
    method="POST",
    path="/api/v2/tickets",
    content_type="application/json",
    params=[
        ParamSpec(name="subject", type="string", required=True,
                  description="Ticket subject line"),
        ParamSpec(name="body", type="string", required=True,
                  description="Ticket description / first comment body"),
        ParamSpec(name="requester_email", type="string", required=False,
                  description="Requester's email (creates user if not found)"),
        ParamSpec(name="requester_id", type="integer", required=False,
                  description="Requester's Zendesk user ID (alternative to email)"),
        ParamSpec(name="priority", type="string", required=False,
                  description="'low', 'normal', 'high', 'urgent'"),
        ParamSpec(name="status", type="string", required=False,
                  description="'new', 'open', 'pending', 'hold', 'solved'. Default: 'new'"),
        ParamSpec(name="type", type="string", required=False,
                  description="'problem', 'incident', 'question', 'task'"),
        ParamSpec(name="assignee_id", type="integer", required=False,
                  description="Agent ID to assign to"),
        ParamSpec(name="group_id", type="integer", required=False,
                  description="Group ID to assign to"),
        ParamSpec(name="tags", type="list", required=False,
                  description="List of tags, e.g. ['billing', 'vip']"),
        ParamSpec(name="custom_fields", type="list", required=False,
                  description="List of {id, value} objects for custom fields"),
    ],
    request_transform="zendesk_ticket",
    response_ids={"id": "ticket_id"},
)

ZENDESK_GET_TICKET = ActionSpec(
    name="zendesk_get_ticket",
    app="zendesk",
    description="Get a ticket by ID. Returns subject, description, status, priority, requester, assignee, and timestamps.",
    method="GET",
    path="/api/v2/tickets/{ticket_id}",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Zendesk ticket ID"),
    ],
    response_ids={"id": "ticket_id"},
)

ZENDESK_UPDATE_TICKET = ActionSpec(
    name="zendesk_update_ticket",
    app="zendesk",
    description=(
        "Update a ticket's status, priority, assignee, or add a comment. "
        "Include 'comment' to add a reply. Set 'public' on the comment to control visibility."
    ),
    method="PUT",
    path="/api/v2/tickets/{ticket_id}",
    content_type="application/json",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Zendesk ticket ID"),
        ParamSpec(name="status", type="string", required=False,
                  description="'new', 'open', 'pending', 'hold', 'solved', 'closed'"),
        ParamSpec(name="priority", type="string", required=False,
                  description="'low', 'normal', 'high', 'urgent'"),
        ParamSpec(name="assignee_id", type="integer", required=False,
                  description="Agent ID to assign to"),
        ParamSpec(name="group_id", type="integer", required=False,
                  description="Group ID to assign to"),
        ParamSpec(name="subject", type="string", required=False,
                  description="Updated subject"),
        ParamSpec(name="tags", type="list", required=False,
                  description="Replace all tags"),
        ParamSpec(name="comment_body", type="string", required=False,
                  description="Add a comment/reply to the ticket"),
        ParamSpec(name="comment_public", type="boolean", required=False,
                  description="True for public reply, False for internal note. Default: True"),
        ParamSpec(name="custom_fields", type="list", required=False,
                  description="List of {id, value} objects"),
    ],
    request_transform="zendesk_ticket_update",
    response_ids={"id": "ticket_id"},
)

ZENDESK_LIST_TICKETS = ActionSpec(
    name="zendesk_list_tickets",
    app="zendesk",
    description="List tickets. Returns most recently created tickets first.",
    method="GET",
    path="/api/v2/tickets",
    params=[
        ParamSpec(name="sort_by", type="string", required=False, location="query",
                  description="Sort by: 'created_at', 'updated_at', 'priority', 'status'. Default: 'created_at'"),
        ParamSpec(name="sort_order", type="string", required=False, location="query",
                  description="'asc' or 'desc'. Default: 'desc'"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)

ZENDESK_SEARCH_TICKETS = ActionSpec(
    name="zendesk_search_tickets",
    app="zendesk",
    description=(
        "Search tickets using Zendesk search syntax. "
        "Examples: 'type:ticket status:open priority:high', "
        "'type:ticket requester:user@example.com', "
        "'type:ticket tags:billing created>2024-01-01'."
    ),
    method="GET",
    path="/api/v2/search",
    params=[
        ParamSpec(name="query", type="string", required=True, location="query",
                  description="Zendesk search query (e.g. 'type:ticket status:open priority:urgent')"),
        ParamSpec(name="sort_by", type="string", required=False, location="query",
                  description="Sort by: 'created_at', 'updated_at', 'priority', 'status', 'relevance'"),
        ParamSpec(name="sort_order", type="string", required=False, location="query",
                  description="'asc' or 'desc'"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)

ZENDESK_ADD_COMMENT = ActionSpec(
    name="zendesk_add_comment",
    app="zendesk",
    description=(
        "Add a comment to a ticket. Set public=true for a customer-visible reply, "
        "public=false for an internal note."
    ),
    method="PUT",
    path="/api/v2/tickets/{ticket_id}",
    content_type="application/json",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Zendesk ticket ID"),
        ParamSpec(name="body", type="string", required=True,
                  description="Comment body (HTML supported)"),
        ParamSpec(name="public", type="boolean", required=False,
                  description="True for public reply, False for internal note. Default: True"),
        ParamSpec(name="author_id", type="integer", required=False,
                  description="Author user ID (defaults to authenticated user)"),
    ],
    request_transform="zendesk_comment",
    response_ids={"id": "ticket_id"},
)

ZENDESK_GET_COMMENTS = ActionSpec(
    name="zendesk_get_comments",
    app="zendesk",
    description="Get all comments on a ticket. Returns the full conversation thread.",
    method="GET",
    path="/api/v2/tickets/{ticket_id}/comments",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Zendesk ticket ID"),
        ParamSpec(name="sort_order", type="string", required=False, location="query",
                  description="'asc' or 'desc'. Default: 'asc'"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)

ZENDESK_DELETE_TICKET = ActionSpec(
    name="zendesk_delete_ticket",
    app="zendesk",
    description="Delete a ticket permanently. This cannot be undone.",
    method="DELETE",
    path="/api/v2/tickets/{ticket_id}",
    params=[
        ParamSpec(name="ticket_id", type="integer", required=True, location="path",
                  description="Zendesk ticket ID to delete"),
    ],
)


# ══════════════════════════════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════════════════════════════

ZENDESK_GET_USER = ActionSpec(
    name="zendesk_get_user",
    app="zendesk",
    description="Get a user by ID. Returns name, email, role, organization, and custom fields.",
    method="GET",
    path="/api/v2/users/{user_id}",
    params=[
        ParamSpec(name="user_id", type="integer", required=True, location="path",
                  description="Zendesk user ID"),
    ],
    response_ids={"id": "user_id"},
)

ZENDESK_SEARCH_USERS = ActionSpec(
    name="zendesk_search_users",
    app="zendesk",
    description="Search users by name, email, or other attributes.",
    method="GET",
    path="/api/v2/users/search",
    params=[
        ParamSpec(name="query", type="string", required=True, location="query",
                  description="Search query (searches name and email)"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)

ZENDESK_LIST_AGENTS = ActionSpec(
    name="zendesk_list_agents",
    app="zendesk",
    description="List all agents in the Zendesk account. Useful for finding agent IDs for assignment.",
    method="GET",
    path="/api/v2/users",
    params=[
        ParamSpec(name="role", type="string", required=False, location="query",
                  description="Filter by role: 'agent', 'admin'. Default: returns all users"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)


# ══════════════════════════════════════════════════════════════════════
#  ORGANIZATIONS
# ══════════════════════════════════════════════════════════════════════

ZENDESK_GET_ORGANIZATION = ActionSpec(
    name="zendesk_get_organization",
    app="zendesk",
    description="Get an organization by ID.",
    method="GET",
    path="/api/v2/organizations/{organization_id}",
    params=[
        ParamSpec(name="organization_id", type="integer", required=True, location="path",
                  description="Zendesk organization ID"),
    ],
    response_ids={"id": "organization_id"},
)

ZENDESK_LIST_ORGANIZATIONS = ActionSpec(
    name="zendesk_list_organizations",
    app="zendesk",
    description="List all organizations.",
    method="GET",
    path="/api/v2/organizations",
    params=[
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)


# ── Export ────────────────────────────────────────────────────────────

ZENDESK_SPECS = [
    # Tickets
    ZENDESK_CREATE_TICKET,
    ZENDESK_GET_TICKET,
    ZENDESK_UPDATE_TICKET,
    ZENDESK_LIST_TICKETS,
    ZENDESK_SEARCH_TICKETS,
    ZENDESK_ADD_COMMENT,
    ZENDESK_GET_COMMENTS,
    ZENDESK_DELETE_TICKET,
    # Users
    ZENDESK_GET_USER,
    ZENDESK_SEARCH_USERS,
    ZENDESK_LIST_AGENTS,
    # Organizations
    ZENDESK_GET_ORGANIZATION,
    ZENDESK_LIST_ORGANIZATIONS,
]
