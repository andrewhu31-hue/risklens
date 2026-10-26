"""Shared fixtures for the RiskLens stress-test suite.

Everything here is deterministic and offline:
  * yfinance is replaced by `FakeMarket`, an in-memory provider whose price
    series are defined explicitly by each test.
  * The database is a throwaway SQLite file, recreated for every test.
  * `date.today()` inside the price service can be frozen.

No production code is modified; all substitution happens via monkeypatch.
"""
import os
import tempfile
import time
from datetime import date, datetime, timedelta

# Must be set before `app` is imported (the engine is created at import time).
_TMP_DIR = tempfile.mkdtemp(prefix="risklens-tests-")
# TEST_DATABASE_URL (e.g. a throwaway local Postgres) runs the same suite on another DB.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_TMP_DIR}/test.db"
os.environ.setdefault("JWT_SECRET", "stress-suite-secret-that-is-long-enough-0123456789")
os.environ.pop("ANTHROPIC_API_KEY", None)

import numpy as np
import pandas as pd
import pytest
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

from app.limiter import limiter
from app.models import database as dbmod

# Trading calendar used by fixtures: weekdays minus US federal holidays.
# (Close enough to NYSE for these tests: it closes on 2008-09-01 Labor Day and
# 2020-02-17 Presidents' Day, which the stress windows touch.)
TRADING_DAY = CustomBusinessDay(calendar=USFederalHolidayCalendar())
FIXTURE_TODAY = date(2026, 10, 26)  # a Monday, matches the real run date


def trading_days(start, end) -> pd.DatetimeIndex:
    return pd.date_range(start, end, freq=TRADING_DAY)


def calendar_days(start, end) -> pd.DatetimeIndex:
    return pd.date_range(start, end, freq="D")


def geometric_path(index: pd.DatetimeIndex, start_price: float = 100.0, mu=0.0003, sigma=0.012, seed=0) -> pd.Series:
    rng = np.random.default_rng(seed)
    rets = rng.normal(mu, sigma, len(index))
    prices = start_price * np.exp(np.cumsum(rets))
    return pd.Series(prices, index=index)


class FakeMarket:
    """In-memory stand-in for yfinance.

    `series[ticker]` is a pd.Series of closes indexed by naive dates.
    Behaviour knobs: `delay` (seconds per call), `fail` (ticker -> exception),
    `override` (ticker -> callable(start, end) -> DataFrame) for malformed responses.
    """

    def __init__(self):
        self.series: dict[str, pd.Series] = {}
        self.calls: list[tuple[str, str, str]] = []
        self.delay = 0.0
        self.fail: dict[str, Exception] = {}
        self.override: dict = {}

    # yfinance-compatible surface -------------------------------------------
    def Ticker(self, ticker):  # noqa: N802 (mirrors yfinance API)
        market = self

        class _T:
            def history(self, start, end, auto_adjust=True, **_):
                return market._history(ticker, start, end)

        return _T()

    def _history(self, ticker, start, end):
        self.calls.append((ticker, start, end))
        if self.delay:
            time.sleep(self.delay)
        if ticker in self.fail:
            raise self.fail[ticker]
        if ticker in self.override:
            return self.override[ticker](start, end)
        s = self.series.get(ticker)
        if s is None:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        s = s[(s.index >= pd.Timestamp(start)) & (s.index < pd.Timestamp(end))]
        # yfinance returns a tz-aware index named "Date".
        idx = s.index.tz_localize("America/New_York")
        idx.name = "Date"
        return pd.DataFrame({"Open": s.values, "High": s.values, "Low": s.values, "Close": s.values, "Volume": 1}, index=idx)

    def calls_for(self, ticker):
        return [c for c in self.calls if c[0] == ticker]


@pytest.fixture
def market(monkeypatch):
    m = FakeMarket()
    import app.services.prices as prices_mod

    monkeypatch.setattr(prices_mod, "yf", m)
    return m


@pytest.fixture
def frozen_today(monkeypatch):
    """Freeze date.today() inside the price service. Returns a setter."""
    import app.services.prices as prices_mod

    state = {"today": FIXTURE_TODAY}

    class _FrozenDate(date):
        @classmethod
        def today(cls):
            return state["today"]

    monkeypatch.setattr(prices_mod, "date", _FrozenDate)

    def set_today(d: date):
        state["today"] = d

    return set_today


@pytest.fixture(autouse=True)
def fresh_db():
    dbmod.Base.metadata.drop_all(bind=dbmod.engine)
    dbmod.Base.metadata.create_all(bind=dbmod.engine)
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def db():
    s = dbmod.SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    # raise_server_exceptions=False so unhandled errors surface as real HTTP 500s,
    # exactly as a curl user would see them.
    return TestClient(app, raise_server_exceptions=False)


# --- API helpers -------------------------------------------------------------

_counter = {"n": 0}


def register(client, email=None, password="correct-horse-battery"):
    _counter["n"] += 1
    email = email or f"user{_counter['n']}_{time.time_ns()}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_portfolio(client, headers, holdings, benchmark="SPY", name="p"):
    r = client.post("/portfolios", json={"name": name, "benchmark": benchmark}, headers=headers)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    if holdings:
        r = client.post(f"/portfolios/{pid}/holdings", json=holdings, headers=headers)
        assert r.status_code == 200, r.text
    return pid


@pytest.fixture
def standard_market(market):
    """Long-history tickers OLD1, OLD2, SPY from 2006 to the fixture 'today'."""
    idx = trading_days("2006-01-03", FIXTURE_TODAY)
    market.series["OLD1"] = geometric_path(idx, 100, seed=1)
    market.series["OLD2"] = geometric_path(idx, 50, seed=2)
    market.series["SPY"] = geometric_path(idx, 120, seed=3)
    return market
