import numpy as np
import pandas as pd
import pytest

from app.analytics.risk import (
    TRADING_DAYS,
    covariance_matrix,
    historical_cvar,
    historical_var,
    max_drawdown,
    sharpe_ratio,
    volatility,
)


@pytest.fixture
def two_asset_returns():
    # Deterministic, hand-computable daily returns for two assets.
    a = np.array([0.01, -0.02, 0.015, 0.005, -0.01, 0.02, -0.015, 0.01])
    b = np.array([0.005, 0.01, -0.01, 0.02, 0.0, -0.005, 0.01, -0.02])
    return pd.DataFrame({"A": a, "B": b})


def test_covariance_matrix_matches_numpy(two_asset_returns):
    cov = covariance_matrix(two_asset_returns)
    expected = np.cov(two_asset_returns["A"], two_asset_returns["B"], ddof=1) * TRADING_DAYS
    assert cov.shape == (2, 2)
    np.testing.assert_allclose(cov, expected, rtol=1e-8)


def test_volatility_matches_quadratic_form(two_asset_returns):
    weights = {"A": 0.5, "B": 0.5}
    vol = volatility(two_asset_returns, weights)

    cov = covariance_matrix(two_asset_returns)
    w = np.array([0.5, 0.5])
    expected = np.sqrt(w @ cov @ w)
    assert vol == pytest.approx(expected, rel=1e-8)


def test_volatility_zero_for_constant_returns():
    flat = pd.DataFrame({"A": [0.001] * 10, "B": [0.001] * 10})
    vol = volatility(flat, {"A": 0.5, "B": 0.5})
    assert vol == pytest.approx(0.0, abs=1e-10)


def test_sharpe_ratio_sign_matches_mean_return():
    positive = pd.Series([0.01, 0.02, -0.005, 0.015, 0.01])
    negative = pd.Series([-0.01, -0.02, 0.005, -0.015, -0.01])
    assert sharpe_ratio(positive) > 0
    assert sharpe_ratio(negative) < 0


def test_max_drawdown_known_sequence():
    # Cumulative path: 1.0 -> 1.10 -> 0.99 -> 1.0395
    # Peak is 1.10; trough relative to peak is 0.99/1.10 - 1 = -0.10 exactly.
    rets = pd.Series([0.10, -0.10, 0.05])
    dd = max_drawdown(rets)
    assert dd == pytest.approx(-0.10, rel=1e-6)


def test_historical_var_and_cvar_ordering():
    # 90 calm days at +0.01, 10 increasingly bad days in the tail (-0.02 down to -0.11).
    tail = [-0.02 * i for i in range(1, 11)]
    rets = pd.Series([0.01] * 90 + tail)

    threshold = np.percentile(rets, 5)  # reference computation, independent of implementation
    expected_var = -threshold
    expected_cvar = -rets[rets <= threshold].mean()

    var_95 = historical_var(rets, 0.95)
    cvar_95 = historical_cvar(rets, 0.95)

    assert var_95 == pytest.approx(expected_var, rel=1e-8)
    assert cvar_95 == pytest.approx(expected_cvar, rel=1e-8)
    # CVaR averages the tail beyond the cutoff, which is strictly worse than the
    # cutoff itself when the tail isn't flat.
    assert cvar_95 > var_95


def test_historical_var_increases_with_confidence():
    rng = np.random.default_rng(42)
    rets = pd.Series(rng.normal(loc=0.0005, scale=0.02, size=500))
    var_95 = historical_var(rets, 0.95)
    var_99 = historical_var(rets, 0.99)
    assert var_99 >= var_95
