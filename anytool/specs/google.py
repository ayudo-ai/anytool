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

GMAIL_GET_ATTACHMENT = ActionSpec(
    name="gmail_get_attachment",
    app="google",
    description=(
        "Download an attachment from a Gmail message. Returns the attachment data as base64. "
        "Use the attachment_id from trigger webhook payloads or from gmail_get_message response."
    ),
    method="GET",
    path="/gmail/v1/users/me/messages/{message_id}/attachments/{attachment_id}",
    params=[
        ParamSpec(name="message_id", type="string", required=True, location="path", description="The message ID containing the attachment"),
        ParamSpec(name="attachment_id", type="string", required=True, location="path", description="The attachment ID to download"),
    ],
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
    request_transform="sheets_append",
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


# ── Google Calendar ──────────────────────────────────────────────────

CALENDAR_LIST_EVENTS = ActionSpec(
    name="calendar_list_events",
    app="google",
    description=(
        "List upcoming events from a Google Calendar. "
        "Defaults to primary calendar. Use timeMin/timeMax for date range."
    ),
    method="GET",
    path="/calendar/v3/calendars/{calendar_id}/events",
    base_url="https://www.googleapis.com",
    params=[
        ParamSpec(name="calendar_id", type="string", required=True, location="path",
                  description="Calendar ID. Use 'primary' for the user's main calendar"),
        ParamSpec(name="timeMin", type="string", required=False, location="query",
                  description="Start of time range (RFC3339, e.g. '2024-01-15T00:00:00Z')"),
        ParamSpec(name="timeMax", type="string", required=False, location="query",
                  description="End of time range (RFC3339)"),
        ParamSpec(name="maxResults", type="integer", required=False, location="query",
                  description="Max events to return (default 10, max 2500)"),
        ParamSpec(name="singleEvents", type="boolean", required=False, location="query",
                  description="Expand recurring events into single instances. Default: false"),
        ParamSpec(name="orderBy", type="string", required=False, location="query",
                  description="'startTime' (requires singleEvents=true) or 'updated'"),
        ParamSpec(name="q", type="string", required=False, location="query",
                  description="Free-text search across event fields"),
    ],
)

CALENDAR_GET_EVENT = ActionSpec(
    name="calendar_get_event",
    app="google",
    description="Get a specific calendar event by ID. Returns summary, start/end times, attendees, and description.",
    method="GET",
    path="/calendar/v3/calendars/{calendar_id}/events/{event_id}",
    base_url="https://www.googleapis.com",
    params=[
        ParamSpec(name="calendar_id", type="string", required=True, location="path",
                  description="Calendar ID (use 'primary' for main calendar)"),
        ParamSpec(name="event_id", type="string", required=True, location="path",
                  description="Event ID"),
    ],
    response_ids={"id": "event_id"},
)

CALENDAR_CREATE_EVENT = ActionSpec(
    name="calendar_create_event",
    app="google",
    description=(
        "Create a calendar event. Specify start/end as dateTime (with time) "
        "or date (all-day). Optionally add attendees, location, and description."
    ),
    method="POST",
    path="/calendar/v3/calendars/{calendar_id}/events",
    base_url="https://www.googleapis.com",
    content_type="application/json",
    params=[
        ParamSpec(name="calendar_id", type="string", required=True, location="path",
                  description="Calendar ID (use 'primary' for main calendar)"),
        ParamSpec(name="summary", type="string", required=True,
                  description="Event title"),
        ParamSpec(name="start_datetime", type="string", required=True,
                  description="Start time (RFC3339, e.g. '2024-01-15T10:00:00-05:00') or date for all-day ('2024-01-15')"),
        ParamSpec(name="end_datetime", type="string", required=True,
                  description="End time (RFC3339) or date for all-day"),
        ParamSpec(name="timezone", type="string", required=False,
                  description="Timezone (e.g. 'America/New_York'). Defaults to calendar timezone"),
        ParamSpec(name="description", type="string", required=False,
                  description="Event description (HTML supported)"),
        ParamSpec(name="location", type="string", required=False,
                  description="Event location"),
        ParamSpec(name="attendees", type="list", required=False,
                  description="List of attendee emails, e.g. ['alice@example.com', 'bob@example.com']"),
        ParamSpec(name="send_updates", type="string", required=False, location="query",
                  description="'all' to notify attendees, 'none' for no notifications. Default: 'none'"),
    ],
    request_transform="calendar_event",
    response_ids={"id": "event_id"},
)

CALENDAR_UPDATE_EVENT = ActionSpec(
    name="calendar_update_event",
    app="google",
    description="Update a calendar event — change title, time, attendees, description, or location.",
    method="PATCH",
    path="/calendar/v3/calendars/{calendar_id}/events/{event_id}",
    base_url="https://www.googleapis.com",
    content_type="application/json",
    params=[
        ParamSpec(name="calendar_id", type="string", required=True, location="path",
                  description="Calendar ID"),
        ParamSpec(name="event_id", type="string", required=True, location="path",
                  description="Event ID to update"),
        ParamSpec(name="summary", type="string", required=False,
                  description="Updated event title"),
        ParamSpec(name="start_datetime", type="string", required=False,
                  description="Updated start time (RFC3339)"),
        ParamSpec(name="end_datetime", type="string", required=False,
                  description="Updated end time (RFC3339)"),
        ParamSpec(name="timezone", type="string", required=False,
                  description="Timezone"),
        ParamSpec(name="description", type="string", required=False,
                  description="Updated description"),
        ParamSpec(name="location", type="string", required=False,
                  description="Updated location"),
        ParamSpec(name="attendees", type="list", required=False,
                  description="Replace all attendees (list of emails)"),
        ParamSpec(name="send_updates", type="string", required=False, location="query",
                  description="'all' or 'none'"),
    ],
    request_transform="calendar_event",
    response_ids={"id": "event_id"},
)

CALENDAR_DELETE_EVENT = ActionSpec(
    name="calendar_delete_event",
    app="google",
    description="Delete a calendar event.",
    method="DELETE",
    path="/calendar/v3/calendars/{calendar_id}/events/{event_id}",
    base_url="https://www.googleapis.com",
    params=[
        ParamSpec(name="calendar_id", type="string", required=True, location="path",
                  description="Calendar ID"),
        ParamSpec(name="event_id", type="string", required=True, location="path",
                  description="Event ID to delete"),
        ParamSpec(name="send_updates", type="string", required=False, location="query",
                  description="'all' or 'none'"),
    ],
)

CALENDAR_LIST_CALENDARS = ActionSpec(
    name="calendar_list_calendars",
    app="google",
    description="List all calendars the user has access to. Returns calendar IDs, names, and access roles.",
    method="GET",
    path="/calendar/v3/users/me/calendarList",
    base_url="https://www.googleapis.com",
    params=[
        ParamSpec(name="maxResults", type="integer", required=False, location="query",
                  description="Max calendars to return (default 100)"),
    ],
)


# ── Google Docs ──────────────────────────────────────────────────────

DOCS_GET_DOCUMENT = ActionSpec(
    name="docs_get_document",
    app="google",
    description=(
        "Get a Google Doc by ID. Returns the document title, body content, "
        "headers, footers, and structural elements."
    ),
    method="GET",
    path="/v1/documents/{document_id}",
    base_url="https://docs.googleapis.com",
    params=[
        ParamSpec(name="document_id", type="string", required=True, location="path",
                  description="Google Doc ID (from the URL)"),
    ],
    response_ids={"documentId": "document_id", "title": "document_title"},
)

DOCS_CREATE_DOCUMENT = ActionSpec(
    name="docs_create_document",
    app="google",
    description="Create a new empty Google Doc with a title.",
    method="POST",
    path="/v1/documents",
    base_url="https://docs.googleapis.com",
    content_type="application/json",
    params=[
        ParamSpec(name="title", type="string", required=True,
                  description="Document title"),
    ],
    response_ids={"documentId": "document_id"},
)

DOCS_BATCH_UPDATE = ActionSpec(
    name="docs_batch_update",
    app="google",
    description=(
        "Apply updates to a Google Doc — insert text, delete content, "
        "replace text, update formatting. Pass an array of request objects. "
        "Common requests: insertText, deleteContentRange, replaceAllText."
    ),
    method="POST",
    path="/v1/documents/{document_id}:batchUpdate",
    base_url="https://docs.googleapis.com",
    content_type="application/json",
    params=[
        ParamSpec(name="document_id", type="string", required=True, location="path",
                  description="Google Doc ID"),
        ParamSpec(name="requests", type="list", required=True,
                  description=(
                      "List of update requests. Examples: "
                      '[{"insertText": {"location": {"index": 1}, "text": "Hello world"}}], '
                      '[{"replaceAllText": {"containsText": {"text": "old"}, "replaceText": "new"}}]'
                  )),
    ],
    request_transform="docs_batch_update",
)

DOCS_INSERT_TEXT = ActionSpec(
    name="docs_insert_text",
    app="google",
    description=(
        "Insert text into a Google Doc at a specific position. "
        "Use index=1 to insert at the beginning of the document."
    ),
    method="POST",
    path="/v1/documents/{document_id}:batchUpdate",
    base_url="https://docs.googleapis.com",
    content_type="application/json",
    params=[
        ParamSpec(name="document_id", type="string", required=True, location="path",
                  description="Google Doc ID"),
        ParamSpec(name="text", type="string", required=True,
                  description="Text to insert"),
        ParamSpec(name="index", type="integer", required=False,
                  description="Position to insert at (1 = beginning of doc). Default: 1"),
    ],
    request_transform="docs_insert_text",
)

DOCS_REPLACE_TEXT = ActionSpec(
    name="docs_replace_text",
    app="google",
    description="Find and replace all occurrences of text in a Google Doc.",
    method="POST",
    path="/v1/documents/{document_id}:batchUpdate",
    base_url="https://docs.googleapis.com",
    content_type="application/json",
    params=[
        ParamSpec(name="document_id", type="string", required=True, location="path",
                  description="Google Doc ID"),
        ParamSpec(name="find_text", type="string", required=True,
                  description="Text to find"),
        ParamSpec(name="replace_text", type="string", required=True,
                  description="Replacement text"),
        ParamSpec(name="match_case", type="boolean", required=False,
                  description="Case-sensitive matching. Default: true"),
    ],
    request_transform="docs_replace_text",
)


# ── Export all specs ─────────────────────────────────────────────────

GOOGLE_SPECS = [
    # Gmail
    GMAIL_SEND_EMAIL,
    GMAIL_SEARCH,
    GMAIL_GET_MESSAGE,
    GMAIL_GET_THREAD,
    GMAIL_REPLY,
    GMAIL_GET_ATTACHMENT,
    GMAIL_CREATE_LABEL,
    GMAIL_MODIFY_LABELS,
    # Sheets
    SHEETS_APPEND_ROW,
    SHEETS_READ_RANGE,
    # Drive
    DRIVE_LIST_FILES,
    DRIVE_GET_FILE,
    # Calendar
    CALENDAR_LIST_EVENTS,
    CALENDAR_GET_EVENT,
    CALENDAR_CREATE_EVENT,
    CALENDAR_UPDATE_EVENT,
    CALENDAR_DELETE_EVENT,
    CALENDAR_LIST_CALENDARS,
    # Docs
    DOCS_GET_DOCUMENT,
    DOCS_CREATE_DOCUMENT,
    DOCS_BATCH_UPDATE,
    DOCS_INSERT_TEXT,
    DOCS_REPLACE_TEXT,
]
