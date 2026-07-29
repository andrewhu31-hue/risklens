from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics.factors import factor_report
from app.models.database import User, get_db
from app.services.auth import get_current_user
from app.services.context import load_portfolio_context

router = APIRouter(prefix="/portfolios", tags=["factors"])


@router.get("/{portfolio_id}/factors")
def get_factors(
    portfolio_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    try:
        ctx = load_portfolio_context(db, portfolio_id, current_user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return factor_report(ctx.returns[ctx.tickers], ctx.weights)
