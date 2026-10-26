"""Section 2 — historical crisis-replay correctness.

Unit tests drive `run_stress_tests` with hand-built price frames; pipeline tests
go through the real price cache + `load_portfolio_context` + HTTP API with the
FakeMarket provider, which is how production calls it.

Fixture price anchors (all other days are a seeded random walk):
  2008 window 2008-09-01 (Labor Day, closed) .. 2009-03-01 (Sunday)
      -> first obs 2008-09-02, last obs 2009-02-27
      OLD1 100 -> 55  (-45%)   OLD2 50 -> 40  (-20%)
  2020 window 2020-02-15 (Sat; Mon 02-17 Presidents' Day) .. 2020-03-23
      -> first obs 2020-02-18, last obs 2020-03-23
      OLD1 200 -> 130 (-35%)   OLD2 80 -> 72  (-10%)
  2022 window 2022-01-01 (Sat) .. 2022-10-01 (Sat)
      -> first obs 2022-01-03, last obs 2022-09-30
      OLD1 300 -> 240 (-20%)   OLD2 90 -> 63  (-30%)
Decoy prices sit on the trading days just outside each window so that an
off-by-one date selection produces an obviously wrong number.
"""
import numpy as np
import pandas as pd
import pytest

from app.analytics.stress import run_stress_tests
from app.services.context import load_portfolio_context

from .conftest import FIXTURE_TODAY, geometric_path, make_portfolio, register, trading_days

ANCHORS = {
    "OLD1": {"2008-09-02": 100, "2009-02-27": 55, "2020-02-18": 200, "2020-03-23": 130, "2022-01-03": 300, "2022-09-30": 240},
    "OLD2": {"2008-09-02": 50, "2009-02-27": 40, "2020-02-18": 80, "2020-03-23": 72, "2022-01-03": 90, "2022-09-30": 63},
}
DECOYS = ["2008-08-29", "2009-03-02", "2020-02-14", "2020-03-24", "2021-12-31", "2022-10-03"]
R = {  # hand returns per scenario
    "2008_gfc": {"OLD1": -0.45, "OLD2": -0.20},
    "2020_covid": {"OLD1": -0.35, "OLD2": -0.10},
    "2022_selloff": {"OLD1": -0.20, "OLD2": -0.30},
}


def anchored(ticker, idx, seed):
    s = geometric_path(idx, 100, seed=seed)
    for d, p in ANCHORS.get(ticker, {}).items():
        assert pd.Timestamp(d) in s.index, f"{d} not a fixture trading day"
        s[pd.Timestamp(d)] = p
    for d in DECOYS:
        if pd.Timestamp(d) in s.index:
            s[pd.Timestamp(d)] = 9999.0
    return s


@pytest.fixture
def frame():
    idx = trading_days("2006-01-03", "2026-10-23")
    return pd.DataFrame({"OLD1": anchored("OLD1", idx, 1), "OLD2": anchored("OLD2", idx, 2)})


def by_key(results):
    return {r["scenario"]: r for r in results}


# --- unit: run_stress_tests --------------------------------------------------

def test_fixture_calendar_matches_expected_observation_dates():
    idx = trading_days("2008-08-25", "2009-03-06")
    assert pd.Timestamp("2008-09-01") not in idx  # Labor Day
    assert pd.Timestamp("2020-02-17") not in trading_days("2020-02-10", "2020-02-20")


@pytest.mark.parametrize("scenario", ["2008_gfc", "2020_covid", "2022_selloff"])
def test_start_end_selection_and_weighted_return(frame, scenario):
    w = {"OLD1": 0.7, "OLD2": 0.3}
    res = by_key(run_stress_tests(frame, w))[scenario]
    expected = sum(w[t] * R[scenario][t] for t in w)
    assert res["applicable"] is True
    assert res["missing_tickers"] == []
    assert res["portfolio_return"] == pytest.approx(expected, abs=1e-12)


def test_asset_missing_from_window_is_flagged_and_weights_renormalized(frame):
    frame = frame.copy()
    frame["NEW"] = np.where(frame.index >= "2015-06-01", 20.0, np.nan)
    res = by_key(run_stress_tests(frame, {"OLD1": 0.5, "OLD2": 0.3, "NEW": 0.2}))["2008_gfc"]
    assert res["applicable"] is True
    assert res["missing_tickers"] == ["NEW"]
    # renormalized: OLD1 .5/.8=.625, OLD2 .3/.8=.375
    assert res["portfolio_return"] == pytest.approx(0.625 * -0.45 + 0.375 * -0.20, abs=1e-12)


def test_response_reports_full_vs_partial_coverage(frame):
    frame = frame.copy()
    frame["NEW"] = np.where(frame.index >= "2015-06-01", 20.0, np.nan)
    res = by_key(run_stress_tests(frame, {"OLD1": 0.5, "OLD2": 0.3, "NEW": 0.2}))["2008_gfc"]
    coverage_keys = {"coverage", "coverage_weight", "covered_weight", "partial", "is_partial", "coverage_status"}
    assert coverage_keys & set(res), f"no coverage indicator in response keys {sorted(res)}"


