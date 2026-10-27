"""The /performance endpoint: growth of 1 versus the benchmark, and drawdown."""
import pandas as pd
import pytest

from app.analytics.performance import MAX_POINTS, performance_report

from .conftest import FIXTURE_TODAY, geometric_path, make_portfolio, register, trading_days


@pytest.fixture
def mkt(standard_market, frozen_today):
    return standard_market


def test_known_path_growth_and_drawdown_dates():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"])
    rets = pd.Series([0.10, -0.10, 0.05, 0.10], index=idx[1:])
    bench = pd.Series([100.0, 101.0, 99.0, 102.0, 110.0], index=idx)
    out = performance_report(rets, idx[0], bench)

    wealth = [p["portfolio"] for p in out["series"]]
    assert wealth == pytest.approx([1.0, 1.1, 0.99, 1.0395, 1.14345])
    assert [p["benchmark"] for p in out["series"]] == pytest.approx([1.0, 1.01, 0.99, 1.02, 1.10])
    assert out["total_return"] == pytest.approx(0.14345)
    assert out["benchmark_total_return"] == pytest.approx(0.10)
    assert out["max_drawdown"] == {
        "depth": pytest.approx(-0.10),
        "peak_date": "2024-01-03",
        "trough_date": "2024-01-04",
        "recovered_date": "2024-01-08",
    }


def test_unrecovered_drawdown_and_missing_benchmark():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    out = performance_report(pd.Series([-0.2, 0.1], index=idx[1:]), idx[0], None)
    assert out["benchmark_total_return"] is None
    assert all(p["benchmark"] is None for p in out["series"])
    assert out["max_drawdown"]["peak_date"] == "2024-01-02"
    assert out["max_drawdown"]["recovered_date"] is None


def test_benchmark_on_a_different_calendar_is_forward_filled():
    # Benchmark has no price on 2024-01-03; it should carry 2024-01-02's price.
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    bench = pd.Series([100.0, 120.0], index=pd.to_datetime(["2024-01-02", "2024-01-04"]))
    out = performance_report(pd.Series([0.0, 0.0], index=idx[1:]), idx[0], bench)
    assert [p["benchmark"] for p in out["series"]] == pytest.approx([1.0, 1.0, 1.2])


def test_long_history_is_thinned_but_keeps_ends_and_trough():
    idx = trading_days("2006-01-03", "2026-10-26")
    rets = geometric_path(idx, 100, seed=9).pct_change().iloc[1:]
    out = performance_report(rets, idx[0], None)
    assert len(out["series"]) <= MAX_POINTS + 2
    assert out["series"][0]["date"] == "2006-01-03"
    assert out["series"][-1]["date"] == idx[-1].date().isoformat()
    deepest = min(p["drawdown"] for p in out["series"])
    assert deepest == pytest.approx(out["max_drawdown"]["depth"])


def test_endpoint_matches_risk_max_drawdown(client, mkt):
    h = register(client)
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 10}, {"ticker": "OLD2", "shares": 20}])
    perf = client.get(f"/portfolios/{pid}/performance", headers=h)
    assert perf.status_code == 200, perf.text
    body = perf.json()
    risk = client.get(f"/portfolios/{pid}/risk", headers=h).json()

    assert body["benchmark"] == "SPY"
    assert body["series"][0]["portfolio"] == 1.0 and body["series"][0]["benchmark"] == 1.0
    assert body["max_drawdown"]["depth"] == pytest.approx(risk["max_drawdown"], abs=1e-6)
    assert body["window"] == risk["window"]
    assert body["benchmark_total_return"] is not None


def test_endpoint_requires_owner(client, mkt):
    owner, other = register(client), register(client)
    pid = make_portfolio(client, owner, [{"ticker": "OLD1", "shares": 1}])
    assert client.get(f"/portfolios/{pid}/performance", headers=other).status_code == 404
    assert client.get(f"/portfolios/{pid}/performance").status_code == 401


def test_endpoint_with_young_holding_uses_common_window(client, mkt):
    mkt.series["IPO"] = geometric_path(trading_days("2024-01-02", FIXTURE_TODAY), 10, seed=4)
    h = register(client)
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 1}, {"ticker": "IPO", "shares": 1}])
    body = client.get(f"/portfolios/{pid}/performance", headers=h).json()
    assert body["series"][0]["date"] == "2024-01-02"
    assert body["window"]["limited_by"] == "IPO"
