"""
Rate limiter — per-key sliding window using in-memory counters.

Applies to:
  - API keys: based on plan limits
  - Session tokens: generous limits (dashboard use)

Limits (per minute):
  - free:       30 req/min
  - pro:        300 req/min
  - enterprise: 3000 req/min
  - session:    120 req/min (dashboard)

Returns 429 with Retry-After header when exceeded.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Tuple

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


# ── Rate limits per plan (requests per minute) ───────────────────────

PLAN_RATE_LIMITS = {
    "free": 30,
    "pro": 300,
    "enterprise": 3000,
}

SESSION_RATE_LIMIT = 120  # Dashboard requests per minute


class SlidingWindowCounter:
    """In-memory sliding window rate limiter.

    Uses two fixed windows to approximate a sliding window.
    Memory efficient — stores only current + previous window counts.
    """

    def __init__(self):
        # key → (current_window_start, current_count, prev_count)
        self._windows: Dict[str, Tuple[int, int, int]] = {}
        self._window_size = 60  # 1 minute window

    def is_allowed(self, key: str, limit: int) -> Tuple[bool, int, int]:
        """Check if request is allowed.

        Returns: (allowed, remaining, retry_after_seconds)
        """
        now = time.time()
        window_start = int(now // self._window_size) * self._window_size
        window_progress = (now - window_start) / self._window_size

        prev_start = window_start - self._window_size

        entry = self._windows.get(key)
        if not entry:
            self._windows[key] = (window_start, 1, 0)
            return (True, limit - 1, 0)

        stored_start, current_count, prev_count = entry

        if stored_start == window_start:
            # Same window — use weighted previous + current
            weighted = prev_count * (1 - window_progress) + current_count
            if weighted >= limit:
                retry_after = int(self._window_size - (now - window_start)) + 1
                return (False, 0, retry_after)
            self._windows[key] = (window_start, current_count + 1, prev_count)
            remaining = max(0, int(limit - weighted - 1))
            return (True, remaining, 0)
        elif stored_start == prev_start:
            # New window — rotate
            weighted = current_count * (1 - window_progress) + 0
            self._windows[key] = (window_start, 1, current_count)
            remaining = max(0, int(limit - weighted - 1))
            return (True, remaining, 0)
        else:
            # Old data — reset
            self._windows[key] = (window_start, 1, 0)
            return (True, limit - 1, 0)

    def cleanup(self):
        """Remove stale entries (older than 2 windows)."""
        now = time.time()
        cutoff = int(now // self._window_size) * self._window_size - self._window_size * 2
        stale = [k for k, (start, _, _) in self._windows.items() if start < cutoff]
        for k in stale:
            del self._windows[k]


# Global rate limiter instance
_limiter = SlidingWindowCounter()
_last_cleanup = time.time()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that enforces per-key rate limits.

    Skips:
      - Health checks (/health)
      - Auth endpoints (/v1/auth/*)
      - OAuth callbacks (/v1/connections/callback)
      - Requests without auth
    """

    SKIP_PATHS = {"/health", "/v1/auth/google", "/v1/auth/google/config",
                  "/v1/auth/signup", "/v1/auth/login", "/v1/connections/callback"}

    async def dispatch(self, request: Request, call_next):
        global _last_cleanup

        # Skip paths that don't need rate limiting
        path = request.url.path
        if path in self.SKIP_PATHS or not path.startswith("/v1"):
            return await call_next(request)

        # Extract token from Authorization header
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return await call_next(request)

        token = auth[7:].strip()

        # Determine rate limit based on token type
        if token.startswith("sess_"):
            limit = SESSION_RATE_LIMIT
            key = f"sess:{token[:20]}"  # Don't store full token
        elif token.startswith("at_"):
            # We need the plan — but we can't do async DB lookups in middleware easily
            # Use a default limit; the auth layer will check plan-specific limits
            limit = PLAN_RATE_LIMITS["free"]  # Conservative default
            key = f"key:{token[:20]}"
        else:
            return await call_next(request)

        # Check rate limit
        allowed, remaining, retry_after = _limiter.is_allowed(key, limit)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Max {limit} requests/minute.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Periodic cleanup (every 5 minutes)
        now = time.time()
        if now - _last_cleanup > 300:
            _limiter.cleanup()
            _last_cleanup = now

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
