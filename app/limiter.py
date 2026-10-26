import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

# Per-route limits. They are applied with explicit @limiter.limit(...) decorators
# on every route: SlowAPIMiddleware's default_limits are not enforced for routes
# that live on included APIRouters in current FastAPI versions.
ANALYTICS_LIMIT = "60/minute"
WRITE_LIMIT = "30/minute"
READ_LIMIT = "120/minute"
AUTH_LIMIT = "10/minute"
AI_LIMIT = "20/minute"
REFRESH_LIMIT = "10/minute"


def client_ip(request: Request) -> str:
    # On Vercel the platform sets X-Forwarded-For itself, so it is trustworthy
    # there; elsewhere use the socket peer (configure your proxy explicitly).
    if os.getenv("VERCEL"):
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def rate_limit_key(request: Request) -> str:
    """Signed-in requests are limited per user (not per IP, so users behind one
    NAT or proxy don't share a bucket); anonymous ones per client IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        from app.services.auth import decode_access_token  # avoid an import cycle

        try:
            return "user:" + decode_access_token(auth.removeprefix("Bearer ").strip())
        except Exception:
            pass
    return "ip:" + client_ip(request)


# key_style="endpoint": one bucket per route, not per URL, so switching the
# portfolio id in the path does not reset the limit.
limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=[ANALYTICS_LIMIT],
    key_style="endpoint",
    storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
)
