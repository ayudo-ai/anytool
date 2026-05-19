"""
WhatsApp Business Cloud API specs.

Auth: Bearer token (System User Token from Meta Business Suite).
Base URL: https://graph.facebook.com/v21.0

The WhatsApp Cloud API uses Meta's Graph API. Key concepts:
- phone_number_id: Your WhatsApp Business phone number ID (not the phone number itself)
- Messages must use pre-approved templates for first contact (24-hour window rule)
- Free-form messages only within 24hrs of customer's last message

Key actions for AI ops automation:
- Send template message (outbound, requires approved template)
- Send text message (within 24hr window)
- Send media message (image, document, video)
- Mark as read
- Get business profile
"""

from __future__ import annotations

from anytool.specs.base import ActionSpec, ParamSpec


# ══════════════════════════════════════════════════════════════════════
#  MESSAGES
# ══════════════════════════════════════════════════════════════════════

WHATSAPP_SEND_TEMPLATE = ActionSpec(
    name="whatsapp_send_template",
    app="whatsapp",
    description=(
        "Send a pre-approved template message to a WhatsApp number. "
        "Use this for first contact or messages outside the 24-hour window. "
        "Templates must be approved in Meta Business Suite first."
    ),
    method="POST",
    path="/{phone_number_id}/messages",
    content_type="application/json",
    params=[
        ParamSpec(name="phone_number_id", type="string", required=True, location="path",
                  description="Your WhatsApp Business phone number ID"),
        ParamSpec(name="to", type="string", required=True,
                  description="Recipient phone number with country code (e.g. '+14155552671')"),
        ParamSpec(name="template_name", type="string", required=True,
                  description="Approved template name (e.g. 'hello_world', 'order_update')"),
        ParamSpec(name="language_code", type="string", required=False,
                  description="Template language code (e.g. 'en_US', 'es'). Default: 'en_US'"),
        ParamSpec(name="components", type="list", required=False,
                  description=(
                      "Template variable values. Example for header + body params: "
                      '[{"type": "body", "parameters": [{"type": "text", "text": "John"}]}]'
                  )),
    ],
    request_transform="whatsapp_template",
    response_ids={"messages[0].id": "message_id"},
)

WHATSAPP_SEND_TEXT = ActionSpec(
    name="whatsapp_send_text",
    app="whatsapp",
    description=(
        "Send a free-form text message. Only works within the 24-hour window "
        "after the customer's last message. For first contact, use whatsapp_send_template."
    ),
    method="POST",
    path="/{phone_number_id}/messages",
    content_type="application/json",
    params=[
        ParamSpec(name="phone_number_id", type="string", required=True, location="path",
                  description="Your WhatsApp Business phone number ID"),
        ParamSpec(name="to", type="string", required=True,
                  description="Recipient phone number with country code"),
        ParamSpec(name="body", type="string", required=True,
                  description="Message text (max 4096 characters)"),
        ParamSpec(name="preview_url", type="boolean", required=False,
                  description="Show URL preview if message contains a link. Default: false"),
    ],
    request_transform="whatsapp_text",
    response_ids={"messages[0].id": "message_id"},
)

WHATSAPP_SEND_IMAGE = ActionSpec(
    name="whatsapp_send_image",
    app="whatsapp",
    description="Send an image message. Provide either a URL or a previously uploaded media ID.",
    method="POST",
    path="/{phone_number_id}/messages",
    content_type="application/json",
    params=[
        ParamSpec(name="phone_number_id", type="string", required=True, location="path",
                  description="Your WhatsApp Business phone number ID"),
        ParamSpec(name="to", type="string", required=True,
                  description="Recipient phone number with country code"),
        ParamSpec(name="image_url", type="string", required=False,
                  description="Public URL of the image (JPEG or PNG)"),
        ParamSpec(name="image_id", type="string", required=False,
                  description="Media ID of a previously uploaded image"),
        ParamSpec(name="caption", type="string", required=False,
                  description="Image caption text"),
    ],
    request_transform="whatsapp_media",
)

WHATSAPP_SEND_DOCUMENT = ActionSpec(
    name="whatsapp_send_document",
    app="whatsapp",
    description="Send a document (PDF, XLSX, DOCX, etc.) via WhatsApp.",
    method="POST",
    path="/{phone_number_id}/messages",
    content_type="application/json",
    params=[
        ParamSpec(name="phone_number_id", type="string", required=True, location="path",
                  description="Your WhatsApp Business phone number ID"),
        ParamSpec(name="to", type="string", required=True,
                  description="Recipient phone number with country code"),
        ParamSpec(name="document_url", type="string", required=False,
                  description="Public URL of the document"),
        ParamSpec(name="document_id", type="string", required=False,
                  description="Media ID of a previously uploaded document"),
        ParamSpec(name="filename", type="string", required=False,
                  description="Display filename (e.g. 'invoice.pdf')"),
        ParamSpec(name="caption", type="string", required=False,
                  description="Document caption text"),
    ],
    request_transform="whatsapp_document",
)

