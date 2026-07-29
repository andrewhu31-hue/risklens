import csv
import io
import re

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.limiter import limiter
from app.models.database import Holding, Portfolio, get_db
from app.services.context import load_portfolio_context
from app.services.review import generate_debrief

router = APIRouter(prefix="/portfolios", tags=["portfolios"])

TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")
MAX_CSV_BYTES = 1_000_000  # 1 MB
MAX_CSV_ROWS = 500


def _validate_ticker(raw: str) -> str:
    ticker = raw.strip().upper()
    if not TICKER_RE.match(ticker):
        raise ValueError(f"invalid ticker: {raw!r}")
    return ticker


def _validate_shares(raw: float) -> float:
    if raw <= 0 or raw > 1_000_000_000:
        raise ValueError("shares must be a positive number")
    return raw


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
    cost_basis: float | None = Field(default=None, ge=0)
    sector: str | None = Field(default=None, max_length=50)

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        return _validate_ticker(v)

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, v: float) -> float:
        return _validate_shares(v)


@router.post("")
def create_portfolio(body: PortfolioCreate, db: Session = Depends(get_db)):
    portfolio = Portfolio(name=body.name, benchmark=body.benchmark)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return {"id": portfolio.id, "name": portfolio.name, "benchmark": portfolio.benchmark}


@router.get("/{portfolio_id}")
def get_portfolio(portfolio_id: str, db: Session = Depends(get_db)):
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(404, "portfolio not found")
    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "benchmark": portfolio.benchmark,
        "holdings": [
            {"ticker": h.ticker, "shares": h.shares, "cost_basis": h.cost_basis, "sector": h.sector}
            for h in portfolio.holdings
        ],
    }


@router.post("/{portfolio_id}/holdings")
def add_holdings(portfolio_id: str, holdings: list[HoldingIn], db: Session = Depends(get_db)):
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(404, "portfolio not found")
    if not holdings:
        raise HTTPException(400, "no holdings provided")
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
    request: Request, portfolio_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(404, "portfolio not found")

    raw = await file.read()
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(413, f"CSV file too large (max {MAX_CSV_BYTES // 1000} KB)")

    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV must be UTF-8 encoded text")

    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise HTTPException(400, "empty CSV file")

    header = {name.strip().lower() for name in reader.fieldnames}
    if not {"ticker", "shares"}.issubset(header):
        raise HTTPException(400, "CSV must have at least 'ticker' and 'shares' columns")

    rows = list(reader)
    if len(rows) > MAX_CSV_ROWS:
        raise HTTPException(400, f"CSV has too many rows (max {MAX_CSV_ROWS})")

    added = 0
    for row in rows:
        norm = {k.strip().lower(): (v.strip() if v else v) for k, v in row.items()}
        if not norm.get("ticker") or not norm.get("shares"):
            continue
        try:
            ticker = _validate_ticker(norm["ticker"])
            shares = _validate_shares(float(norm["shares"]))
            cost_basis = float(norm["cost_basis"]) if norm.get("cost_basis") else None
        except ValueError as e:
            raise HTTPException(400, f"row {added + 1}: {e}")
        db.add(
            Holding(
                portfolio_id=portfolio_id,
                ticker=ticker,
                shares=shares,
                cost_basis=cost_basis,
                sector=(norm.get("sector") or None),
            )
        )
        added += 1
    db.commit()
    return {"added": added}


@router.post("/{portfolio_id}/refresh")
@limiter.limit("10/minute")
def refresh_portfolio(request: Request, portfolio_id: str, db: Session = Depends(get_db)):
    try:
        ctx = load_portfolio_context(db, portfolio_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

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
    }
