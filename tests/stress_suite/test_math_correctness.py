"""Section 1 — mathematical correctness against hand-computed values.

Every expected number below is worked out by hand in the comments (or by an
independent textbook formula such as the 2x2 quadratic for eigenvalues), NOT by
calling the same numpy/pandas routine the implementation uses.
"""
import math

import numpy as np
import pandas as pd
import pytest

from app.analytics import factors, optimizer, risk
from app.analytics.returns import aligned_returns, log_returns

TOL = 1e-9

# Hand dataset (daily returns)
#   A = [0.01, 0.03, -0.02, 0.02]  mean 0.010  deviations [0, .02, -.03, .01]  SS = 1.4e-3
#   B = [0.02, 0.00, 0.01, -0.01]  mean 0.005  deviations [.015, -.005, .005, -.015] SS = 5.0e-4
#   sum(devA*devB) = 0 - 1e-4 - 1.5e-4 - 1.5e-4 = -4.0e-4
#   sample (n-1=3): varA = 4.6667e-4, varB = 1.6667e-4, covAB = -1.3333e-4
#   annualized x252: varA = 0.1176, varB = 0.042, covAB = -0.0336
A = [0.01, 0.03, -0.02, 0.02]
B = [0.02, 0.00, 0.01, -0.01]
HAND = pd.DataFrame({"A": A, "B": B})
W = {"A": 0.6, "B": 0.4}


# --- returns -----------------------------------------------------------------

def test_log_returns_hand_values():
    prices = pd.DataFrame({"X": [100.0, 110.0, 99.0]})
    r = log_returns(prices)["X"].tolist()
    assert r == pytest.approx([math.log(1.1), math.log(0.9)], abs=TOL)


def test_simple_return_used_by_stress_replay_is_end_over_start_minus_one():
    # The codebase has no standalone simple-return helper; the stress module
    # computes (end/start - 1). 100 -> 80 must be exactly -20 %.
    from app.analytics.stress import run_stress_tests

    idx = pd.to_datetime(["2020-02-18", "2020-03-02", "2020-03-23"])
    prices = pd.DataFrame({"X": [100.0, 90.0, 80.0]}, index=idx)
    res = {s["scenario"]: s for s in run_stress_tests(prices, {"X": 1.0})}
    assert res["2020_covid"]["portfolio_return"] == pytest.approx(-0.20, abs=TOL)


# --- covariance & annualization ---------------------------------------------

def test_sample_covariance_uses_n_minus_1_and_annualizes():
    cov = risk.covariance_matrix(HAND)
    assert cov[0, 0] == pytest.approx(0.1176, abs=1e-12)
    assert cov[1, 1] == pytest.approx(0.042, abs=1e-12)
    assert cov[0, 1] == pytest.approx(-0.0336, abs=1e-12)


def test_covariance_symmetric_and_diagonal_equals_asset_variance():
    cov = risk.covariance_matrix(HAND)
    assert np.array_equal(cov, cov.T)
    assert cov[0, 0] == pytest.approx(1.4e-3 / 3 * 252, abs=1e-12)  # varA by hand
    assert cov[1, 1] == pytest.approx(5.0e-4 / 3 * 252, abs=1e-12)  # varB by hand


def test_correlation_symmetric_unit_diagonal_hand_value():
    corr = HAND.corr().values  # what /correlation returns
    # rho = covAB / (sdA*sdB) = -4e-4 / sqrt(1.4e-3 * 5e-4)
    expected = -4e-4 / math.sqrt(1.4e-3 * 5e-4)
    assert corr[0, 1] == pytest.approx(expected, abs=1e-12)
    assert np.allclose(corr, corr.T) and np.allclose(np.diag(corr), 1.0)


def test_annualized_return_and_volatility_hand_values():
    # Portfolio daily returns 0.6A+0.4B = [0.014, 0.018, -0.008, 0.008], mean 0.008
    # deviations [.006, .010, -.016, 0] SS = 3.92e-4, sample var = 1.30667e-4
    port = risk.portfolio_returns(HAND, W)
    assert port.tolist() == pytest.approx([0.014, 0.018, -0.008, 0.008], abs=TOL)
    assert risk.annualized_return(port) == pytest.approx(0.008 * 252, abs=TOL)
    # w'Σw by hand: .36*.1176 + .16*.042 + 2*.24*(-.0336) = 0.032928
    assert risk.volatility(HAND, W) ** 2 == pytest.approx(0.032928, abs=1e-12)
    assert risk.volatility(HAND, W) == pytest.approx(math.sqrt(3.92e-4 / 3 * 252), abs=1e-12)


