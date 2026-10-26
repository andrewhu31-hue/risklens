from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import load_context, meta
from app.limiter import ANALYTICS_LIMIT, limiter
from app.models.database import User, get_db
from app.services.auth import get_current_user

router = APIRouter(prefix="/portfolios", tags=["correlation"])


@router.get("/{portfolio_id}/correlation")
@limiter.limit(ANALYTICS_LIMIT)
def get_correlation(
    request: Request,
    portfolio_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctx = load_context(db, portfolio_id, current_user.id)
    corr = ctx.returns[ctx.tickers].corr()
    # A holding with constant prices has undefined correlation: returned as null.
    matrix = [[None if v != v else round(float(v), 4) for v in row] for row in corr.values.tolist()]
    return {"tickers": ctx.tickers, "matrix": matrix, **meta(ctx)}
