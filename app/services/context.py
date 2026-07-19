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


def load_portfolio_context(db: Session, portfolio_id: int) -> PortfolioContext:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise ValueError("portfolio not found")

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
