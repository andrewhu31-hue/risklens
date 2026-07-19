import numpy as np
import pandas as pd
import pytest

from app.analytics.optimizer import (
    _annualized_cov,
    _annualized_mean,
    max_sharpe_weights,
    min_variance_weights,
    optimizer_report,
)


@pytest.fixture
def imperfectly_correlated_returns():
    rng = np.random.default_rng(3)
    n = 300
    market = rng.normal(0.0004, 0.01, n)
    a = 1.0 * market + rng.normal(0, 0.006, n)
    b = 0.6 * market + rng.normal(0, 0.004, n)
    c = -0.4 * market + rng.normal(0.0002, 0.005, n)  # weak/negative correlation -> real diversification benefit
    return pd.DataFrame({"A": a, "B": b, "C": c})


def test_min_variance_weights_sum_to_one_and_nonnegative(imperfectly_correlated_returns):
    cov = _annualized_cov(imperfectly_correlated_returns)
    w = min_variance_weights(cov)
    assert w.sum() == pytest.approx(1.0, rel=1e-4)
    assert (w >= -1e-6).all()


def test_min_variance_beats_every_single_asset_vol(imperfectly_correlated_returns):
    cov = _annualized_cov(imperfectly_correlated_returns)
    w = min_variance_weights(cov)
    min_var_vol = np.sqrt(w @ cov @ w)

    individual_vols = np.sqrt(np.diag(cov))
    # With imperfect correlation, diversification means the min-variance portfolio's
    # volatility is strictly less than even the least volatile single asset.
    assert min_var_vol < individual_vols.min()


def test_max_sharpe_weights_sum_to_one_and_nonnegative(imperfectly_correlated_returns):
    cov = _annualized_cov(imperfectly_correlated_returns)
    mean_returns = _annualized_mean(imperfectly_correlated_returns)
    w = max_sharpe_weights(mean_returns, cov)
    assert w.sum() == pytest.approx(1.0, rel=1e-4)
    assert (w >= -1e-6).all()


def test_optimizer_report_min_variance_has_lowest_volatility(imperfectly_correlated_returns):
    weights = {"A": 0.5, "B": 0.3, "C": 0.2}
    report = optimizer_report(imperfectly_correlated_returns, weights)

    assert report["min_variance"]["volatility"] <= report["current"]["volatility"] + 1e-9
    assert report["min_variance"]["volatility"] <= report["max_sharpe"]["volatility"] + 1e-9


def test_efficient_frontier_is_monotonic_by_construction(imperfectly_correlated_returns):
    weights = {"A": 0.5, "B": 0.3, "C": 0.2}
    report = optimizer_report(imperfectly_correlated_returns, weights)
    frontier = report["efficient_frontier"]

    assert len(frontier) > 0
    returns_seen = [p["return"] for p in frontier]
    assert returns_seen == sorted(returns_seen)
    assert all(p["volatility"] >= 0 for p in frontier)
