from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics.stress import run_stress_tests
from app.models.database import User, get_db
from app.services.auth import get_current_user
from app.services.context import load_portfolio_context

router = APIRouter(prefix="/portfolios", tags=["stress"])


@router.get("/{portfolio_id}/stress")
def get_stress(
    portfolio_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    try:
        ctx = load_portfolio_context(db, portfolio_id, current_user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"scenarios": run_stress_tests(ctx.prices, ctx.weights)}
