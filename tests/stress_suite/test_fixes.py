"""Tests for behaviour added while fixing the stress-test findings."""
import pandas as pd
import pytest

from app.analytics.stress import run_stress_tests

from .conftest import FIXTURE_TODAY, geometric_path, make_portfolio, register, trading_days


@pytest.fixture
def mkt(standard_market, frozen_today):
    return standard_market


def test_list_portfolios_returns_only_mine(client, mkt):
    a, b = register(client), register(client)
    pa = make_portfolio(client, a, [{"ticker": "OLD1", "shares": 1}], name="mine")
    make_portfolio(client, b, [{"ticker": "OLD1", "shares": 1}], name="theirs")
    r = client.get("/portfolios", headers=a)
    assert r.status_code == 200
    assert [p["id"] for p in r.json()["portfolios"]] == [pa]


def test_delete_holding_removes_all_lots_and_unbreaks_portfolio(client, mkt):
    h = register(client)
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 10}, {"ticker": "OLD1", "shares": 30}, {"ticker": "OLD2", "shares": 5}])
    assert client.get(f"/portfolios/{pid}", headers=h).json()["positions"] == [
        {"ticker": "OLD1", "shares": 40.0},
        {"ticker": "OLD2", "shares": 5.0},
    ]
    r = client.delete(f"/portfolios/{pid}/holdings/OLD1", headers=h)
    assert r.status_code == 200 and r.json()["lots_removed"] == 2
    assert [p["ticker"] for p in client.get(f"/portfolios/{pid}", headers=h).json()["positions"]] == ["OLD2"]


def test_delete_requires_ownership(client, mkt):
    owner, intruder = register(client), register(client)
    pid = make_portfolio(client, owner, [{"ticker": "OLD1", "shares": 1}])
    assert client.delete(f"/portfolios/{pid}", headers=intruder).status_code == 404
    assert client.delete(f"/portfolios/{pid}/holdings/OLD1", headers=intruder).status_code == 404
    assert client.delete(f"/portfolios/{pid}").status_code == 401
    assert client.get(f"/portfolios/{pid}", headers=owner).status_code == 200
    assert client.delete(f"/portfolios/{pid}", headers=owner).status_code == 200
    assert client.get(f"/portfolios/{pid}", headers=owner).status_code == 404


def test_stress_reports_coverage_weight_and_asset_returns():
    idx = trading_days("2008-08-25", "2009-03-06")
    prices = pd.DataFrame({"A": 100.0, "B": 50.0}, index=idx)
    prices.loc[pd.Timestamp("2009-02-27"), "A"] = 60.0
    prices["NEW"] = float("nan")
    res = next(r for r in run_stress_tests(prices, {"A": 0.6, "B": 0.2, "NEW": 0.2}) if r["scenario"] == "2008_gfc")
    assert res["coverage"] == "partial"
    assert res["coverage_weight"] == pytest.approx(0.8)
    assert res["asset_returns"] == {"A": pytest.approx(-0.4), "B": pytest.approx(0.0)}
    assert res["portfolio_return"] == pytest.approx(0.75 * -0.4)


def test_risk_response_discloses_window_limited_by_young_holding(client, mkt):
    mkt.series["IPO"] = geometric_path(trading_days("2024-01-02", FIXTURE_TODAY), 10, seed=4)
    h = register(client)
    pid = make_portfolio(client, h, [{"ticker": "OLD1", "shares": 1}, {"ticker": "IPO", "shares": 1}])
    body = client.get(f"/portfolios/{pid}/risk", headers=h).json()
    assert body["window"]["limited_by"] == "IPO"
    assert body["window"]["start"] >= "2024-01-02"
    assert any("IPO" in w for w in body["warnings"])
    assert body["beta"] is not None


def test_generated_jwt_secret_is_persisted(monkeypatch, client):
    import app.services.auth as auth

    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setattr(auth, "_secret_cache", None)
    h = register(client)
    first = auth._get_secret()
    assert len(first) == 64
    monkeypatch.setattr(auth, "_secret_cache", None)  # simulate a new server instance
    assert auth._get_secret() == first
    assert client.post("/portfolios", json={"name": "x"}, headers=h).status_code == 200
