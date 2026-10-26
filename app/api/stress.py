from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.analytics.stress import run_stress_tests
from app.api.deps import load_context, meta
from app.limiter import ANALYTICS_LIMIT, limiter
from app.models.database import User, get_db
from app.services.auth import get_current_user

router = APIRouter(prefix="/portfolios", tags=["stress"])


@router.get("/{portfolio_id}/stress")
@limiter.limit(ANALYTICS_LIMIT)
def get_stress(
    request: Request,
    portfolio_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Stress replay works on each holding's own price history, so it doesn't need
    # (and isn't limited by) the common return window.
    ctx = load_context(db, portfolio_id, current_user.id, need_returns=False)
    return {"scenarios": run_stress_tests(ctx.prices, ctx.weights, reference=ctx.benchmark), **meta(ctx)}