def test_sharpe_ratio_hand_value():
    port = risk.portfolio_returns(HAND, W)
    expected = (0.008 * 252) / (math.sqrt(3.92e-4 / 3) * math.sqrt(252))
    assert risk.sharpe_ratio(port) == pytest.approx(expected, rel=1e-9)


def test_sharpe_ratio_with_risk_free_rate():
    port = risk.portfolio_returns(HAND, W)
    expected = (0.008 * 252 - 0.04) / (math.sqrt(3.92e-4 / 3) * math.sqrt(252))
    assert risk.sharpe_ratio(port, risk_free=0.04) == pytest.approx(expected, rel=1e-9)


# --- Sortino -----------------------------------------------------------------

def test_sortino_uses_standard_downside_deviation():
    """Standard Sortino (Sortino & Price 1994, MAR=0): downside deviation is
    sqrt(mean(min(r,0)^2)) over ALL observations.

    r = [.02, -.01, .03, -.02, .01, -.01]; mean = .02/6
    squares of shortfalls: 1e-4 + 4e-4 + 1e-4 = 6e-4; /6 = 1e-4 -> DD = 0.01
    Sortino = (.02/6*252) / (0.01*sqrt(252)) = 5.2915
    """
    r = pd.Series([0.02, -0.01, 0.03, -0.02, 0.01, -0.01])
    expected = (0.02 / 6 * 252) / (0.01 * math.sqrt(252))
    assert risk.sortino_ratio(r) == pytest.approx(expected, rel=1e-6)


def test_sortino_identical_losses_is_finite_and_correct():
    # Lose 1% every day: mean -.01, DD = .01 -> Sortino = -sqrt(252) = -15.87.
    r = pd.Series([-0.01] * 10)
    assert risk.sortino_ratio(r) == pytest.approx(-math.sqrt(252), rel=1e-6)


def test_sortino_single_down_day_is_not_zero():
    # One -1% day among nine +1% days: mean .008, DD = sqrt(1e-4/10)
    r = pd.Series([0.01] * 9 + [-0.01])
    expected = (0.008 * 252) / (math.sqrt(1e-4 / 10) * math.sqrt(252))
    assert risk.sortino_ratio(r) == pytest.approx(expected, rel=1e-6)


# --- VaR / CVaR --------------------------------------------------------------

def test_var_cvar_convention_free_case():
    # 94 days +1%, 6 days -10%: every standard convention gives VaR95 = CVaR95 = 10%.
    r = pd.Series([0.01] * 94 + [-0.10] * 6)
    assert risk.historical_var(r, 0.95) == pytest.approx(0.10, abs=1e-12)
    assert risk.historical_cvar(r, 0.95) == pytest.approx(0.10, abs=1e-12)


def test_var95_is_a_loss_when_5pct_of_days_are_losses():
    """95 days +1%, 5 losses of -2,-4,-6,-8,-10%.

    The 5% empirical quantile (5th worst of 100) is -2%, so VaR95 = 2% and
    CVaR95 = mean of the 5 worst = 6%. numpy's linear interpolation instead
    lands between -2% and +1%, so the implementation reports a *negative* VaR
    (a gain) even though 5% of days lost 2-10%.
    """
    r = pd.Series([0.01] * 95 + [-0.02, -0.04, -0.06, -0.08, -0.10])
    assert risk.historical_cvar(r, 0.95) == pytest.approx(0.06, abs=1e-12)
    assert risk.historical_var(r, 0.95) >= 0.02 - 1e-12


def test_cvar_at_least_var():
    rng = np.random.default_rng(11)
    r = pd.Series(rng.standard_t(3, 1000) * 0.01)
    assert risk.historical_cvar(r) >= risk.historical_var(r) - 1e-15


# --- beta --------------------------------------------------------------------

def test_beta_of_exactly_levered_benchmark_is_leverage():
    bench = pd.Series([0.01, -0.01, 0.02, -0.02])
    port = 2 * bench
    assert risk.beta(port, bench) == pytest.approx(2.0, abs=1e-12)


