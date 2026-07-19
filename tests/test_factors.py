import numpy as np
import pandas as pd
import pytest

from app.analytics.factors import eigendecompose, factor_report


@pytest.fixture
def three_asset_returns():
    rng = np.random.default_rng(7)
    n = 200
    market = rng.normal(0, 0.01, n)
    a = 1.2 * market + rng.normal(0, 0.003, n)
    b = 0.8 * market + rng.normal(0, 0.004, n)
    c = -0.3 * market + rng.normal(0, 0.006, n)  # partial hedge against the market factor
    return pd.DataFrame({"A": a, "B": b, "C": c})


def test_eigenvalues_are_descending(three_asset_returns):
    eigenvalues, _ = eigendecompose(three_asset_returns)
    assert list(eigenvalues) == sorted(eigenvalues, reverse=True)


def test_eigenvalues_sum_to_total_variance(three_asset_returns):
    eigenvalues, _ = eigendecompose(three_asset_returns)
    cov = three_asset_returns.cov().values
    # Trace of a covariance matrix equals the sum of its eigenvalues.
    assert float(np.sum(eigenvalues)) == pytest.approx(float(np.trace(cov)), rel=1e-8)


def test_eigenvectors_are_orthonormal(three_asset_returns):
    _, eigenvectors = eigendecompose(three_asset_returns)
    identity = eigenvectors.T @ eigenvectors
    np.testing.assert_allclose(identity, np.eye(eigenvectors.shape[1]), atol=1e-8)


def test_dominant_factor_explains_most_variance_when_market_driven(three_asset_returns):
    # A and B are both strongly market-driven, C is only weakly linked -> the first
    # eigenvalue (dominant common factor) should explain a large share of variance.
    eigenvalues, _ = eigendecompose(three_asset_returns)
    total = np.sum(eigenvalues)
    assert eigenvalues[0] / total > 0.5


def test_risk_contributions_sum_to_one(three_asset_returns):
    weights = {"A": 0.5, "B": 0.3, "C": 0.2}
    report = factor_report(three_asset_returns, weights)
    total_pct = sum(c["risk_contribution_pct"] for c in report["risk_contributions"])
    assert total_pct == pytest.approx(1.0, rel=1e-6)


def test_factor_variance_explained_sums_to_one(three_asset_returns):
    weights = {"A": 0.5, "B": 0.3, "C": 0.2}
    report = factor_report(three_asset_returns, weights)
    total_explained = sum(f["variance_explained"] for f in report["factors"])
    assert total_explained == pytest.approx(1.0, rel=1e-6)
