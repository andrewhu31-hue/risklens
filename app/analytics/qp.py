"""Small exact solver for the optimizer's quadratic programs.

    minimize    x' Q x
    subject to  A x = b,  x >= 0

Primal active-set method (Nocedal & Wright, Algorithm 16.3) on the bound
constraints. Replaces scipy.optimize.minimize/SLSQP so the API fits in a
Vercel function bundle; it is also exact (no finite-difference gradients) and
reports failure explicitly instead of returning a non-optimal point.
"""
import numpy as np


class QPError(RuntimeError):
    pass


def _step(Q: np.ndarray, A: np.ndarray, x: np.ndarray, free: np.ndarray):
    """Equality-constrained step on the free variables: minimize over d with
    A_F d_F = 0 and d_W = 0. Returns (d, lam) where lam are the equality
    multipliers of the KKT system Q_FF d_F + A_F' lam = -(Qx)_F."""
    n, m = len(x), A.shape[0]
    g = Q @ x
    F = np.flatnonzero(free)
    k = len(F)
    kkt = np.zeros((k + m, k + m))
    kkt[:k, :k] = Q[np.ix_(F, F)]
    kkt[:k, k:] = A[:, F].T
    kkt[k:, :k] = A[:, F]
    rhs = np.concatenate([-g[F], np.zeros(m)])
    sol, *_ = np.linalg.lstsq(kkt, rhs, rcond=None)
    d = np.zeros(n)
    d[F] = sol[:k]
    return d, sol[k:]


def solve(Q: np.ndarray, A: np.ndarray, b: np.ndarray, x0: np.ndarray, max_iter: int | None = None) -> np.ndarray:
    """`x0` must be feasible (A x0 = b, x0 >= 0)."""
    Q = np.asarray(Q, dtype=float)
    A = np.atleast_2d(np.asarray(A, dtype=float))
    b = np.atleast_1d(np.asarray(b, dtype=float))
    x = np.asarray(x0, dtype=float).copy()
    n = len(x)
    if not (np.all(np.isfinite(Q)) and np.all(np.isfinite(A)) and np.all(np.isfinite(b))):
        raise QPError("non-finite problem data")
    if np.any(x < -1e-12) or np.linalg.norm(A @ x - b) > 1e-9 * max(1.0, np.linalg.norm(b)):
        raise QPError("starting point is not feasible")

    Q = (Q + Q.T) / 2
    # Small ridge keeps the KKT system well posed when Q is singular (e.g.
    # perfectly correlated assets); far below any meaningful variance.
    scale = max(float(np.max(np.abs(np.diag(Q)))), 1e-300)
    Q = Q + np.eye(n) * scale * 1e-10
    mult_tol = 1e-9 * scale

    def objective(v):
        return float(v @ Q @ v)

    free = x > 0
    x[~free] = 0.0
    no_release: set[int] = set()  # bounds just shown to block; don't re-release them before progress
    for _ in range(max_iter or 50 * n + 100):
        d, lam = _step(Q, A, x, free)
        g = 2 * (Q @ x)
        decrease = float(g @ d + d @ Q @ d)  # f(x + d) - f(x)
        if np.max(np.abs(d)) <= 1e-13 or decrease > -1e-15 * max(objective(x), scale):
            nu = Q @ x + A.T @ lam  # (scaled) multipliers of the active bounds
            fixed = [i for i in np.flatnonzero(~free) if i not in no_release]
            if not fixed or min(nu[i] for i in fixed) >= -mult_tol:
                x[x < 0] = 0.0
                return x
            j = min(fixed, key=lambda i: nu[i])
            free[j] = True
            continue
        shrinking = free & (d < 0)
        if not np.any(shrinking):
            x = x + d
            no_release.clear()
            continue
        idx = np.flatnonzero(shrinking)
        ratios = x[idx] / -d[idx]
        j = int(np.argmin(ratios))
        alpha = min(1.0, float(ratios[j]))
        x = x + alpha * d
        if alpha > 0:
            no_release.clear()
        if alpha < 1.0:
            x[idx[j]] = 0.0
            free[idx[j]] = False
            if alpha == 0:
                no_release.add(int(idx[j]))
    raise QPError("active-set solver did not converge")
