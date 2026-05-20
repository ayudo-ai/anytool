"""
Webhook signature verification — use this in your webhook handler
to verify that webhook payloads actually came from anytool.

Usage (Python / FastAPI):

    from anytool.webhook import verify_webhook

    @app.post("/webhooks/inbox")
    async def handle_webhook(request: Request):
        body = await request.body()
        signature = request.headers.get("x-anytool-signature", "")

        if not verify_webhook(body, signature, "whsec_your_secret"):
            raise HTTPException(401, "Invalid signature")

        payload = json.loads(body)
        # process payload...

Usage (Python / Flask):

    from anytool.webhook import verify_webhook

    @app.route("/webhooks/inbox", methods=["POST"])
    def handle_webhook():
        body = request.get_data()
        signature = request.headers.get("X-Anytool-Signature", "")

        if not verify_webhook(body, signature, "whsec_your_secret"):
            abort(401)

        payload = request.get_json()
        # process payload...

Usage (Node.js):

    const crypto = require("crypto");

    function verifyWebhook(body, signature, secret) {
        const expected = "sha256=" + crypto
            .createHmac("sha256", secret)
            .update(body)
            .digest("hex");
        return crypto.timingSafeEqual(
            Buffer.from(signature),
            Buffer.from(expected)
        );
    }
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Union


def verify_webhook(
    payload: Union[bytes, str, dict],
    signature: str,
    secret: str,
) -> bool:
    """Verify an anytool webhook signature.

    Args:
        payload: The raw request body (bytes, string, or parsed dict).
                 If dict, it will be JSON-serialized.
        signature: The X-Anytool-Signature header value (e.g. "sha256=abc123...")
        secret: Your webhook secret (from ANYTOOL_WEBHOOK_SECRET or dashboard)

    Returns:
        True if the signature is valid, False otherwise.

    Example:
        body = await request.body()
        sig = request.headers["x-anytool-signature"]
        assert verify_webhook(body, sig, "whsec_xxx")
    """
    if not signature or not secret:
        return False

    # Normalize payload to bytes
    if isinstance(payload, dict):
        payload_bytes = json.dumps(payload, default=str).encode()
    elif isinstance(payload, str):
        payload_bytes = payload.encode()
    else:
        payload_bytes = payload

    # Compute expected signature
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(signature, expected)


def sign_webhook(payload: Union[bytes, str, dict], secret: str) -> str:
    """Sign a webhook payload. Used internally by the trigger engine.

    Returns the signature string to put in X-Anytool-Signature header.
    """
    if isinstance(payload, dict):
        payload_bytes = json.dumps(payload, default=str).encode()
    elif isinstance(payload, str):
        payload_bytes = payload.encode()
    else:
        payload_bytes = payload

    sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"
