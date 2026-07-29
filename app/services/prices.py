from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.database import PriceHistory

# Far enough back to cover the 2008 stress-test window.
HISTORY_START = date(2006, 1, 1)


def _cached_range(db: Session, ticker: str) -> tuple[date | None, date | None]:
    row = db.execute(
        select(func.min(PriceHistory.date), func.max(PriceHistory.date)).where(
            PriceHistory.ticker == ticker
        )
    ).one()
    return row[0], row[1]


def ensure_price_history(db: Session, ticker: str) -> None:
    """Fetch and cache any daily price history for `ticker` not already in the DB."""
    min_date, max_date = _cached_range(db, ticker)
    today = date.today()

    if min_date is None:
        fetch_start = HISTORY_START
    elif max_date >= today - timedelta(days=1):
        return
    else:
        fetch_start = max_date + timedelta(days=1)

    data = yf.Ticker(ticker).history(
        start=fetch_start.isoformat(),
        end=(today + timedelta(days=1)).isoformat(),
        auto_adjust=True,
    )
    if data.empty:
        return

    existing_dates: set[date] = set()
    if min_date is not None:
        existing_dates = set(
            db.execute(select(PriceHistory.date).where(PriceHistory.ticker == ticker)).scalars().all()
        )

    new_rows = [
        PriceHistory(ticker=ticker, date=idx.date(), adj_close=float(row["Close"]))
        for idx, row in data.iterrows()
        # yfinance can return a NaN close for the current day's still-in-progress
        # bar (e.g. queried while the market is open) — skip it rather than
        # crash the insert; it'll be fetched properly once the day has closed.
        if idx.date() not in existing_dates and pd.notna(row["Close"])
    ]
    if new_rows:
        db.add_all(new_rows)
        db.commit()


def get_price_series(db: Session, ticker: str) -> pd.Series:
    rows = db.execute(
        select(PriceHistory.date, PriceHistory.adj_close)
        .where(PriceHistory.ticker == ticker)
        .order_by(PriceHistory.date)
    ).all()
    if not rows:
        return pd.Series(dtype=float, name=ticker)
    dates, prices = zip(*rows)
    return pd.Series(list(prices), index=pd.to_datetime(list(dates)), name=ticker)


def get_price_matrix(db: Session, tickers: list[str]) -> pd.DataFrame:
    series = {t: get_price_series(db, t) for t in tickers}
    df = pd.DataFrame(series)
    return df.ffill().dropna()
