import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import ask, auth, correlation, factors, optimizer, performance, portfolios, risk, stress
from app.api.deps import SafeJSONResponse, sanitize
from app.limiter import limiter
from app.models.database import init_db

# Comma-separated allowlist, e.g. "http://localhost:5173,https://risklens.app".
# No wildcard: an open CORS policy would let any website read a visitor's
# portfolio data through their browser. (When the frontend and API share an
# origin, as on Vercel, CORS is not involved at all.)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="RiskLens API", lifespan=lifespan, default_response_class=SafeJSONResponse)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Applies the default limit to routes defined directly on `app` (e.g. /health);
# router routes carry explicit @limiter.limit decorators.
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Echoing the rejected input back can include NaN/Infinity, which is not valid
    # JSON and used to turn a 422 into a 500. Return location + message only.
    errors = [
        {"loc": list(e.get("loc", [])), "msg": e.get("msg", "invalid value"), "type": e.get("type", "value_error")}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content=sanitize({"detail": errors}))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(auth.router)
app.include_router(portfolios.router)
app.include_router(risk.router)
app.include_router(performance.router)
app.include_router(factors.router)
app.include_router(correlation.router)
app.include_router(optimizer.router)
app.include_router(stress.router)
app.include_router(ask.router)


@app.get("/health")
def health():
    """Liveness plus which database backend is in use and whether it answers."""
    from sqlalchemy import text

    from app.models.database import IS_SQLITE, engine
    from app.services.ai import key_status, model_name

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "sqlite (temporary)" if IS_SQLITE and os.getenv("VERCEL") else ("sqlite" if IS_SQLITE else "postgresql"),
        "database_ok": db_ok,
        "ai_configured": key_status() == "present",
        "ai_key": key_status(),  # missing | malformed | present (never the key)
        "ai_model": model_name(),
    }
