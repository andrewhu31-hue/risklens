from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics.risk import risk_report
from app.models.database import get_db
from app.services.context import load_portfolio_context

router = APIRouter(prefix="/portfolios", tags=["risk"])


@router.get("/{portfolio_id}/risk")
def get_risk(portfolio_id: int, db: Session = Depends(get_db)):
    try:
        ctx = load_portfolio_context(db, portfolio_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return risk_report(ctx.returns[ctx.tickers], ctx.weights, ctx.returns[ctx.benchmark])
