import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.limiter import limiter
from app.models.database import Holding, Portfolio, get_db
from app.services.context import load_portfolio_context
from app.services.review import generate_debrief

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


class PortfolioCreate(BaseModel):
    name: str
    benchmark: str = "SPY"


class HoldingIn(BaseModel):
    ticker: str
    shares: float
    cost_basis: float | None = None
    sector: str | None = None


@router.post("")
def create_portfolio(body: PortfolioCreate, db: Session = Depends(get_db)):
    portfolio = Portfolio(name=body.name, benchmark=body.benchmark.upper())
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return {"id": portfolio.id, "name": portfolio.name, "benchmark": portfolio.benchmark}


@router.get("/{portfolio_id}")
def get_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
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
def add_holdings(portfolio_id: int, holdings: list[HoldingIn], db: Session = Depends(get_db)):
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(404, "portfolio not found")
    if not holdings:
        raise HTTPException(400, "no holdings provided")
    for h in holdings:
        db.add(
            Holding(
                portfolio_id=portfolio_id,
                ticker=h.ticker.strip().upper(),
                shares=h.shares,
                cost_basis=h.cost_basis,
                sector=h.sector,
            )
        )
    db.commit()
    return {"added": len(holdings)}


@router.post("/{portfolio_id}/holdings/csv")
async def add_holdings_csv(
    portfolio_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(404, "portfolio not found")

    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise HTTPException(400, "empty CSV file")

    header = {name.strip().lower() for name in reader.fieldnames}
    if not {"ticker", "shares"}.issubset(header):
        raise HTTPException(400, "CSV must have at least 'ticker' and 'shares' columns")

    added = 0
    for row in reader:
        norm = {k.strip().lower(): (v.strip() if v else v) for k, v in row.items()}
        if not norm.get("ticker") or not norm.get("shares"):
            continue
        db.add(
            Holding(
                portfolio_id=portfolio_id,
                ticker=norm["ticker"].upper(),
                shares=float(norm["shares"]),
                cost_basis=float(norm["cost_basis"]) if norm.get("cost_basis") else None,
                sector=norm.get("sector") or None,
            )
        )
        added += 1
    db.commit()
    return {"added": added}


@router.post("/{portfolio_id}/refresh")
@limiter.limit("10/minute")
def refresh_portfolio(request: Request, portfolio_id: int, db: Session = Depends(get_db)):
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
