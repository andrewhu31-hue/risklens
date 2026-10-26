"""Section 3 — adversarial portfolio inputs, exercised through the HTTP API
(the same path a browser or curl takes) with deterministic fake market data.

AAA and BBB both close at exactly 100.00 on the last day so expected weights can
be computed by hand from share counts.
"""
import math

import numpy as np
import pandas as pd
import pytest

from app.analytics import factors, optimizer, risk

from .conftest import FIXTURE_TODAY, geometric_path, make_portfolio, register, trading_days

ANALYTICS = ["risk", "factors", "correlation", "optimize", "stress"]


@pytest.fixture
def mkt(standard_market, frozen_today):
    idx = trading_days("2006-01-03", FIXTURE_TODAY)
    for t, seed in [("AAA", 11), ("BBB", 12)]:
        s = geometric_path(idx, 100, seed=seed)
        s.iloc[-1] = 100.0
        standard_market.series[t] = s
    return standard_market


@pytest.fixture
def h(client):
    return register(client)


def finite_json(obj):
    if isinstance(obj, dict):
        return all(finite_json(v) for v in obj.values())
    if isinstance(obj, list):
        return all(finite_json(v) for v in obj)
    if isinstance(obj, float):
        return math.isfinite(obj)
    return True


# --- portfolio shape ---------------------------------------------------------

@pytest.mark.parametrize("endpoint", ANALYTICS)
def test_empty_portfolio_returns_clear_400(client, mkt, h, endpoint):
    pid = make_portfolio(client, h, [])
    r = client.get(f"/portfolios/{pid}/{endpoint}", headers=h)
    assert r.status_code == 400 and "no holdings" in r.json()["detail"]


def test_empty_holdings_list_rejected(client, mkt, h):
    pid = make_portfolio(client, h, [])
    assert client.post(f"/portfolios/{pid}/holdings", json=[], headers=h).status_code == 400


def test_single_holding(client, mkt, h):
    pid = make_portfolio(client, h, [{"ticker": "AAA", "shares": 5}])
    for ep in ["risk", "factors", "correlation", "stress"]:
        r = client.get(f"/portfolios/{pid}/{ep}", headers=h)
        assert r.status_code == 200 and finite_json(r.json()), (ep, r.status_code, r.text[:200])
    assert client.get(f"/portfolios/{pid}/correlation", headers=h).json()["matrix"] == [[1.0]]
    assert client.get(f"/portfolios/{pid}/optimize", headers=h).status_code == 400
    fac = client.get(f"/portfolios/{pid}/factors", headers=h).json()
    assert fac["risk_contributions"][0]["risk_contribution_pct"] == pytest.approx(1.0)


@pytest.mark.parametrize("shares,ok", [(0, False), (-5, False), (-0.0001, False), (1e-9, True), (1_000_000_000, True), (1_000_000_001, False), (1e300, False)])
def test_share_bounds(client, mkt, h, shares, ok):
    pid = make_portfolio(client, h, [])
    r = client.post(f"/portfolios/{pid}/holdings", json=[{"ticker": "AAA", "shares": shares}], headers=h)
    assert (r.status_code == 200) == ok, r.text


def test_extremely_large_and_tiny_positions_give_finite_weights(client, mkt, h):
    pid = make_portfolio(client, h, [{"ticker": "AAA", "shares": 1_000_000_000}, {"ticker": "BBB", "shares": 1e-9}])
    r = client.get(f"/portfolios/{pid}/optimize", headers=h)
    assert r.status_code == 200
    w = r.json()["current"]["weights"]
    assert w["AAA"] == pytest.approx(1.0, abs=1e-12) and w["BBB"] == pytest.approx(1e-18, rel=1e-6)


# --- duplicates ----------------------------------------------------------------

def test_duplicate_ticker_is_aggregated_or_rejected(client, mkt, h):
    """AAA 10 + AAA 30 + BBB 40, all at $100 -> AAA should be 50%.
    Production keys weights by ticker in a dict, so the second AAA lot
    silently overwrites the first: AAA = 30/70 = 42.9%."""
    pid = make_portfolio(client, h, [])
    r = client.post(
        f"/portfolios/{pid}/holdings",
        json=[{"ticker": "AAA", "shares": 10}, {"ticker": "AAA", "shares": 30}, {"ticker": "BBB", "shares": 40}],
        headers=h,
    )
    if r.status_code in (400, 409, 422):
        return  # explicit rejection is acceptable
    w = client.get(f"/portfolios/{pid}/optimize", headers=h).json()["current"]["weights"]
    assert w["AAA"] == pytest.approx(0.5, abs=1e-9), f"lot overwritten: weights={w}"


