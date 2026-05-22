"""
Gmail MIME encoder — converts friendly email params into base64url-encoded RFC 2822.

This is one of the ~5 encoders in all of anytool.
Gmail's API requires emails as base64url-encoded MIME messages in a 'raw' field.
An LLM cannot do base64 encoding, so this encoder bridges the gap.

Input (from LLM / agent_params):
    {
        "to": "sarah@example.com",
        "subject": "Invoice Follow-up",
        "body": "Hi Sarah, please send the updated invoice.",
        "cc": "manager@example.com",       # optional
        "bcc": "audit@example.com",        # optional
        "reply_to": "billing@example.com", # optional
        "content_type": "text/html",       # optional, default text/plain
        "thread_id": "thread-123",         # optional, for replies
        "in_reply_to": "<msg-id@mail>",    # optional, for threading
        "references": "<msg-id@mail>",     # optional, for threading
    }

Output (sent to Gmail API):
    {
        "raw": "base64url_encoded_mime_message...",
        "threadId": "thread-123"  # only if thread_id was provided
    }
"""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict


def encode_gmail_mime(params: Dict[str, Any]) -> Dict[str, Any]:
    """Convert email params into Gmail API request body.

    Takes friendly params (to, subject, body) and returns
    {raw: base64url_mime, threadId: ...}.
    """
    to = params.get("to", "")
    subject = params.get("subject", "")
    body = params.get("body", "")
    cc = params.get("cc", "")
    bcc = params.get("bcc", "")
    reply_to = params.get("reply_to", "")
    content_type = params.get("content_type", "text/plain")
    thread_id = params.get("thread_id", "")
    in_reply_to = params.get("in_reply_to", "")
    references = params.get("references", "")

    # Build MIME message
    if content_type == "text/html":
        msg = MIMEText(body, "html")
    else:
        msg = MIMEText(body, "plain")

    msg["To"] = to
    msg["Subject"] = subject

    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    if reply_to:
        msg["Reply-To"] = reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    # Base64url encode (no padding, URL-safe)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    # Strip padding (Gmail requires no padding)
    raw = raw.rstrip("=")

    # Build API body
    result: Dict[str, Any] = {"raw": raw}
    if thread_id:
        result["threadId"] = thread_id

    return result