def test_window_with_no_data_is_unavailable_not_zero(frame):
    late = frame[frame.index >= "2023-01-01"]
    for r in run_stress_tests(late, {"OLD1": 0.7, "OLD2": 0.3}):
        assert r["applicable"] is False
        assert r["portfolio_return"] is None
        assert sorted(r["missing_tickers"]) == ["OLD1", "OLD2"]


def test_asset_listing_inside_window_does_not_shift_other_assets_start(frame):
    """MID lists on 2020-03-02, inside the COVID window. OLD1 must still be
    measured from 2020-02-18. Acceptable outcomes: MID excluded (-35%) or MID
    included from its own first price with OLD1 over the full window."""
    frame = frame.copy()
    frame.loc[pd.Timestamp("2020-03-02"), "OLD1"] = 160.0  # OLD1 3/2->3/23 would be -18.75%
    frame["MID"] = np.where(frame.index >= "2020-03-02", 10.0, np.nan)
    frame.loc[pd.Timestamp("2020-03-23"), "MID"] = 8.0  # MID -20% from its listing
    res = by_key(run_stress_tests(frame, {"OLD1": 0.5, "MID": 0.5}))["2020_covid"]
    acceptable = [-0.35, 0.5 * -0.35 + 0.5 * -0.20]
    assert any(res["portfolio_return"] == pytest.approx(a, abs=1e-9) for a in acceptable), res


def test_asset_delisting_inside_window_does_not_truncate_other_assets(frame):
    frame = frame.copy()
    frame["GONE"] = np.where(frame.index <= "2008-11-14", 30.0, np.nan)
    frame.loc[pd.Timestamp("2008-11-14"), "OLD1"] = 70.0  # OLD1 to 11/14 would be -30%
    res = by_key(run_stress_tests(frame, {"OLD1": 0.5, "GONE": 0.5}))["2008_gfc"]
    acceptable = [-0.45, 0.5 * -0.45 + 0.5 * 0.0]
    assert any(res["portfolio_return"] == pytest.approx(a, abs=1e-9) for a in acceptable), res


def test_disjoint_partial_histories_do_not_crash(frame):
    frame = frame.copy()
    frame["EARLY"] = np.where(frame.index <= "2008-10-15", 30.0, np.nan)
    frame["LATE"] = np.where(frame.index >= "2008-12-01", 40.0, np.nan)
    w = {"EARLY": 0.5, "LATE": 0.5}
    try:
        res = by_key(run_stress_tests(frame, w))["2008_gfc"]
    except Exception as e:  # pragma: no cover - we want to record the failure mode
        pytest.fail(f"run_stress_tests raised {type(e).__name__}: {e}")
    assert res["portfolio_return"] is None or np.isfinite(res["portfolio_return"])


def test_zero_start_price_does_not_produce_infinite_return(frame):
    frame = frame.copy()
    frame.loc[pd.Timestamp("2008-09-02"), "OLD2"] = 0.0
    res = by_key(run_stress_tests(frame, {"OLD1": 0.5, "OLD2": 0.5}))["2008_gfc"]
    assert res["portfolio_return"] is None or np.isfinite(res["portfolio_return"]), res


# --- pipeline: shared price matrix -------------------------------------------

@pytest.fixture
def crisis_market(market, frozen_today):
    idx = trading_days("2006-01-03", FIXTURE_TODAY)
    market.series["OLD1"] = anchored("OLD1", idx, 1)
    market.series["OLD2"] = anchored("OLD2", idx, 2)
    market.series["SPY"] = geometric_path(idx, 120, seed=3)
    return market


def _weights_from_last(market, shares):
    vals = {t: n * float(market.series[t].iloc[-1]) for t, n in shares.items()}
    tot = sum(vals.values())
    return {t: v / tot for t, v in vals.items()}


def test_price_matrix_dropna_is_shared_across_tickers(db, crisis_market):
    """Direct evidence: get_price_matrix() does ffill().dropna() over ALL tickers."""
    from app.services.prices import ensure_price_history, get_price_matrix

    idx = trading_days("2015-06-01", FIXTURE_TODAY)
    crisis_market.series["NEW"] = geometric_path(idx, 20, seed=9)
    for t in ["OLD1", "NEW"]:
        ensure_price_history(db, t)
    alone = get_price_matrix(db, ["OLD1"])
    together = get_price_matrix(db, ["OLD1", "NEW"])
    assert alone.index.min() == pd.Timestamp("2006-01-03")
    # Regression assertion: OLD1's own history must survive adding a newer ticker.
    assert together["OLD1"].first_valid_index() == pd.Timestamp("2006-01-03"), (
        f"OLD1 history now starts {together.index.min().date()} — erased by NEW's IPO"
    )