WHATSAPP_SEND_REACTION = ActionSpec(
    name="whatsapp_send_reaction",
    app="whatsapp",
    description="React to a message with an emoji.",
    method="POST",
    path="/{phone_number_id}/messages",
    content_type="application/json",
    params=[
        ParamSpec(name="phone_number_id", type="string", required=True, location="path",
                  description="Your WhatsApp Business phone number ID"),
        ParamSpec(name="to", type="string", required=True,
                  description="Recipient phone number"),
        ParamSpec(name="message_id", type="string", required=True,
                  description="ID of the message to react to"),
        ParamSpec(name="emoji", type="string", required=True,
                  description="Emoji to react with (e.g. '👍', '❤️', '✅')"),
    ],
    request_transform="whatsapp_reaction",
)

WHATSAPP_MARK_READ = ActionSpec(
    name="whatsapp_mark_read",
    app="whatsapp",
    description="Mark a message as read (sends blue check marks to the sender).",
    method="POST",
    path="/{phone_number_id}/messages",
    content_type="application/json",
    params=[
        ParamSpec(name="phone_number_id", type="string", required=True, location="path",
                  description="Your WhatsApp Business phone number ID"),
        ParamSpec(name="message_id", type="string", required=True,
                  description="ID of the message to mark as read"),
    ],
    request_transform="whatsapp_read",
)


# ══════════════════════════════════════════════════════════════════════
#  MEDIA
# ══════════════════════════════════════════════════════════════════════

WHATSAPP_UPLOAD_MEDIA = ActionSpec(
    name="whatsapp_upload_media",
    app="whatsapp",
    description=(
        "Upload media (image, document, video, audio) to WhatsApp servers. "
        "Returns a media ID that can be used in send_image or send_document."
    ),
    method="POST",
    path="/{phone_number_id}/media",
    content_type="application/json",
    params=[
        ParamSpec(name="phone_number_id", type="string", required=True, location="path",
                  description="Your WhatsApp Business phone number ID"),
        ParamSpec(name="messaging_product", type="string", required=True,
                  description="Must be 'whatsapp'"),
        ParamSpec(name="type", type="string", required=True,
                  description="Media type: 'image/jpeg', 'image/png', 'application/pdf', etc."),
        ParamSpec(name="url", type="string", required=True,
                  description="Public URL of the media to upload"),
    ],
    response_ids={"id": "media_id"},
)

WHATSAPP_GET_MEDIA_URL = ActionSpec(
    name="whatsapp_get_media_url",
    app="whatsapp",
    description="Get the download URL for a media file by its ID. URL is valid for 5 minutes.",
    method="GET",
    path="/{media_id}",
    params=[
        ParamSpec(name="media_id", type="string", required=True, location="path",
                  description="Media ID"),
    ],
)


# ══════════════════════════════════════════════════════════════════════
#  BUSINESS PROFILE
# ══════════════════════════════════════════════════════════════════════

WHATSAPP_GET_PROFILE = ActionSpec(
    name="whatsapp_get_profile",
    app="whatsapp",
    description="Get the WhatsApp Business profile — name, about text, address, email, website.",
    method="GET",
    path="/{phone_number_id}/whatsapp_business_profile",
    params=[
        ParamSpec(name="phone_number_id", type="string", required=True, location="path",
                  description="Your WhatsApp Business phone number ID"),
        ParamSpec(name="fields", type="string", required=False, location="query",
                  description="Comma-separated fields: 'about,address,description,email,websites'. Default: all"),
    ],
)


# ── Export ────────────────────────────────────────────────────────────

WHATSAPP_SPECS = [
    # Messages
    WHATSAPP_SEND_TEMPLATE,
    WHATSAPP_SEND_TEXT,
    WHATSAPP_SEND_IMAGE,
    WHATSAPP_SEND_DOCUMENT,
    WHATSAPP_SEND_REACTION,
    WHATSAPP_MARK_READ,
    # Media
    WHATSAPP_UPLOAD_MEDIA,
    WHATSAPP_GET_MEDIA_URL,
    # Profile
    WHATSAPP_GET_PROFILE,
]
