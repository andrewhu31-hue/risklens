"""Section 4 — price alignment and the PriceHistory cache.

Note: the repository has no Redis. The only cache is the `price_history`
SQL table populated by `ensure_price_history()`; these tests target that.
"""
import threading
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.analytics.returns import aligned_returns
from app.models.database import PriceHistory, SessionLocal
from app.services.prices import ensure_price_history, get_price_matrix, get_price_series

from .conftest import FIXTURE_TODAY, calendar_days, geometric_path, make_portfolio, register, trading_days


# --- cache hit / miss ------------------------------------------------------------

def test_cache_miss_fetches_full_history_from_2006(db, standard_market, frozen_today):
    ensure_price_history(db, "OLD1")
    (_, start, _), = standard_market.calls_for("OLD1")
    assert start == "2006-01-01"
    assert db.query(PriceHistory).filter_by(ticker="OLD1").count() == len(standard_market.series["OLD1"])


def test_cache_hit_makes_no_provider_call(db, standard_market, frozen_today):
    ensure_price_history(db, "OLD1")
    ensure_price_history(db, "OLD1")
    assert len(standard_market.calls_for("OLD1")) == 1


def test_incremental_fetch_starts_day_after_last_cached(db, standard_market, frozen_today):
    frozen_today(date(2026, 10, 1))
    standard_market.series["OLD1"] = standard_market.series["OLD1"][:"2026-10-01"]
    ensure_price_history(db, "OLD1")
    idx = trading_days("2006-01-03", FIXTURE_TODAY)
    standard_market.series["OLD1"] = geometric_path(idx, 100, seed=1)
    frozen_today(FIXTURE_TODAY)
    ensure_price_history(db, "OLD1")
    # Tail fetch only (with a short overlap used to detect re-adjusted history),
    # not a re-download of 20 years.
    start = standard_market.calls_for("OLD1")[-1][1]
    assert "2026-09-15" <= start <= "2026-10-02", start
    assert get_price_series(db, "OLD1").index.is_unique


def test_monday_before_close_does_not_refetch_every_request(db, standard_market, frozen_today):
    """Data through Friday 10/23; 'today' is Monday 10/26 and today's bar isn't
    out yet. Each request re-hits the provider (max_date < today-1)."""
    standard_market.series["OLD1"] = standard_market.series["OLD1"][:"2026-10-23"]
    for _ in range(5):
        ensure_price_history(db, "OLD1")
    assert len(standard_market.calls_for("OLD1")) <= 2, f"{len(standard_market.calls_for('OLD1'))} provider calls for 5 requests"


def test_unknown_ticker_is_negatively_cached(db, standard_market, frozen_today):
    for _ in range(5):
        ensure_price_history(db, "NOPE")
    assert len(standard_market.calls_for("NOPE")) <= 1, f"{len(standard_market.calls_for('NOPE'))} provider calls for a ticker with no data"


def test_partial_cache_is_backfilled_to_history_start(db, standard_market, frozen_today):
    """If the first fetch only got recent data (provider hiccup, or the ticker was
    first cached by an older build), earlier history is never requested again."""
    s = standard_market.series["OLD1"]
    db.add_all([PriceHistory(ticker="OLD1", date=d.date(), adj_close=float(p)) for d, p in s["2019-01-02":"2026-10-20"].items()])
    db.commit()
    ensure_price_history(db, "OLD1")
    assert get_price_series(db, "OLD1").index.min() <= pd.Timestamp("2006-01-31"), "2006-2018 never backfilled"


def test_cache_not_mixed_across_split_readjustment(db, standard_market, frozen_today):
    """yfinance auto_adjust=True re-bases ALL history after a split. The cache
    keeps old-basis rows and appends new-basis rows, fabricating a crash.
    Scenario: cached through 2026-10-01; 2:1 split on 2026-10-15."""
    idx = trading_days("2006-01-03", FIXTURE_TODAY)
    raw = geometric_path(idx, 100, seed=1, sigma=0.01)
    frozen_today(date(2026, 10, 1))
    standard_market.series["SPLT"] = raw[:"2026-10-01"]
    ensure_price_history(db, "SPLT")
    adjusted = raw.copy()
    adjusted[adjusted.index < "2026-10-15"] *= 0.5  # provider's re-adjusted history
    standard_market.series["SPLT"] = adjusted
    frozen_today(FIXTURE_TODAY)
    ensure_price_history(db, "SPLT")
    r = np.log(get_price_series(db, "SPLT")).diff().dropna()
    worst = float(r.min())
    assert worst > -0.2, f"fabricated one-day log return of {worst:.3f} ({np.expm1(worst):.0%}) at {r.idxmin().date()}"


@pytest.mark.skip(reason="N/A: no endpoint accepts a date range; every analysis uses all cached history from 2006. The cache is keyed only by (ticker, date).")
def test_different_requested_ranges_for_same_ticker():
    pass


# --- provider failures -----------------------------------------------------------