def test_beta_hand_value_non_proportional():
    # bench m = [.01,-.01,.02,-.02] (mean 0, SS = 1e-3)
    # port  p = [.02, 0, .01, -.03] (mean 0)  sum(p*m) = 2e-4 + 0 + 2e-4 + 6e-4 = 1e-3
    # beta = cov/var = (1e-3/3)/(1e-3/3) = 1.0 (same ddof both sides)
    bench = pd.Series([0.01, -0.01, 0.02, -0.02])
    port = pd.Series([0.02, 0.0, 0.01, -0.03])
    assert risk.beta(port, bench) == pytest.approx(1.0, abs=1e-12)


# --- risk contributions ------------------------------------------------------

def test_risk_contributions_hand_values_and_sum_to_variance():
    # Σw = [.6*.1176 + .4*(-.0336), .6*(-.0336) + .4*.042] = [.05712, -.00336]
    # contributions w*(Σw) = [.034272, -.001344], sum = .032928 = w'Σw
    rep = factors.factor_report(HAND, W)
    pct = {c["ticker"]: c["risk_contribution_pct"] for c in rep["risk_contributions"]}
    assert pct["A"] == pytest.approx(0.034272 / 0.032928, rel=1e-9)
    assert pct["B"] == pytest.approx(-0.001344 / 0.032928, rel=1e-9)
    assert sum(pct.values()) * rep["portfolio_volatility"] ** 2 == pytest.approx(0.032928, rel=1e-9)


# --- eigendecomposition ------------------------------------------------------

def test_eigenvalues_match_2x2_closed_form():
    # daily Σ: a=1.4e-3/3, d=5e-4/3, b=-4e-4/3; λ = T/2 ± sqrt(T²/4 - det)
    a, d, b = 1.4e-3 / 3, 5e-4 / 3, -4e-4 / 3
    T, det = a + d, a * d - b * b
    disc = math.sqrt(T * T / 4 - det)
    vals, vecs = factors.eigendecompose(HAND)
    assert vals.tolist() == pytest.approx([T / 2 + disc, T / 2 - disc], rel=1e-10)


def test_eigen_orthonormal_reconstruction_and_trace():
    rng = np.random.default_rng(5)
    m = rng.normal(0, 0.01, 500)
    df = pd.DataFrame({f"S{i}": (0.5 + i * 0.2) * m + rng.normal(0, 0.005, 500) for i in range(6)})
    vals, vecs = factors.eigendecompose(df)
    cov = df.cov().values
    np.testing.assert_allclose(vecs.T @ vecs, np.eye(6), atol=1e-10)
    np.testing.assert_allclose(vecs @ np.diag(vals) @ vecs.T, cov, atol=1e-14)
    assert vals.sum() == pytest.approx(np.trace(cov), rel=1e-12)
    assert np.all(np.diff(vals) <= 0)


# --- optimizer ---------------------------------------------------------------

SIG2 = np.array([[0.04, 0.006], [0.006, 0.09]])  # σ=.2,.3  ρ=.1


def test_min_variance_two_asset_closed_form():
    # w1 = (σ2² - σ12) / (σ1² + σ2² - 2σ12) = .084/.118
    w = optimizer.min_variance_weights(SIG2)
    assert w[0] == pytest.approx(0.084 / 0.118, abs=1e-4)
    assert w.sum() == pytest.approx(1.0, abs=1e-8)


def test_max_sharpe_two_asset_closed_form():
    # Tangency w ∝ Σ⁻¹μ.  Σ⁻¹μ ∝ [.09*.08-.006*.12, -.006*.08+.04*.12] = [.00648,.00432] -> [.6,.4]
    w = optimizer.max_sharpe_weights(np.array([0.08, 0.12]), SIG2)
    assert w == pytest.approx([0.6, 0.4], abs=1e-3)


def test_max_sharpe_respects_long_only_when_asset_has_negative_mean():
    cov = np.diag([0.04, 0.04, 0.04])
    w = optimizer.max_sharpe_weights(np.array([0.10, 0.05, -0.20]), cov)
    assert w.sum() == pytest.approx(1.0, abs=1e-6)
    assert np.all(w >= -1e-9) and np.all(w <= 1 + 1e-9)
    assert w[2] == pytest.approx(0.0, abs=1e-6)
    # Unconstrained part: w ∝ μ for diagonal equal-variance Σ -> [2/3, 1/3, 0]
    assert w[:2] == pytest.approx([2 / 3, 1 / 3], abs=1e-3)


