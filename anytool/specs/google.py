"""
Google API specs — Gmail, Sheets, Drive.

Each action is a dict with:
- method, path, base_url
- params: {name, type, required, description, location (body|query|path)}
- description: what the action does (for LLM tool description)
- response_ids: which fields to auto-extract from response

These are NOT auto-generated from OpenAPI specs. They're hand-curated
for the 80% of actions AI agents actually use, with clear descriptions
that help the LLM construct correct requests.
"""

from __future__ import annotations

from anytool.specs.base import ActionSpec, ParamSpec

# ── Gmail ────────────────────────────────────────────────────────────

GMAIL_SEND_EMAIL = ActionSpec(
    name="gmail_send_email",
    app="google",
    description=(
        "Send an email via Gmail. Constructs a MIME message and sends it. "
        "Returns the message ID and thread ID of the sent email."
    ),
    method="POST",
    path="/gmail/v1/users/me/messages/send",
    content_type="application/json",
    params=[
        ParamSpec(name="to", type="string", required=True, description="Recipient email address"),
        ParamSpec(name="subject", type="string", required=True, description="Email subject line"),
        ParamSpec(name="body", type="string", required=True, description="Email body (plain text)"),
        ParamSpec(name="cc", type="string", required=False, description="CC email addresses, comma-separated"),
        ParamSpec(name="bcc", type="string", required=False, description="BCC email addresses, comma-separated"),
        ParamSpec(name="in_reply_to", type="string", required=False, description="Message-ID to reply to (for threading)"),
        ParamSpec(name="thread_id", type="string", required=False, description="Thread ID to add this message to"),
    ],
    request_transform="gmail_mime",  # Special: needs MIME encoding
    response_ids={"id": "message_id", "threadId": "thread_id"},
)

GMAIL_SEARCH = ActionSpec(
    name="gmail_search",
    app="google",
    description=(
        "Search Gmail messages using Gmail search syntax. "
        "Returns a list of message IDs matching the query. "
        "Use queries like: 'from:user@example.com', 'subject:invoice', 'is:unread', 'newer_than:1d'."
    ),
    method="GET",
    path="/gmail/v1/users/me/messages",
    params=[
        ParamSpec(name="q", type="string", required=True, location="query", description="Gmail search query (same syntax as Gmail search box)"),
        ParamSpec(name="maxResults", type="integer", required=False, location="query", description="Max messages to return (default 10, max 500)"),
        ParamSpec(name="labelIds", type="string", required=False, location="query", description="Comma-separated label IDs to filter by (e.g. INBOX, SENT, DRAFT)"),
    ],
)

GMAIL_GET_MESSAGE = ActionSpec(
    name="gmail_get_message",
    app="google",
    description=(
        "Get a specific Gmail message by ID. Returns full message including headers, body, and attachments. "
        "Use format='metadata' for just headers, 'full' for everything."
    ),
    method="GET",
    path="/gmail/v1/users/me/messages/{message_id}",
    params=[
        ParamSpec(name="message_id", type="string", required=True, location="path", description="The message ID to retrieve"),
        ParamSpec(name="format", type="string", required=False, location="query", description="'full' (default), 'metadata', 'minimal', or 'raw'"),
    ],
    response_ids={"id": "message_id", "threadId": "thread_id"},
)

GMAIL_GET_THREAD = ActionSpec(
    name="gmail_get_thread",
    app="google",
    description=(
        "Get all messages in a Gmail thread. Returns the full conversation. "
        "Use this to get the entire email chain for a thread_id."
    ),
    method="GET",
    path="/gmail/v1/users/me/threads/{thread_id}",
    params=[
        ParamSpec(name="thread_id", type="string", required=True, location="path", description="The thread ID to retrieve"),
        ParamSpec(name="format", type="string", required=False, location="query", description="'full' (default), 'metadata', or 'minimal'"),
    ],
)

GMAIL_REPLY = ActionSpec(
    name="gmail_reply",
    app="google",
    description=(
        "Reply to an existing email thread. Sends a reply in the same thread. "
        "The reply will appear as part of the conversation in Gmail."
    ),
    method="POST",
    path="/gmail/v1/users/me/messages/send",
    content_type="application/json",
    params=[
        ParamSpec(name="to", type="string", required=True, description="Recipient email address"),
        ParamSpec(name="subject", type="string", required=True, description="Email subject (usually 'Re: original subject')"),
        ParamSpec(name="body", type="string", required=True, description="Reply body (plain text)"),
        ParamSpec(name="thread_id", type="string", required=True, description="Thread ID to reply in"),
        ParamSpec(name="in_reply_to", type="string", required=True, description="Message-ID header of the message being replied to"),
    ],
    request_transform="gmail_mime",
    response_ids={"id": "message_id", "threadId": "thread_id"},
)