@pytest.fixture
def api(client):
    h = register(client)
    return client, h


def test_provider_exception_returns_controlled_error(api, standard_market, frozen_today):
    client, h = api
    standard_market.fail["OLD1"] = RuntimeError("Too Many Requests. Rate limited. Try after a while.")
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 1}])
    r = client.get(f"/portfolios/{pid}/risk", headers=h)
    assert r.status_code in (502, 503, 429), f"provider failure surfaced as HTTP {r.status_code}"


def test_provider_down_but_cache_present_serves_cached_data(api, standard_market, frozen_today):
    client, h = api
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 1}])
    assert client.get(f"/portfolios/{pid}/risk", headers=h).status_code == 200
    frozen_today(date(2026, 10, 28))  # cache now 2 days stale -> refetch attempted
    standard_market.fail["OLD1"] = ConnectionError("provider unreachable")
    r = client.get(f"/portfolios/{pid}/risk", headers=h)
    assert r.status_code == 200, f"provider outage made fully-cached portfolio unusable (HTTP {r.status_code})"


def test_malformed_provider_response_missing_close(api, standard_market, frozen_today):
    client, h = api
    standard_market.override["OLD1"] = lambda s, e: pd.DataFrame({"Price": [1.0]}, index=pd.DatetimeIndex(["2020-01-02"]))
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 1}])
    r = client.get(f"/portfolios/{pid}/risk", headers=h)
    assert r.status_code in (400, 502, 503), f"malformed provider payload -> HTTP {r.status_code}"


def test_malformed_provider_response_duplicate_dates(api, standard_market, frozen_today):
    client, h = api
    s = standard_market.series["OLD1"]
    dup = pd.concat([s, s.iloc[-3:]])

    def resp(start, end):
        d = dup[(dup.index >= pd.Timestamp(start)) & (dup.index < pd.Timestamp(end))]
        return pd.DataFrame({"Close": d.values}, index=d.index.tz_localize("America/New_York"))

    standard_market.override["OLD1"] = resp
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 1}])
    r = client.get(f"/portfolios/{pid}/risk", headers=h)
    assert r.status_code == 200, f"duplicate dates from provider -> HTTP {r.status_code}"


def test_concurrent_first_fetch_of_same_ticker(standard_market, frozen_today):
    standard_market.delay = 0.3
    errors = []

    def worker():
        s = SessionLocal()
        try:
            ensure_price_history(s, "OLD2")
        except Exception as e:
            errors.append(type(e).__name__ + ": " + str(e).splitlines()[0][:120])
        finally:
            s.close()

    ts = [threading.Thread(target=worker) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors, f"{len(errors)}/4 concurrent first-fetches failed: {errors[0]}"


# --- alignment -----------------------------------------------------------------

def test_mixed_calendars_do_not_understate_equity_volatility(db, standard_market, frozen_today):
    """A 7-day asset (crypto-like) forces weekend rows; ffill gives the equity
    0% weekend returns, and annualizing with 252 understates its vol by
    sqrt(252/365) ~ 17%."""
    standard_market.series["COIN7"] = geometric_path(calendar_days("2016-01-01", FIXTURE_TODAY), 400, seed=5, sigma=0.03)
    for t in ["OLD1", "COIN7"]:
        ensure_price_history(db, t)
    # The pipeline's own return function, as load_portfolio_context uses it.
    alone = aligned_returns(get_price_matrix(db, ["OLD1"]), ["OLD1"])["OLD1"]["2016":]
    mixed = aligned_returns(get_price_matrix(db, ["OLD1", "COIN7"]), ["OLD1", "COIN7"])["OLD1"]
    v_alone, v_mixed = alone.std() * np.sqrt(252), mixed.std() * np.sqrt(252)
    assert v_mixed == pytest.approx(v_alone, rel=0.05), f"OLD1 vol {v_alone:.3f} alone vs {v_mixed:.3f} next to a 7-day asset"


def test_missing_dates_in_one_asset_do_not_drop_rows_for_others(db, standard_market, frozen_today):
    s = standard_market.series["OLD2"]
    holes = s.index[1000:1010]
    standard_market.series["OLD2"] = s.drop(holes)
    for t in ["OLD1", "OLD2"]:
        ensure_price_history(db, t)
    m = get_price_matrix(db, ["OLD1", "OLD2"])
    assert all(d in m.index for d in holes)


def test_short_history_ipo_truncates_whole_matrix(db, standard_market, frozen_today):
    standard_market.series["IPO"] = geometric_path(trading_days("2026-06-01", FIXTURE_TODAY), 10, seed=4)
    for t in ["OLD1", "OLD2", "IPO"]:
        ensure_price_history(db, t)
    m = get_price_matrix(db, ["OLD1", "OLD2", "IPO"])
    assert m["OLD1"].first_valid_index() < pd.Timestamp("2007-01-01"), (
        f"one 5-month-old IPO cut every asset's history to {len(m)} rows starting {m.index.min().date()}"
    )
