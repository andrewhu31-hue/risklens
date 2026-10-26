"""Helpers shared by the route handlers."""
import math

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.analytics.risk import beta, portfolio_returns, risk_report
from app.services.context import (
    AnalyticsUnavailable,
    MarketDataUnavailable,
    PortfolioContext,
    PortfolioNotFound,
    load_portfolio_context,
)


def load_context(db: Session, portfolio_id: str, user_id: str, need_returns: bool = True) -> PortfolioContext:
    """load_portfolio_context with errors mapped to HTTP: 404 not found / not
    yours, 400 data can't support the analysis, 503 market data unavailable."""
    try:
        return load_portfolio_context(db, portfolio_id, user_id, need_returns=need_returns)
    except PortfolioNotFound:
        raise HTTPException(404, "portfolio not found")
    except AnalyticsUnavailable as e:
        raise HTTPException(400, str(e))
    except MarketDataUnavailable as e:
        raise HTTPException(503, str(e))


def portfolio_risk(ctx: PortfolioContext) -> dict:
    report = risk_report(ctx.returns[ctx.tickers], ctx.weights, None)
    if ctx.beta_frame is not None:
        port = portfolio_returns(ctx.beta_frame[ctx.tickers], ctx.weights)
        report["beta"] = beta(port, ctx.beta_frame[ctx.benchmark])
    report["benchmark"] = ctx.benchmark
    return report


def meta(ctx: PortfolioContext) -> dict:
    return {"window": ctx.window or None, "warnings": ctx.warnings, "stale_tickers": ctx.stale_tickers}


def sanitize(obj):
    """Replace NaN/Infinity (not valid JSON) with None, recursively."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return super().render(sanitize(jsonable_encoder(content)))