GMAIL_CREATE_LABEL = ActionSpec(
    name="gmail_create_label",
    app="google",
    description="Create a new Gmail label.",
    method="POST",
    path="/gmail/v1/users/me/labels",
    content_type="application/json",
    params=[
        ParamSpec(name="name", type="string", required=True, description="Label name"),
    ],
    body_template={"name": "{name}"},
)

GMAIL_MODIFY_LABELS = ActionSpec(
    name="gmail_modify_labels",
    app="google",
    description="Add or remove labels from a message. Use to mark as read, archive, star, etc.",
    method="POST",
    path="/gmail/v1/users/me/messages/{message_id}/modify",
    content_type="application/json",
    params=[
        ParamSpec(name="message_id", type="string", required=True, location="path", description="Message ID"),
        ParamSpec(name="addLabelIds", type="list", required=False, description="Label IDs to add (e.g. ['STARRED', 'IMPORTANT'])"),
        ParamSpec(name="removeLabelIds", type="list", required=False, description="Label IDs to remove (e.g. ['UNREAD', 'INBOX'])"),
    ],
)


# ── Google Sheets ────────────────────────────────────────────────────

SHEETS_APPEND_ROW = ActionSpec(
    name="sheets_append_row",
    app="google",
    description=(
        "Append a row to a Google Sheets spreadsheet. "
        "Values are written to the first empty row after the specified range."
    ),
    method="POST",
    path="/v4/spreadsheets/{spreadsheet_id}/values/{range}:append",
    base_url="https://sheets.googleapis.com",
    content_type="application/json",
    params=[
        ParamSpec(name="spreadsheet_id", type="string", required=True, location="path", description="The spreadsheet ID (from the URL)"),
        ParamSpec(name="range", type="string", required=True, location="path", description="Sheet range, e.g. 'Sheet1!A:Z'"),
        ParamSpec(name="values", type="list", required=True, description="Row values as a list, e.g. ['John', 'john@example.com', '2024-01-15']"),
        ParamSpec(name="valueInputOption", type="string", required=False, location="query", description="'RAW' or 'USER_ENTERED' (default: USER_ENTERED)"),
    ],
    body_template={"values": ["{values}"]},
)

SHEETS_READ_RANGE = ActionSpec(
    name="sheets_read_range",
    app="google",
    description="Read values from a Google Sheets range.",
    method="GET",
    path="/v4/spreadsheets/{spreadsheet_id}/values/{range}",
    base_url="https://sheets.googleapis.com",
    params=[
        ParamSpec(name="spreadsheet_id", type="string", required=True, location="path", description="Spreadsheet ID"),
        ParamSpec(name="range", type="string", required=True, location="path", description="Range to read, e.g. 'Sheet1!A1:D10'"),
    ],
)


# ── Google Drive ─────────────────────────────────────────────────────

DRIVE_LIST_FILES = ActionSpec(
    name="drive_list_files",
    app="google",
    description="List files in Google Drive. Supports search queries.",
    method="GET",
    path="/drive/v3/files",
    params=[
        ParamSpec(name="q", type="string", required=False, location="query", description="Search query (e.g. \"name contains 'invoice'\" or \"mimeType='application/pdf'\")"),
        ParamSpec(name="pageSize", type="integer", required=False, location="query", description="Max files to return (default 10, max 1000)"),
        ParamSpec(name="fields", type="string", required=False, location="query", description="Fields to include (default: 'files(id,name,mimeType,modifiedTime)')"),
    ],
)

DRIVE_GET_FILE = ActionSpec(
    name="drive_get_file",
    app="google",
    description="Get metadata for a Google Drive file.",
    method="GET",
    path="/drive/v3/files/{file_id}",
    params=[
        ParamSpec(name="file_id", type="string", required=True, location="path", description="The file ID"),
        ParamSpec(name="fields", type="string", required=False, location="query", description="Fields to return (e.g. 'id,name,mimeType,webViewLink')"),
    ],
)


# ── Export all specs ─────────────────────────────────────────────────

GOOGLE_SPECS = [
    # Gmail
    GMAIL_SEND_EMAIL,
    GMAIL_SEARCH,
    GMAIL_GET_MESSAGE,
    GMAIL_GET_THREAD,
    GMAIL_REPLY,
    GMAIL_CREATE_LABEL,
    GMAIL_MODIFY_LABELS,
    # Sheets
    SHEETS_APPEND_ROW,
    SHEETS_READ_RANGE,
    # Drive
    DRIVE_LIST_FILES,
    DRIVE_GET_FILE,
]