def test_duplicate_ticker_does_not_corrupt_factor_report(client, mkt, h):
    pid = make_portfolio(client, h, [{"ticker": "AAA", "shares": 10}, {"ticker": "AAA", "shares": 30}, {"ticker": "BBB", "shares": 40}])
    fac = client.get(f"/portfolios/{pid}/factors", headers=h).json()
    tickers = [c["ticker"] for c in fac["risk_contributions"]]
    total_weight = sum(c["weight"] for c in fac["risk_contributions"])
    assert len(tickers) == len(set(tickers)), f"duplicate rows in risk contributions: {tickers}"
    assert total_weight == pytest.approx(1.0, abs=1e-9), f"weights shown sum to {total_weight:.4f}"


def test_csv_duplicate_lots_aggregate(client, mkt, h):
    pid = make_portfolio(client, h, [])
    csv = "ticker,shares\nAAA,10\nAAA,30\nBBB,40\n"
    r = client.post(f"/portfolios/{pid}/holdings/csv", files={"file": ("p.csv", csv, "text/csv")}, headers=h)
    if r.status_code != 200:
        return
    w = client.get(f"/portfolios/{pid}/optimize", headers=h).json()["current"]["weights"]
    assert w["AAA"] == pytest.approx(0.5, abs=1e-9), w


def test_all_holdings_same_ticker(client, mkt, h):
    pid = make_portfolio(client, h, [{"ticker": "AAA", "shares": 10}, {"ticker": "AAA", "shares": 20}])
    fac = client.get(f"/portfolios/{pid}/factors", headers=h)
    risk_r = client.get(f"/portfolios/{pid}/risk", headers=h)
    assert risk_r.status_code == 200
    # A one-asset portfolio's factor model has one factor carrying 100% of risk.
    assert fac.status_code == 200
    body = fac.json()
    assert len(body["factors"]) == 1, f"{len(body['factors'])} factors for a single underlying asset"
    # Portfolio vol must equal AAA's own vol (risk endpoint), not 2x it.
    assert body["portfolio_volatility"] == pytest.approx(risk_r.json()["annualized_volatility"], rel=1e-9)


# --- tickers -------------------------------------------------------------------

@pytest.mark.parametrize("ticker,ok", [("aaa", True), ("BRK.B", True), ("$$$", False), ("ABCDEFGHIJK", False), ("A B", False), ("A';--", False), ("", False), ("../etc", False)])
def test_ticker_format_validation(client, mkt, h, ticker, ok):
    pid = make_portfolio(client, h, [])
    r = client.post(f"/portfolios/{pid}/holdings", json=[{"ticker": ticker, "shares": 1}], headers=h)
    assert (r.status_code == 200) == ok, r.text


def test_unknown_ticker_error_names_the_ticker(client, mkt, h):
    pid = make_portfolio(client, h, [{"ticker": "AAA", "shares": 1}, {"ticker": "ZZZZ", "shares": 1}])
    r = client.get(f"/portfolios/{pid}/risk", headers=h)
    assert r.status_code == 400
    assert "ZZZZ" in r.json()["detail"], r.json()


def test_unknown_benchmark_is_reported_as_benchmark_problem(client, mkt, h):
    pid = make_portfolio(client, h, [{"ticker": "AAA", "shares": 1}], benchmark="QQQX")
    r = client.get(f"/portfolios/{pid}/stress", headers=h)  # stress doesn't even use the benchmark
    assert r.status_code == 200 or "QQQX" in r.json().get("detail", ""), (r.status_code, r.text)


# --- bad prices ------------------------------------------------------------------

@pytest.mark.parametrize("endpoint", ANALYTICS)
def test_zero_price_in_history_does_not_500(client, mkt, h, endpoint):
    mkt.series["AAA"][pd.Timestamp("2015-03-02")] = 0.0
    pid = make_portfolio(client, h, [{"ticker": "AAA", "shares": 1}, {"ticker": "BBB", "shares": 1}])
    r = client.get(f"/portfolios/{pid}/{endpoint}", headers=h)
    assert r.status_code != 500, f"{endpoint}: HTTP 500"
    assert r.status_code >= 400 or finite_json(r.json())


