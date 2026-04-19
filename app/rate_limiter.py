"""
Shared rate limiter instance for TinyChat.

Uses SlowAPI to enforce per-IP rate limits on API endpoints.
Defined here so both the app initialization and route decorators
reference the same Limiter instance.

Note: Storage is in-memory (per-process). For multi-worker deployments,
consider configuring a Redis backend via Limiter(storage_uri="redis://...").
For typical single-process TinyChat installs, in-memory is sufficient.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
