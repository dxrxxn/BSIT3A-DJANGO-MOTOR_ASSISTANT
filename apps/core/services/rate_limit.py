"""Small cache-backed request throttles.

The default Django cache is local-memory in this project.  This limits
accidental duplicate requests and casual abuse on a single process; a
multi-worker deployment should configure a shared cache (Redis, Memcached, or
a database cache) so every worker sees the same counters.
"""
from __future__ import annotations

import time

from django.core.cache import cache


def check_rate_limit(scope, identity, *, limit, window_seconds=60):
    """Return (allowed, retry_after_seconds, remaining).

    Counters are bucketed by time window, so a denied request can be retried
    after the bucket rolls over.  The function fails open if the cache backend
    is unavailable; the AI provider budget and upload checks remain in force.
    """
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 30
    window_seconds = max(1, int(window_seconds))
    bucket = int(time.time()) // window_seconds
    key = f'rate:{scope}:{identity}:{bucket}'
    try:
        current = cache.get(key, 0)
        if current >= limit:
            return False, window_seconds, 0
        if current == 0:
            cache.set(key, 1, timeout=window_seconds + 5)
        else:
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, current + 1, timeout=window_seconds + 5)
        return True, 0, max(0, limit - current - 1)
    except Exception:
        return True, 0, limit