def test_zero_latest_price_does_not_500(client, mkt, h):
    mkt.series["AAA"].iloc[-1] = 0.0
    pid = make_portfolio(client, h, [{"ticker": "AAA", "shares": 1}, {"ticker": "BBB", "shares": 1}])
    r = client.get(f"/portfolios/{pid}/risk", headers=h)
    assert r.status_code != 500


@pytest.mark.parametrize("endpoint", ANALYTICS)
def test_constant_price_history_does_not_500(client, mkt, h, endpoint):
    idx = mkt.series["AAA"].index
    mkt.series["FLAT"] = pd.Series(25.0, index=idx)
    pid = make_portfolio(client, h, [{"ticker": "FLAT", "shares": 1}, {"ticker": "BBB", "shares": 1}])
    r = client.get(f"/portfolios/{pid}/{endpoint}", headers=h)
    assert r.status_code != 500, f"{endpoint}: HTTP 500"


@pytest.mark.parametrize("n_days", [1, 2, 3])
@pytest.mark.parametrize("endpoint", ["risk", "factors", "optimize"])
def test_insufficient_history_does_not_500(client, mkt, h, n_days, endpoint):
    idx = trading_days("2026-01-02", FIXTURE_TODAY)[-n_days:]
    mkt.series["IPO"] = pd.Series(np.linspace(10, 11, n_days), index=idx)
    pid = make_portfolio(client, h, [{"ticker": "AAA", "shares": 1}, {"ticker": "IPO", "shares": 1}])
    r = client.get(f"/portfolios/{pid}/{endpoint}", headers=h)
    assert r.status_code != 500, f"{endpoint} with {n_days}-day IPO: HTTP 500"
    assert r.status_code >= 400 or finite_json(r.json())


# --- degenerate return distributions (pure functions) ---------------------------

def test_sortino_with_no_negative_returns_is_not_reported_as_zero():
    r = pd.Series([0.01, 0.02, 0.005, 0.03])
    v = risk.sortino_ratio(r)
    assert v is None or math.isinf(v) or v > 0, f"all-gain portfolio reported Sortino {v}"


def test_all_negative_returns_metrics():
    r = pd.Series([-0.01, -0.02, -0.005, -0.03])
    assert risk.sharpe_ratio(r) < 0
    assert risk.sortino_ratio(r) < 0
    assert risk.historical_var(r) > 0
    assert risk.max_drawdown(r) == pytest.approx(0.99 * 0.98 * 0.995 * 0.97 - 1, abs=1e-12)


def test_zero_benchmark_variance_beta_is_undefined_not_zero():
    v = risk.beta(pd.Series([0.01, -0.02, 0.03]), pd.Series([0.0, 0.0, 0.0]))
    assert v is None or math.isnan(v), f"beta vs constant benchmark reported as {v}"


def test_perfectly_correlated_assets():
    rng = np.random.default_rng(1)
    a = rng.normal(0.0005, 0.01, 500)
    df = pd.DataFrame({"A": a, "B": a})
    vals, _ = factors.eigendecompose(df)
    assert vals[1] == pytest.approx(0.0, abs=1e-15)
    rep = optimizer.optimizer_report(df, {"A": 0.5, "B": 0.5})
    for k in ("min_variance", "max_sharpe"):
        w = np.array(list(rep[k]["weights"].values()))
        assert w.sum() == pytest.approx(1, abs=1e-6) and (w >= -1e-9).all()


def test_perfectly_negatively_correlated_assets_hedge_to_zero():
    rng = np.random.default_rng(2)
    a = rng.normal(0.0, 0.01, 500)
    df = pd.DataFrame({"A": a, "B": -a})
    w = optimizer.min_variance_weights(optimizer._annualized_cov(df))
    assert w == pytest.approx([0.5, 0.5], abs=1e-4)
    assert risk.volatility(df, {"A": 0.5, "B": 0.5}) == pytest.approx(0.0, abs=1e-12)


def test_nearly_singular_covariance():
    rng = np.random.default_rng(3)
    a = rng.normal(0.0005, 0.01, 500)
    df = pd.DataFrame({"A": a, "B": a + rng.normal(0, 1e-10, 500), "C": rng.normal(0.0003, 0.01, 500)})
    cond = np.linalg.cond(df.cov().values)
    assert cond > 1e12
    rep = optimizer.optimizer_report(df, {"A": 0.3, "B": 0.3, "C": 0.4})
    for k in ("min_variance", "max_sharpe"):
        w = np.array(list(rep[k]["weights"].values()))
        assert w.sum() == pytest.approx(1, abs=1e-6) and (w >= -1e-9).all() and (w <= 1 + 1e-9).all()
    fr = factors.factor_report(df, {"A": 0.3, "B": 0.3, "C": 0.4})
    assert sum(c["risk_contribution_pct"] for c in fr["risk_contributions"]) == pytest.approx(1.0, abs=1e-9)