def test_efficient_frontier_endpoints_are_single_assets():
    mu = np.array([0.05, 0.08, 0.12])
    cov = np.array([[0.02, 0.004, 0.002], [0.004, 0.05, 0.01], [0.002, 0.01, 0.12]])
    fr = optimizer.efficient_frontier(mu, cov, n_points=10)
    # Long-only, fully invested: the only portfolio returning max(μ) is 100% asset 3.
    assert fr[-1]["volatility"] == pytest.approx(math.sqrt(0.12), rel=1e-3)
    assert fr[0]["volatility"] == pytest.approx(math.sqrt(0.02), rel=1e-3)
    mv = optimizer.min_variance_weights(cov)
    mv_vol = math.sqrt(mv @ cov @ mv)
    assert all(p["volatility"] >= mv_vol - 1e-6 for p in fr)


def test_optimizer_failure_is_not_silently_reported_as_optimal():
    """If SLSQP fails, `_solve` returns the 1/n starting point. The report then
    labels equal weights as 'min_variance' with no flag. A NaN covariance (which
    arises from a single zero/missing price, see adversarial tests) triggers it."""
    cov = np.array([[np.nan, 0.0], [0.0, 0.04]])
    try:
        w = optimizer.min_variance_weights(cov)
    except Exception:
        return  # raising is an acceptable, explicit failure
    assert not np.allclose(w, [0.5, 0.5]), "solver failure returned equal weights as if optimal"


# --- max drawdown --------------------------------------------------------------

def test_max_drawdown_counts_loss_on_first_day():
    # Wealth 1.0 -> 0.5 -> 1.0 : max drawdown -50%.
    assert risk.max_drawdown(pd.Series([-0.5, 1.0])) == pytest.approx(-0.5, abs=1e-12)


def test_max_drawdown_of_two_consecutive_losses():
    # Wealth 1.0 -> 0.7 -> 0.56 : max drawdown -44%.
    assert risk.max_drawdown(pd.Series([-0.3, -0.2])) == pytest.approx(-0.44, abs=1e-12)


# --- pipeline-level: log returns fed into compounding formulas ----------------

def test_max_drawdown_through_pipeline_uses_correct_compounding():
    """Price 100 -> 50 -> 100 is a -50% max drawdown.

    Originally the API passed *log* returns into risk_report, whose max_drawdown
    compounded them as simple returns: (1+ln .5) = 0.307 -> -69.3%. Uses the
    pipeline's own return function (aligned_returns, as load_portfolio_context does).
    """
    prices = pd.DataFrame({"X": [100.0, 50.0, 100.0], "SPY": [100.0, 101.0, 102.0]})
    rets = aligned_returns(prices, ["X", "SPY"])
    rep = risk.risk_report(rets[["X"]], {"X": 1.0}, rets["SPY"])
    assert rep["max_drawdown"] == pytest.approx(-0.50, abs=1e-9)


def test_max_drawdown_through_pipeline_when_first_day_is_a_gain():
    # 100 -> 110 -> 55 -> 110: peak 110, trough 55 => -50%. Isolates the
    # log-vs-simple compounding error from the first-day bug.
    prices = pd.DataFrame({"X": [100.0, 110.0, 55.0, 110.0], "SPY": [100.0, 101.0, 102.0, 103.0]})
    rets = aligned_returns(prices, ["X", "SPY"])
    rep = risk.risk_report(rets[["X"]], {"X": 1.0}, rets["SPY"])
    assert rep["max_drawdown"] == pytest.approx(-0.50, abs=1e-9)


def test_portfolio_return_through_pipeline_matches_value_weighted_growth():
    """Two assets 50/50: X 100->200 (+100%), Y 100->50 (-50%). The portfolio
    goes 1.0 -> 0.5*2 + 0.5*0.5 = 1.25, a +25% day.
    Weighting log returns (the original pipeline) gave 0.5*ln2 + 0.5*ln.5 = 0."""
    prices = pd.DataFrame({"X": [100.0, 200.0], "Y": [100.0, 50.0]})
    rets = aligned_returns(prices, ["X", "Y"])
    port = risk.portfolio_returns(rets, {"X": 0.5, "Y": 0.5})
    assert float(port.iloc[0]) == pytest.approx(0.25, abs=1e-12)
