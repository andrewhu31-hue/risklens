"""Shared loader used by every analytics endpoint.

  * Holdings with the same ticker are aggregated (lots summed), never overwritten.
  * The price matrix keeps each asset's own history (see prices.get_price_matrix).
  * Return-based analytics use the window where *all holdings* have prices; that
    window, and the holding that limits it, are reported rather than hidden. The
    benchmark never shortens it (beta is computed on the overlap separately).
  * A failed provider call falls back to cached data with a warning; only a
    ticker with no cached data at all is an error.
"""
from collections import OrderedDict
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.returns import aligned_returns
from app.models.database import Holding, Portfolio
from app.services.prices import get_price_matrix, sync_prices

MIN_OBSERVATIONS = 20  # fewer daily returns than this gives meaningless statistics
STALE_AFTER_DAYS = 10  # a holding whose last price is this much older than the rest is stale


class PortfolioNotFound(ValueError):
    def __init__(self):
        super().__init__("portfolio not found")


class AnalyticsUnavailable(ValueError):
    """The request is valid but the data cannot support the analysis (400)."""


class MarketDataUnavailable(RuntimeError):
    """The price provider failed and nothing is cached (503)."""


@dataclass
class PortfolioContext:
    portfolio: Portfolio
    holdings: list[Holding]
    tickers: list[str]
    benchmark: str | None
    prices: pd.DataFrame
    weights: dict[str, float]
    shares: dict[str, float]
    returns: pd.DataFrame | None = None
    benchmark_returns: pd.Series | None = None
    beta_frame: pd.DataFrame | None = None  # holdings + benchmark returns on their common dates
    warnings: list[str] = field(default_factory=list)
    stale_tickers: list[str] = field(default_factory=list)
    window: dict = field(default_factory=dict)


def get_owned_portfolio(db: Session, portfolio_id: str, user_id: str) -> Portfolio:
    """Loads a portfolio and verifies `user_id` owns it.

    Missing and not-owned both raise the identical "not found" error — a
    non-owner shouldn't be able to tell the difference between an ID that
    doesn't exist and one that belongs to someone else.
    """
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None or portfolio.owner_id != user_id:
        raise PortfolioNotFound()
    return portfolio


def aggregate_shares(holdings: list[Holding]) -> "OrderedDict[str, float]":
    shares: OrderedDict[str, float] = OrderedDict()
    for h in holdings:
        shares[h.ticker] = shares.get(h.ticker, 0.0) + float(h.shares)
    return shares


def load_portfolio_context(db: Session, portfolio_id: str, user_id: str, need_returns: bool = True) -> PortfolioContext:
    portfolio = get_owned_portfolio(db, portfolio_id, user_id)

    holdings = list(portfolio.holdings)
    if not holdings:
        raise AnalyticsUnavailable("portfolio has no holdings")

    shares = aggregate_shares(holdings)
    tickers = list(shares)
    benchmark = (portfolio.benchmark or "SPY").upper()
    all_tickers = list(dict.fromkeys(tickers + [benchmark]))

    errors = sync_prices(db, all_tickers)
    prices = get_price_matrix(db, all_tickers)
    warnings: list[str] = []

    def has_data(t: str) -> bool:
        return t in prices.columns and prices[t].notna().any()

    failed_uncached = [t for t in tickers if t in errors and not has_data(t)]
    if failed_uncached:
        raise MarketDataUnavailable(
            "market data provider unavailable and no cached prices for: " + ", ".join(failed_uncached)
        )
    for t, msg in errors.items():
        if has_data(t):
            warnings.append(f"{t}: using cached prices; refresh failed ({msg})")

    no_data = [t for t in tickers if not has_data(t)]
    if no_data:
        raise AnalyticsUnavailable(f"no price history found for: {', '.join(no_data)} (check the ticker symbol)")

    if not has_data(benchmark):
        warnings.append(f"benchmark {benchmark} has no price history; beta is unavailable")
        benchmark_ok = None
    else:
        benchmark_ok = benchmark

    last_dates = {t: prices[t].last_valid_index() for t in tickers}
    latest_market_date = max(last_dates.values())
    stale = [t for t, d in last_dates.items() if (latest_market_date - d).days > STALE_AFTER_DAYS]
    for t in stale:
        warnings.append(f"{t}: last price is from {last_dates[t].date()} (delisted or not trading); weight uses that price")

    values = {t: shares[t] * float(prices[t].dropna().iloc[-1]) for t in tickers}
    total = sum(values.values())
    if not total > 0:
        raise AnalyticsUnavailable("portfolio has zero total market value")
    weights = {t: v / total for t, v in values.items()}

    ctx = PortfolioContext(
        portfolio=portfolio,
        holdings=holdings,
        tickers=tickers,
        benchmark=benchmark_ok,
        prices=prices,
        weights=weights,
        shares=dict(shares),
        warnings=warnings,
        stale_tickers=stale,
    )
    if need_returns:
        _attach_returns(ctx)
    return ctx


def _attach_returns(ctx: PortfolioContext) -> None:
    prices, tickers = ctx.prices, ctx.tickers
    first_dates = {t: prices[t].first_valid_index() for t in tickers}
    returns = aligned_returns(prices, tickers)
    limiting = max(first_dates, key=first_dates.get)
    if len(returns) < MIN_OBSERVATIONS:
        raise AnalyticsUnavailable(
            f"not enough overlapping price history: {len(returns)} daily returns where all holdings traded "
            f"(need {MIN_OBSERVATIONS}); {limiting} only has prices since {first_dates[limiting].date()}"
        )
    ctx.returns = returns
    ctx.window = {
        "start": returns.index[0].date().isoformat(),
        "end": returns.index[-1].date().isoformat(),
        "observations": int(len(returns)),
        "limited_by": limiting if len(tickers) > 1 else None,
    }
    earliest = min(first_dates.values())
    if len(tickers) > 1 and (first_dates[limiting] - earliest).days > 365:
        ctx.warnings.append(
            f"risk statistics cover {ctx.window['start']} to {ctx.window['end']} because {limiting} "
            f"only has prices since {first_dates[limiting].date()}"
        )
    if ctx.benchmark:
        cols = list(dict.fromkeys(tickers + [ctx.benchmark]))
        both = aligned_returns(prices, cols)
        if len(both) >= 2:
            ctx.beta_frame = both
            ctx.benchmark_returns = both[ctx.benchmark]
