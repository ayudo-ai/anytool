"""
Slack Web API specs.

Auth: OAuth2 Bot Token (via Nango).
Base URL: https://slack.com/api

Slack uses a flat POST-with-JSON pattern for most endpoints.
Some read endpoints use GET with query params.

Key actions for AI ops automation:
- Send message (post to channel or DM)
- Reply in thread
- List channels
- Get message/thread history
- Update message
- Add reaction
"""

from __future__ import annotations

from anyapi.specs.base import ActionSpec, ParamSpec


# ── Send Message ─────────────────────────────────────────────────────

SLACK_SEND_MESSAGE = ActionSpec(
    name="slack_send_message",
    app="slack",
    description=(
        "Send a message to a Slack channel or DM. "
        "Use channel ID (e.g. 'C1234567890') not channel name. "
        "Supports markdown formatting."
    ),
    method="POST",
    path="/chat.postMessage",
    content_type="application/json",
    params=[
        ParamSpec(name="channel", type="string", required=True,
                  description="Channel ID to post to (e.g. 'C1234567890')"),
        ParamSpec(name="text", type="string", required=True,
                  description="Message text (supports Slack markdown)"),
        ParamSpec(name="thread_ts", type="string", required=False,
                  description="Thread timestamp to reply to (makes it a threaded reply)"),
        ParamSpec(name="unfurl_links", type="boolean", required=False,
                  description="Unfurl URLs in the message. Default: true"),
    ],
    response_ids={"ts": "message_ts", "channel": "channel_id"},
)


# ── Update Message ───────────────────────────────────────────────────

SLACK_UPDATE_MESSAGE = ActionSpec(
    name="slack_update_message",
    app="slack",
    description="Update an existing Slack message.",
    method="POST",
    path="/chat.update",
    content_type="application/json",
    params=[
        ParamSpec(name="channel", type="string", required=True,
                  description="Channel ID containing the message"),
        ParamSpec(name="ts", type="string", required=True,
                  description="Timestamp of the message to update"),
        ParamSpec(name="text", type="string", required=True,
                  description="New message text"),
    ],
    response_ids={"ts": "message_ts"},
)


# ── List Channels ────────────────────────────────────────────────────

SLACK_LIST_CHANNELS = ActionSpec(
    name="slack_list_channels",
    app="slack",
    description=(
        "List public channels in the workspace. "
        "Returns channel IDs, names, and topics."
    ),
    method="GET",
    path="/conversations.list",
    params=[
        ParamSpec(name="types", type="string", required=False, location="query",
                  description="Channel types: 'public_channel', 'private_channel', 'mpim', 'im'. Comma-separated. Default: public_channel"),
        ParamSpec(name="limit", type="integer", required=False, location="query",
                  description="Max channels to return (default 100, max 1000)"),
        ParamSpec(name="cursor", type="string", required=False, location="query",
                  description="Pagination cursor from previous response"),
        ParamSpec(name="exclude_archived", type="boolean", required=False, location="query",
                  description="Exclude archived channels. Default: false"),
    ],
)


# ── Get Channel History ──────────────────────────────────────────────

SLACK_GET_HISTORY = ActionSpec(
    name="slack_get_history",
    app="slack",
    description=(
        "Get recent messages from a channel. "
        "Returns messages in reverse chronological order."
    ),
    method="GET",
    path="/conversations.history",
    params=[
        ParamSpec(name="channel", type="string", required=True, location="query",
                  description="Channel ID"),
        ParamSpec(name="limit", type="integer", required=False, location="query",
                  description="Number of messages to return (default 20, max 1000)"),
        ParamSpec(name="oldest", type="string", required=False, location="query",
                  description="Only messages after this timestamp"),
        ParamSpec(name="latest", type="string", required=False, location="query",
                  description="Only messages before this timestamp"),
        ParamSpec(name="cursor", type="string", required=False, location="query",
                  description="Pagination cursor"),
    ],
)


# ── Get Thread Replies ───────────────────────────────────────────────

SLACK_GET_THREAD = ActionSpec(
    name="slack_get_thread",
    app="slack",
    description=(
        "Get all replies in a message thread. "
        "Requires the channel and the parent message timestamp."
    ),
    method="GET",
    path="/conversations.replies",
    params=[
        ParamSpec(name="channel", type="string", required=True, location="query",
                  description="Channel ID containing the thread"),
        ParamSpec(name="ts", type="string", required=True, location="query",
                  description="Timestamp of the parent message"),
        ParamSpec(name="limit", type="integer", required=False, location="query",
                  description="Number of replies to return (default 20)"),
        ParamSpec(name="cursor", type="string", required=False, location="query",
                  description="Pagination cursor"),
    ],
)


# ── Add Reaction ─────────────────────────────────────────────────────

SLACK_ADD_REACTION = ActionSpec(
    name="slack_add_reaction",
    app="slack",
    description=(
        "Add an emoji reaction to a message. "
        "Use emoji name without colons (e.g. 'thumbsup' not ':thumbsup:')."
    ),
    method="POST",
    path="/reactions.add",
    content_type="application/json",
    params=[
        ParamSpec(name="channel", type="string", required=True,
                  description="Channel ID containing the message"),
        ParamSpec(name="timestamp", type="string", required=True,
                  description="Timestamp of the message to react to"),
        ParamSpec(name="name", type="string", required=True,
                  description="Emoji name without colons (e.g. 'thumbsup', 'white_check_mark')"),
    ],
)


# ── Lookup User by Email ─────────────────────────────────────────────

SLACK_LOOKUP_USER = ActionSpec(
    name="slack_lookup_user",
    app="slack",
    description=(
        "Find a Slack user by their email address. "
        "Returns user ID, display name, and profile info."
    ),
    method="GET",
    path="/users.lookupByEmail",
    params=[
        ParamSpec(name="email", type="string", required=True, location="query",
                  description="Email address to look up"),
    ],
)


# ── Export ────────────────────────────────────────────────────────────

SLACK_SPECS = [
    SLACK_SEND_MESSAGE,
    SLACK_UPDATE_MESSAGE,
    SLACK_LIST_CHANNELS,
    SLACK_GET_HISTORY,
    SLACK_GET_THREAD,
    SLACK_ADD_REACTION,
    SLACK_LOOKUP_USER,
]
