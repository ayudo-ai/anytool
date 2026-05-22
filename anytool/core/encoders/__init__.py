"""
Encoders — transform agent-friendly params into API-specific formats.

Only needed for Tier 3 actions (~5 total across all APIs).
If you're adding an encoder for a new action, you're probably
doing it wrong — the LLM should construct the body directly.

Usage:
    from anytool.core.encoders import get_encoder, encode

    # Get encoder by name
    encoder = get_encoder("gmail_mime")
    result = encoder({"to": "...", "subject": "...", "body": "..."})

    # Or use the convenience function
    result = encode("gmail_mime", {"to": "...", "subject": "...", "body": "..."})
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from anytool.core.encoders.gmail_mime import encode_gmail_mime

# Registry of encoder functions
# Each takes agent_params dict → returns API request body dict
ENCODERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "gmail_mime": encode_gmail_mime,
}


def get_encoder(name: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Get an encoder function by name. Raises ValueError if not found."""
    if name not in ENCODERS:
        available = list(ENCODERS.keys())
        raise ValueError(
            f"Unknown encoder '{name}'. Available: {available}. "
            f"Most actions don't need an encoder — check your spec."
        )
    return ENCODERS[name]


def encode(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Run an encoder by name. Convenience wrapper."""
    return get_encoder(name)(params)


def register_encoder(name: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
    """Register a custom encoder at runtime."""
    ENCODERS[name] = fn
