from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.analytics.performance import performance_report
from app.analytics.risk import portfolio_returns
from app.api.deps import load_context, meta
from app.limiter import ANALYTICS_LIMIT, limiter
from app.models.database import User, get_db
from app.services.auth import get_current_user

router = APIRouter(prefix="/portfolios", tags=["performance"])


@router.get("/{portfolio_id}/performance")
@limiter.limit(ANALYTICS_LIMIT)
def get_performance(
    request: Request,
    portfolio_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Growth of 1 at today's weights versus the benchmark, and the drawdown path."""
    ctx = load_context(db, portfolio_id, current_user.id)
    port = portfolio_returns(ctx.returns[ctx.tickers], ctx.weights)
    common = ctx.prices[ctx.tickers].dropna().index
    start = common[common < port.index[0]]
    bench_prices = ctx.prices[ctx.benchmark] if ctx.benchmark else None
    report = performance_report(port, start[-1] if len(start) else None, bench_prices)
    return {**report, "benchmark": ctx.benchmark, **meta(ctx)}