def test_api_stress_baseline_old_assets_only(client, crisis_market):
    h = register(client)
    shares = {"OLD1": 10, "OLD2": 30}
    pid = make_portfolio(client, h, [{"ticker": t, "shares": n} for t, n in shares.items()])
    r = client.get(f"/portfolios/{pid}/stress", headers=h)
    assert r.status_code == 200, r.text
    w = _weights_from_last(crisis_market, shares)
    for s in r.json()["scenarios"]:
        exp = sum(w[t] * R[s["scenario"]][t] for t in w)
        assert s["applicable"] and s["portfolio_return"] == pytest.approx(exp, abs=1e-9)


def test_api_newer_asset_does_not_erase_2008_history_of_older_assets(client, crisis_market):
    """REGRESSION: adding one 2015 IPO should flag it as missing for 2008 —
    not wipe out 2008 for OLD1/OLD2 as well."""
    crisis_market.series["NEW"] = geometric_path(trading_days("2015-06-01", FIXTURE_TODAY), 20, seed=9)
    h = register(client)
    shares = {"OLD1": 10, "OLD2": 30, "NEW": 5}
    pid = make_portfolio(client, h, [{"ticker": t, "shares": n} for t, n in shares.items()])
    res = by_key(client.get(f"/portfolios/{pid}/stress", headers=h).json()["scenarios"])["2008_gfc"]
    assert res["applicable"] is True, f"2008 replay lost for every holding: {res}"
    assert res["missing_tickers"] == ["NEW"]
    w = _weights_from_last(crisis_market, shares)
    tot = w["OLD1"] + w["OLD2"]
    exp = (w["OLD1"] * -0.45 + w["OLD2"] * -0.20) / tot
    assert res["portfolio_return"] == pytest.approx(exp, abs=1e-9)


def test_api_newer_benchmark_does_not_erase_holdings_history(client, crisis_market):
    crisis_market.series["NEWB"] = geometric_path(trading_days("2021-01-04", FIXTURE_TODAY), 50, seed=8)
    h = register(client)
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 10}], benchmark="NEWB")
    res = by_key(client.get(f"/portfolios/{pid}/stress", headers=h).json()["scenarios"])
    assert res["2008_gfc"]["applicable"] is True, "benchmark choice erased the holdings' 2008 history"
    assert res["2008_gfc"]["portfolio_return"] == pytest.approx(-0.45, abs=1e-9)


def test_api_ipo_inside_covid_window_is_not_silent_full_coverage(client, crisis_market):
    """MID lists 2020-03-02. Production silently starts *every* asset's COVID
    replay on 3/2 and reports missing_tickers=[] (i.e. full coverage)."""
    idx = trading_days("2020-03-02", FIXTURE_TODAY)
    crisis_market.series["MID"] = geometric_path(idx, 10, seed=7)
    crisis_market.series["OLD1"][pd.Timestamp("2020-03-02")] = 160.0
    h = register(client)
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 10}, {"ticker": "MID", "shares": 10}])
    res = by_key(client.get(f"/portfolios/{pid}/stress", headers=h).json()["scenarios"])["2020_covid"]
    silently_truncated = res["applicable"] and res["missing_tickers"] == [] and not (
        {"coverage", "partial", "is_partial", "coverage_status"} & set(res)
    )
    assert not silently_truncated, f"partial-window result presented as full coverage: {res}"


def test_api_delisted_asset_not_replayed_as_flat_through_later_crisis(client, crisis_market):
    """DEAD stops trading 2021-06-30. ffill() carries its last price forward to
    today, so it is 'available' for 2022 with a fabricated 0% return, and its
    weight is computed from a 5-year-old price."""
    crisis_market.series["DEAD"] = geometric_path(trading_days("2006-01-03", "2021-06-30"), 40, seed=6)
    h = register(client)
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 10}, {"ticker": "DEAD", "shares": 10}])
    res = by_key(client.get(f"/portfolios/{pid}/stress", headers=h).json()["scenarios"])["2022_selloff"]
    assert "DEAD" in res["missing_tickers"], f"delisted asset replayed as flat: {res}"


def test_context_weights_use_fresh_prices_not_forward_filled(db, crisis_market):
    crisis_market.series["DEAD"] = geometric_path(trading_days("2006-01-03", "2021-06-30"), 40, seed=6)
    from app.models.database import Holding, Portfolio, User

    u = User(email="w@x.com", hashed_password="x")
    db.add(u)
    db.flush()
    p = Portfolio(owner_id=u.id, name="p", benchmark="SPY")
    db.add(p)
    db.flush()
    db.add_all([Holding(portfolio_id=p.id, ticker="OLD1", shares=1), Holding(portfolio_id=p.id, ticker="DEAD", shares=1)])
    db.commit()
    ctx = load_portfolio_context(db, p.id, u.id)
    # The context's "latest" price for DEAD is a stale 2021 close presented as today's.
    assert ctx.prices.index[-1] > pd.Timestamp("2026-01-01")
    stale = ctx.prices["DEAD"].iloc[-1] == crisis_market.series["DEAD"].iloc[-1]
    assert not stale, "weight for DEAD computed from a forward-filled 2021 price with no warning"