# --- malformed numerics -----------------------------------------------------------

@pytest.mark.parametrize("raw_shares", ['"NaN"', "NaN", '"nan"', '"Infinity"', "Infinity", '"-Infinity"', '"abc"', "null", "[]", '"1e400"'])
def test_non_finite_or_malformed_shares_rejected_with_4xx(client, mkt, h, raw_shares):
    pid = make_portfolio(client, h, [])
    body = '[{"ticker": "AAA", "shares": %s}]' % raw_shares
    r = client.post(f"/portfolios/{pid}/holdings", content=body, headers={**h, "Content-Type": "application/json"})
    assert 400 <= r.status_code < 500, f"shares={raw_shares}: HTTP {r.status_code} {r.text[:150]}"


@pytest.mark.parametrize("raw", ["nan", "NaN", "inf", "-inf", "abc", "1e400"])
def test_csv_non_finite_shares_rejected(client, mkt, h, raw):
    pid = make_portfolio(client, h, [])
    csv = f"ticker,shares\nAAA,{raw}\n"
    r = client.post(f"/portfolios/{pid}/holdings/csv", files={"file": ("p.csv", csv, "text/csv")}, headers=h)
    assert 400 <= r.status_code < 500, f"CSV shares={raw}: HTTP {r.status_code} {r.text[:150]}"


def test_csv_cost_basis_validated_like_json(client, mkt, h):
    pid = make_portfolio(client, h, [])
    json_r = client.post(f"/portfolios/{pid}/holdings", json=[{"ticker": "AAA", "shares": 1, "cost_basis": -50}], headers=h)
    csv_r = client.post(
        f"/portfolios/{pid}/holdings/csv",
        files={"file": ("p.csv", "ticker,shares,cost_basis\nAAA,1,-50\n", "text/csv")},
        headers=h,
    )
    assert json_r.status_code == 422
    assert csv_r.status_code == 400, f"CSV accepted negative cost_basis (HTTP {csv_r.status_code})"


def test_csv_error_reports_correct_row_number(client, mkt, h):
    pid = make_portfolio(client, h, [])
    csv = "ticker,shares\nAAA,1\n,\nBBB,1\n$$$,1\n"  # bad row is data row 4
    r = client.post(f"/portfolios/{pid}/holdings/csv", files={"file": ("p.csv", csv, "text/csv")}, headers=h)
    assert r.status_code == 400
    assert "row 4" in r.json()["detail"], r.json()


@pytest.mark.parametrize(
    "body",
    ['{"ticker": "AAA", "shares": 1}', '[{"shares": 1}]', '[{"ticker": 123, "shares": 1}]', "not json", '[{"ticker": "AAA", "shares": 1}', ""],
)
def test_malformed_holdings_bodies_rejected(client, mkt, h, body):
    pid = make_portfolio(client, h, [])
    r = client.post(f"/portfolios/{pid}/holdings", content=body, headers={**h, "Content-Type": "application/json"})
    assert r.status_code == 422, (body, r.status_code)


def test_json_holdings_list_is_size_limited_like_csv(client, mkt, h):
    pid = make_portfolio(client, h, [])
    big = [{"ticker": "AAA", "shares": 1}] * 5000
    r = client.post(f"/portfolios/{pid}/holdings", json=big, headers=h)
    assert r.status_code in (400, 413, 422), f"5,000 holdings accepted via JSON (CSV caps at 500): HTTP {r.status_code}"


def test_ask_question_length_is_bounded(client, mkt, h, monkeypatch):
    import app.api.ask as ask_mod

    monkeypatch.setattr(ask_mod, "answer_question", lambda ctx, q: "stub")
    pid = make_portfolio(client, h, [{"ticker": "AAA", "shares": 1}])
    r = client.post(f"/portfolios/{pid}/ask", json={"question": "x" * 200_000}, headers=h)
    assert r.status_code in (400, 413, 422), f"200 KB question forwarded to the LLM: HTTP {r.status_code}"
