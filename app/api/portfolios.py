import csv
import io
import math
import re

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import load_context, meta
from app.limiter import READ_LIMIT, REFRESH_LIMIT, WRITE_LIMIT, limiter
from app.models.database import Holding, Portfolio, User, get_db
from app.services.auth import get_current_user
from app.services.context import PortfolioNotFound, aggregate_shares, get_owned_portfolio
from app.services.review import generate_debrief

router = APIRouter(prefix="/portfolios", tags=["portfolios"])

TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")
MAX_CSV_BYTES = 1_000_000  # 1 MB
MAX_CSV_ROWS = 500
MAX_HOLDINGS_PER_REQUEST = 500
MAX_HOLDINGS_PER_PORTFOLIO = 500
MAX_SHARES = 1_000_000_000


def _validate_ticker(raw: str) -> str:
    ticker = raw.strip().upper()
    if not TICKER_RE.match(ticker):
        raise ValueError(f"invalid ticker: {raw!r}")
    return ticker


def _validate_shares(raw: float) -> float:
    if not math.isfinite(raw) or raw <= 0 or raw > MAX_SHARES:
        raise ValueError(f"shares must be a positive number no larger than {MAX_SHARES:,}")
    return raw


def _validate_cost_basis(raw: float | None) -> float | None:
    if raw is None:
        return None
    if not math.isfinite(raw) or raw < 0:
        raise ValueError("cost_basis must be a non-negative number")
    return raw


def _owned_or_404(db: Session, portfolio_id: str, user: User) -> Portfolio:
    try:
        return get_owned_portfolio(db, portfolio_id, user.id)
    except PortfolioNotFound:
        raise HTTPException(404, "portfolio not found")


def _check_capacity(db: Session, portfolio_id: str, adding: int) -> None:
    existing = db.scalar(select(func.count(Holding.id)).where(Holding.portfolio_id == portfolio_id)) or 0
    if existing + adding > MAX_HOLDINGS_PER_PORTFOLIO:
        raise HTTPException(400, f"a portfolio can hold at most {MAX_HOLDINGS_PER_PORTFOLIO} holdings")


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    benchmark: str = Field(default="SPY", min_length=1, max_length=10)

    @field_validator("benchmark")
    @classmethod
    def validate_benchmark(cls, v: str) -> str:
        return _validate_ticker(v)


class HoldingIn(BaseModel):
    ticker: str
    shares: float
    cost_basis: float | None = None
    sector: str | None = Field(default=None, max_length=50)

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        return _validate_ticker(v)

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, v: float) -> float:
        return _validate_shares(v)

    @field_validator("cost_basis")
    @classmethod
    def validate_cost_basis(cls, v: float | None) -> float | None:
        return _validate_cost_basis(v)


def _portfolio_json(portfolio: Portfolio) -> dict:
    shares = aggregate_shares(portfolio.holdings)
    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "benchmark": portfolio.benchmark,
        "created_at": portfolio.created_at,
        "holdings": [
            {"ticker": h.ticker, "shares": h.shares, "cost_basis": h.cost_basis, "sector": h.sector}
            for h in portfolio.holdings
        ],
        # Lots of the same ticker summed — what the analytics actually use.
        "positions": [{"ticker": t, "shares": s} for t, s in shares.items()],
    }


