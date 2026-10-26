from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import load_context, meta, portfolio_risk
from app.limiter import ANALYTICS_LIMIT, limiter
from app.models.database import User, get_db
from app.services.auth import get_current_user

router = APIRouter(prefix="/portfolios", tags=["risk"])


@router.get("/{portfolio_id}/risk")
@limiter.limit(ANALYTICS_LIMIT)
def get_risk(
    request: Request,
    portfolio_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctx = load_context(db, portfolio_id, current_user.id)
    return {**portfolio_risk(ctx), **meta(ctx)}
