"""
Shared rate limiter instance for TinyChat.

Uses SlowAPI to enforce per-IP rate limits on API endpoints.
Defined here so both the app initialization and route decorators
reference the same Limiter instance.

Rate-limit key function uses get_client_ip() which respects
X-Forwarded-For and X-Real-IP headers, so rate limits apply per
real client even when TinyChat runs behind a reverse proxy or
load balancer (nginx, Caddy, Traefik, AWS ALB, Cloudflare, etc.).

Security note: X-Forwarded-For can be spoofed if the reverse proxy
does not strip or overwrite the header before forwarding. For
self-hosted TinyChat deployments this is an acceptable trade-off;
users concerned about spoofing should configure their proxy to
strip incoming X-Forwarded-For headers before adding its own.

Note: Storage is in-memory (per-process). For multi-worker deployments,
consider configuring a Redis backend via Limiter(storage_uri="redis://...").
For typical single-process TinyChat installs, in-memory is sufficient.

The rate limit itself is configurable via the RATE_LIMIT env var
(default: "20/minute").
"""

import os

from fastapi import Request
from slowapi import Limiter


def _rate_limit_key(request: Request) -> str:
    """
    SlowAPI key function that extracts the real client IP.

    Delegates to app.utils.security.get_client_ip which checks
    X-Forwarded-For → X-Real-IP → request.client.host.
    """
    from app.utils.security import get_client_ip
    return get_client_ip(request)


# Configurable rate limit string (e.g. "20/minute", "100/hour")
RATE_LIMIT = os.getenv("RATE_LIMIT", "20/minute")

limiter = Limiter(key_func=_rate_limit_key)
