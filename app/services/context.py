from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.returns import log_returns
from app.models.database import Holding, Portfolio
from app.services.prices import ensure_price_history, get_price_matrix


@dataclass
class PortfolioContext:
    portfolio: Portfolio
    holdings: list[Holding]
    tickers: list[str]
    benchmark: str
    prices: pd.DataFrame
    returns: pd.DataFrame
    weights: dict[str, float]


def get_owned_portfolio(db: Session, portfolio_id: str, user_id: str) -> Portfolio:
    """Loads a portfolio and verifies `user_id` owns it.

    Missing and not-owned both raise the identical "not found" error — a
    non-owner shouldn't be able to tell the difference between an ID that
    doesn't exist and one that belongs to someone else.
    """
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None or portfolio.owner_id != user_id:
        raise ValueError("portfolio not found")
    return portfolio


def load_portfolio_context(db: Session, portfolio_id: str, user_id: str) -> PortfolioContext:
    portfolio = get_owned_portfolio(db, portfolio_id, user_id)

    holdings = portfolio.holdings
    if not holdings:
        raise ValueError("portfolio has no holdings")

    tickers = [h.ticker for h in holdings]
    benchmark = portfolio.benchmark or "SPY"
    all_tickers = sorted(set(tickers) | {benchmark})

    for ticker in all_tickers:
        ensure_price_history(db, ticker)

    prices = get_price_matrix(db, all_tickers)
    missing = [t for t in tickers if t not in prices.columns]
    if prices.empty or missing:
        raise ValueError(
            f"insufficient price history for: {', '.join(missing) or 'all holdings'}"
        )

    returns = log_returns(prices)

    latest = prices.iloc[-1]
    values = {h.ticker: h.shares * latest[h.ticker] for h in holdings}
    total = sum(values.values())
    if total <= 0:
        raise ValueError("portfolio has zero total market value")
    weights = {t: v / total for t, v in values.items()}

    return PortfolioContext(
        portfolio=portfolio,
        holdings=holdings,
        tickers=tickers,
        benchmark=benchmark,
        prices=prices,
        returns=returns,
        weights=weights,
    )
