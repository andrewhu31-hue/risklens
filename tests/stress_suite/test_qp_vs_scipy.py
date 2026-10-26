"""The optimizer's own QP solver checked against SciPy SLSQP on random problems.

SciPy is a dev-only dependency (requirements-dev.txt); the API itself no longer
needs it. Covariances include singular ones (fewer factors than assets).
"""
import numpy as np
import pytest

from app.analytics import optimizer as O

scipy_optimize = pytest.importorskip("scipy.optimize")


def _reference(obj, n, cons, rng, jac=None):
    best = None
    for x0 in [np.repeat(1 / n, n)] + [rng.dirichlet(np.ones(n)) for _ in range(3)]:
        r = scipy_optimize.minimize(
            obj, x0, jac=jac, method="SLSQP", bounds=[(0, 1)] * n, constraints=cons, options={"ftol": 1e-15, "maxiter": 2000}
        )
        if r.success and (best is None or r.fun < best.fun):
            best = r
    return best


def _problems(count=60):
    rng = np.random.default_rng(0)
    for trial in range(count):
        n = int(rng.integers(2, 25))
        k = int(rng.integers(1, n + 1))
        f = rng.normal(0, 0.1, (n, k))
        cov = f @ f.T + np.diag(rng.uniform(0, 0.02, n)) * (trial % 4 != 0)
        yield rng, n, cov, rng.normal(0.06, 0.08, n)


def test_min_variance_matches_scipy():
    for rng, n, cov, _ in _problems():
        w = O.min_variance_weights(cov)
        assert abs(w.sum() - 1) < 1e-9 and w.min() >= 0
        ref = _reference(lambda x: x @ cov @ x, n, [{"type": "eq", "fun": lambda x: x.sum() - 1}], rng, jac=lambda x: 2 * cov @ x)
        if ref is None:  # SciPy itself failed; nothing to compare against
            continue
        assert w @ cov @ w <= ref.fun * (1 + 1e-5) + 1e-15


def test_max_sharpe_matches_scipy():
    compared = 0
    for rng, n, cov, mu in _problems():
        if not (mu > 0).any():
            continue
        w = O.max_sharpe_weights(mu, cov)
        sharpe = (w @ mu) / np.sqrt(w @ cov @ w)
        ref = _reference(lambda x: -(x @ mu) / np.sqrt(max(x @ cov @ x, 1e-18)), n, [{"type": "eq", "fun": lambda x: x.sum() - 1}], rng)
        if ref is None:  # SciPy itself failed on this one
            continue
        compared += 1
        assert sharpe >= -ref.fun * (1 - 1e-6)
    assert compared >= 40


def test_frontier_matches_scipy_and_keeps_every_point():
    for rng, n, cov, mu in _problems(30):
        frontier = O.efficient_frontier(mu, cov, 6)
        assert len(frontier) == 6
        for p in frontier:
            t = p["return"]
            ref = _reference(
                lambda x: x @ cov @ x,
                n,
                [{"type": "eq", "fun": lambda x: x.sum() - 1}, {"type": "eq", "fun": lambda x, t=t: x @ mu - t}],
                rng,
                jac=lambda x: 2 * cov @ x,
            )
            if ref is None:
                continue
            assert p["volatility"] ** 2 <= ref.fun * (1 + 1e-5) + 1e-15


def test_max_sharpe_undefined_when_no_positive_return():
    with pytest.raises(O.OptimizationError):
        O.max_sharpe_weights(np.array([-0.01, -0.02]), np.diag([0.04, 0.09]))
