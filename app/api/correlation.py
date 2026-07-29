from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import User, get_db
from app.services.auth import get_current_user
from app.services.context import load_portfolio_context

router = APIRouter(prefix="/portfolios", tags=["correlation"])


@router.get("/{portfolio_id}/correlation")
def get_correlation(
    portfolio_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    try:
        ctx = load_portfolio_context(db, portfolio_id, current_user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    corr = ctx.returns[ctx.tickers].corr()
    return {"tickers": ctx.tickers, "matrix": corr.round(4).values.tolist()}
