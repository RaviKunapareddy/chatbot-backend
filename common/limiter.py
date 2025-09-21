import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared SlowAPI limiter instance for use across the app
# For tests, set DISABLE_RATE_LIMITING to one of: 1 / true / yes (case-insensitive)
# to bypass the limiter and avoid 429s.
RATE_LIMITING_DISABLED = str(os.getenv("DISABLE_RATE_LIMITING", "")).strip().lower() in {
    "1",
    "true",
    "yes",
}

if RATE_LIMITING_DISABLED:

    class _NoopLimiter:
        def limit(self, *args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

    limiter = _NoopLimiter()
else:
    limiter = Limiter(key_func=get_remote_address)


def maybe_limit(rate: str):
    """Return a decorator that applies rate limiting unless disabled.

    Usage in routers: @maybe_limit("10/minute")
    """
    if RATE_LIMITING_DISABLED:

        def _identity_decorator(func):
            return func

        return _identity_decorator
    return limiter.limit(rate)


def is_disabled() -> bool:
    return RATE_LIMITING_DISABLED