@router.get("")
@limiter.limit(READ_LIMIT)
def list_portfolios(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.execute(
        select(Portfolio).where(Portfolio.owner_id == current_user.id).order_by(Portfolio.created_at.desc())
    ).scalars()
    return {
        "portfolios": [
            {"id": p.id, "name": p.name, "benchmark": p.benchmark, "created_at": p.created_at, "holdings": len(p.holdings)}
            for p in rows
        ]
    }


@router.post("")
@limiter.limit(WRITE_LIMIT)
def create_portfolio(
    request: Request,
    body: PortfolioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = Portfolio(owner_id=current_user.id, name=body.name, benchmark=body.benchmark)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return {"id": portfolio.id, "name": portfolio.name, "benchmark": portfolio.benchmark}


@router.get("/{portfolio_id}")
@limiter.limit(READ_LIMIT)
def get_portfolio(
    request: Request, portfolio_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return _portfolio_json(_owned_or_404(db, portfolio_id, current_user))


@router.delete("/{portfolio_id}")
@limiter.limit(WRITE_LIMIT)
def delete_portfolio(
    request: Request, portfolio_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    portfolio = _owned_or_404(db, portfolio_id, current_user)
    db.delete(portfolio)
    db.commit()
    return {"deleted": portfolio_id}


@router.delete("/{portfolio_id}/holdings/{ticker}")
@limiter.limit(WRITE_LIMIT)
def delete_holding(
    request: Request,
    portfolio_id: str,
    ticker: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    portfolio = _owned_or_404(db, portfolio_id, current_user)
    ticker = ticker.strip().upper()
    lots = [h for h in portfolio.holdings if h.ticker == ticker]
    if not lots:
        raise HTTPException(404, f"no holding {ticker} in this portfolio")
    for h in lots:
        db.delete(h)
    db.commit()
    return {"deleted": ticker, "lots_removed": len(lots)}


@router.post("/{portfolio_id}/holdings")
@limiter.limit(WRITE_LIMIT)
def add_holdings(
    request: Request,
    portfolio_id: str,
    holdings: list[HoldingIn] = Body(..., max_length=MAX_HOLDINGS_PER_REQUEST),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_or_404(db, portfolio_id, current_user)
    if not holdings:
        raise HTTPException(400, "no holdings provided")
    _check_capacity(db, portfolio_id, len(holdings))
    for h in holdings:
        db.add(
            Holding(
                portfolio_id=portfolio_id,
                ticker=h.ticker,
                shares=h.shares,
                cost_basis=h.cost_basis,
                sector=h.sector,
            )
        )
    db.commit()
    return {"added": len(holdings)}


@router.post("/{portfolio_id}/holdings/csv")
@limiter.limit("10/minute")
async def add_holdings_csv(
    request: Request,
    portfolio_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_or_404(db, portfolio_id, current_user)

    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(413, f"CSV file too large (max {MAX_CSV_BYTES // 1000} KB)")

    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV must be UTF-8 encoded text")

    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise HTTPException(400, "empty CSV file")

    header = {name.strip().lower() for name in reader.fieldnames if name}
    if not {"ticker", "shares"}.issubset(header):
        raise HTTPException(400, "CSV must have at least 'ticker' and 'shares' columns")

    rows = list(reader)
    if len(rows) > MAX_CSV_ROWS:
        raise HTTPException(400, f"CSV has too many rows (max {MAX_CSV_ROWS})")

    parsed = []
    for row_number, row in enumerate(rows, start=1):  # data row number, header excluded
        norm = {(k or "").strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        if not norm.get("ticker") and not norm.get("shares"):
            continue  # blank line
        try:
            ticker = _validate_ticker(norm.get("ticker") or "")
            shares = _validate_shares(float(norm.get("shares") or "nan"))
            cost_basis = _validate_cost_basis(float(norm["cost_basis"])) if norm.get("cost_basis") else None
        except ValueError as e:
            raise HTTPException(400, f"row {row_number}: {e}")
        sector = (norm.get("sector") or None)
        parsed.append(Holding(portfolio_id=portfolio_id, ticker=ticker, shares=shares, cost_basis=cost_basis,
                              sector=sector[:50] if sector else None))

    if not parsed:
        raise HTTPException(400, "CSV contains no holdings")
    _check_capacity(db, portfolio_id, len(parsed))
    db.add_all(parsed)
    db.commit()
    return {"added": len(parsed)}


@router.post("/{portfolio_id}/refresh")
@limiter.limit(REFRESH_LIMIT)
def refresh_portfolio(
    request: Request,
    portfolio_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctx = load_context(db, portfolio_id, current_user.id)
    try:
        debrief = generate_debrief(ctx)
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    return {
        "portfolio_id": portfolio_id,
        "tickers": ctx.tickers,
        "weights": ctx.weights,
        "price_observations": int(ctx.prices.shape[0]),
        "debrief": debrief,
        **meta(ctx),
    }
