from slowapi import Limiter
from slowapi.util import get_remote_address

# Baseline limit applied to every route via SlowAPIMiddleware; individual
# endpoints (e.g. /ask, /refresh, CSV upload) tighten this with their own
# @limiter.limit(...) decorator, which overrides the default.
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
