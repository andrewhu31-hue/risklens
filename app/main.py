from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import ask, correlation, factors, optimizer, portfolios, risk, stress
from app.limiter import limiter
from app.models.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="RiskLens API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
