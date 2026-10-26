"""Daily price history: fetch from yfinance, cache in `price_history`.

Cache rules
  * A ticker's first fetch (or any cache not known to hold the full history)
    pulls everything from HISTORY_START and replaces what is cached — this also
    backfills caches that started late.
  * After that, only the tail is fetched, with OVERLAP_DAYS of overlap. If the
    provider's overlapping closes differ from the cached ones (a split or
    dividend re-based its adjusted history), the whole history is re-pulled so
    old- and new-basis prices are never mixed.
  * The cache is fresh once it holds the last complete weekday session, so
    weekends and Monday mornings don't trigger a fetch on every request. A ticker
    checked today that is still behind (holiday, no data) is not re-asked for
    RECHECK_AFTER.
  * Provider failures raise PriceProviderError; callers decide whether cached
    data is good enough. Rows are inserted with ON CONFLICT DO NOTHING, so
    concurrent first fetches of one ticker don't collide.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.database import PriceFetch, PriceHistory

if os.getenv("VERCEL"):  # only /tmp is writable on Vercel; yfinance keeps a small cache
    try:
        yf.set_tz_cache_location("/tmp/yfinance-cache")
    except Exception:
        pass

HISTORY_START = date(2006, 1, 1)  # far enough back for the 2008 stress window
OVERLAP_DAYS = 10
ADJUSTMENT_TOLERANCE = 0.005  # 0.5% difference on overlapping closes => re-based history
RECHECK_AFTER = timedelta(hours=6)
PROVIDER_TIMEOUT = 20
MAX_PARALLEL_FETCHES = 8


class PriceProviderError(RuntimeError):
    pass


@dataclass
class _Plan:
    ticker: str
    start: date | None  # None => nothing to fetch
    full: bool
    overlap: pd.Series | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def last_complete_session(today: date) -> date:
    d = today - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _clean(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    s = s[np.isfinite(s.values) & (s.values > 0)]
    s = s[~s.index.duplicated(keep="last")]
    return s.sort_index()


def _fetch(ticker: str, start: date, end: date) -> pd.Series:
    """Call the provider. Returns closes indexed by naive dates (possibly empty)."""
    try:
        data = yf.Ticker(ticker).history(
            start=start.isoformat(), end=end.isoformat(), auto_adjust=True, timeout=PROVIDER_TIMEOUT
        )
    except Exception as e:  # network errors, rate limits, provider bugs
        raise PriceProviderError(f"price provider failed for {ticker}: {e}") from e
    if data is None:
        raise PriceProviderError(f"price provider returned nothing for {ticker}")
    if len(data) == 0:
        return pd.Series(dtype=float)
    if "Close" not in getattr(data, "columns", []):
        raise PriceProviderError(f"price provider returned an unexpected format for {ticker}")
    idx = pd.to_datetime([ts.date() if hasattr(ts, "date") else ts for ts in data.index])
    return _clean(pd.Series(data["Close"].values, index=idx))


def _cached_range(db: Session, ticker: str) -> tuple[date | None, date | None]:
    row = db.execute(
        select(func.min(PriceHistory.date), func.max(PriceHistory.date)).where(PriceHistory.ticker == ticker)
    ).one()
    return row[0], row[1]


def _plan(db: Session, ticker: str, today: date) -> _Plan:
    min_d, max_d = _cached_range(db, ticker)
    log = db.get(PriceFetch, ticker)
    recently_checked = (
        log is not None
        and log.checked_for == today
        and log.checked_at is not None
        and _utcnow() - log.checked_at < RECHECK_AFTER
    )
    skip = _Plan(ticker, None, False)
    if log is None or not log.full_history:
        return _Plan(ticker, HISTORY_START, True)  # first fetch, or a cache never fully loaded
    if min_d is None:  # provider had no data last time
        return skip if recently_checked else _Plan(ticker, HISTORY_START, True)
    if max_d >= last_complete_session(today) or recently_checked:
        return skip
    start = max_d - timedelta(days=OVERLAP_DAYS)
    overlap = get_price_series(db, ticker)
    overlap = overlap[overlap.index >= pd.Timestamp(start)]
    return _Plan(ticker, start, False, overlap)


def _rebased(overlap: pd.Series | None, fetched: pd.Series) -> bool:
    if overlap is None or overlap.empty or fetched.empty:
        return False
    both = pd.concat([overlap, fetched], axis=1, join="inner").dropna()
    if both.empty:
        return False
    rel = (both.iloc[:, 1] / both.iloc[:, 0] - 1).abs()
    return bool((rel > ADJUSTMENT_TOLERANCE).any())


def _dialect_insert(db: Session):
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    elif dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        return None
    return insert


def _insert_rows(db: Session, ticker: str, series: pd.Series) -> None:
    if series.empty:
        return
    rows = [{"ticker": ticker, "date": d.date(), "adj_close": float(p)} for d, p in series.items()]
    insert = _dialect_insert(db)
    if insert is not None:
        for i in range(0, len(rows), 2000):
            stmt = insert(PriceHistory).values(rows[i : i + 2000])
            db.execute(stmt.on_conflict_do_nothing(index_elements=["ticker", "date"]))
    else:  # generic fallback for other databases
        existing = set(db.execute(select(PriceHistory.date).where(PriceHistory.ticker == ticker)).scalars())
        db.add_all(PriceHistory(**r) for r in rows if r["date"] not in existing)


def _record(db: Session, ticker: str, today: date, full: bool, status: str) -> None:
    values = {"ticker": ticker, "checked_at": _utcnow(), "checked_for": today, "full_history": full, "status": status}
    insert = _dialect_insert(db)
    if insert is not None:
        stmt = insert(PriceFetch).values(values)
        update = {k: stmt.excluded[k] for k in ("checked_at", "checked_for", "status")}
        if full:
            update["full_history"] = stmt.excluded.full_history
        db.execute(stmt.on_conflict_do_update(index_elements=["ticker"], set_=update))
        return
    log = db.get(PriceFetch, ticker) or PriceFetch(ticker=ticker, full_history=False)
    log.checked_at, log.checked_for, log.status = values["checked_at"], today, status
    log.full_history = log.full_history or full
    db.add(log)


def sync_prices(db: Session, tickers: list[str]) -> dict[str, str]:
    """Bring the cache up to date for `tickers`. Returns {ticker: error message}
    for tickers whose fetch failed (their cached data, if any, is left as is)."""
    today = date.today()
    plans = [_plan(db, t, today) for t in dict.fromkeys(tickers)]
    db.commit()  # release the connection while we wait on the network
    todo = [p for p in plans if p.start is not None]
    if not todo:
        return {}

    end = today + timedelta(days=1)

    def run(plan: _Plan):
        try:
            return plan, _fetch(plan.ticker, plan.start, end), None
        except PriceProviderError as e:
            return plan, None, str(e)

    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_FETCHES, len(todo))) as pool:
        results = list(pool.map(run, todo))

    # Re-based history found on an incremental fetch: pull everything again.
    retry = [p for p, s, err in results if err is None and not p.full and _rebased(p.overlap, s)]
    if retry:
        full_plans = [_Plan(p.ticker, HISTORY_START, True) for p in retry]
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_FETCHES, len(full_plans))) as pool:
            redone = {p.ticker: r for p, *r in pool.map(run, full_plans)}
        results = [
            (_Plan(p.ticker, HISTORY_START, True), *redone[p.ticker]) if p.ticker in redone else (p, s, err)
            for p, s, err in results
        ]

    errors: dict[str, str] = {}
    for plan, series, err in results:
        if err is not None:
            errors[plan.ticker] = err
            continue
        if plan.full:
            db.execute(delete(PriceHistory).where(PriceHistory.ticker == plan.ticker))
        _insert_rows(db, plan.ticker, series)
        _record(db, plan.ticker, today, plan.full, "ok" if len(series) else "empty")
    db.commit()
    return errors


def ensure_price_history(db: Session, ticker: str) -> None:
    """Single-ticker form kept for compatibility; raises on provider failure."""
    errors = sync_prices(db, [ticker])
    if errors:
        raise PriceProviderError(errors[ticker])


def get_price_series(db: Session, ticker: str) -> pd.Series:
    rows = db.execute(
        select(PriceHistory.date, PriceHistory.adj_close)
        .where(PriceHistory.ticker == ticker)
        .order_by(PriceHistory.date)
    ).all()
    if not rows:
        return pd.Series(dtype=float, name=ticker)
    dates, prices = zip(*rows)
    s = _clean(pd.Series(list(prices), index=pd.to_datetime(list(dates))))
    s.name = ticker
    return s


def get_price_matrix(db: Session, tickers: list[str]) -> pd.DataFrame:
    """One column per ticker on the union of their dates. No forward fill and no
    row dropping: each column is NaN outside the days that ticker actually traded,
    so one asset's short history never truncates another's."""
    series = {t: get_price_series(db, t) for t in dict.fromkeys(tickers)}
    if not any(len(s) for s in series.values()):
        return pd.DataFrame(columns=list(series))
    return pd.DataFrame(series).sort_index()


__all__ = [
    "PriceProviderError",
    "ensure_price_history",
    "get_price_matrix",
    "get_price_series",
    "last_complete_session",
    "sync_prices",
]
