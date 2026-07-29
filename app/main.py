import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import ask, correlation, factors, optimizer, portfolios, risk, stress
from app.limiter import limiter
from app.models.database import init_db

# Comma-separated allowlist, e.g. "http://localhost:5173,https://risklens.app".
# No wildcard: an open CORS policy would let any website read a visitor's
# portfolio data through their browser.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="RiskLens API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Enforces the Limiter's default_limits on every route, including ones
# without an explicit @limiter.limit(...) decorator.
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(portfolios.router)
app.include_router(risk.router)
app.include_router(factors.router)
app.include_router(correlation.router)
app.include_router(optimizer.router)
app.include_router(stress.router)
app.include_router(ask.router)


@app.get("/health")
def health():
    return {"status": "ok"}
