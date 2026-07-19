from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics.optimizer import optimizer_report
from app.models.database import get_db
from app.services.context import load_portfolio_context

router = APIRouter(prefix="/portfolios", tags=["optimizer"])


@router.get("/{portfolio_id}/optimize")
def get_optimizer(portfolio_id: int, db: Session = Depends(get_db)):
    try:
        ctx = load_portfolio_context(db, portfolio_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if len(ctx.tickers) < 2:
        raise HTTPException(400, "optimizer requires at least 2 holdings")
    return optimizer_report(ctx.returns[ctx.tickers], ctx.weights)
