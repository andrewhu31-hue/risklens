import numpy as np
import pandas as pd

from app.analytics import qp

TRADING_DAYS = 252


def _annualized_cov(returns: pd.DataFrame) -> np.ndarray:
    return returns.cov().values * TRADING_DAYS


def _annualized_mean(returns: pd.DataFrame) -> np.ndarray:
    return returns.mean().values * TRADING_DAYS


class OptimizationError(RuntimeError):
    """The solver did not converge; callers must not present a result as optimal."""


def _portfolio_stats(w: np.ndarray, mean_returns: np.ndarray, cov: np.ndarray) -> dict:
    ret = float(w @ mean_returns)
    vol = float(np.sqrt(max(w @ cov @ w, 0.0)))
    sharpe = ret / vol if vol > 1e-12 else None
    return {"return": ret, "volatility": vol, "sharpe": sharpe}


def _check_inputs(cov: np.ndarray, mean_returns: np.ndarray | None = None) -> None:
    if not np.all(np.isfinite(cov)) or (mean_returns is not None and not np.all(np.isfinite(mean_returns))):
        raise OptimizationError("covariance or mean returns contain non-finite values")


def _qp(Q, A, b, x0) -> np.ndarray:
    try:
        x = qp.solve(Q, A, b, x0)
    except qp.QPError as e:
        raise OptimizationError(f"optimizer did not converge: {e}") from e
    if not np.all(np.isfinite(x)):
        raise OptimizationError("optimizer produced non-finite weights")
    return x


def min_variance_weights(cov: np.ndarray) -> np.ndarray:
    """Long-only, fully invested minimum-variance weights."""
    _check_inputs(cov)
    n = cov.shape[0]
    w = _qp(cov, np.ones((1, n)), np.array([1.0]), np.repeat(1 / n, n))
    return w / w.sum()


def max_sharpe_weights(mean_returns: np.ndarray, cov: np.ndarray, risk_free: float = 0.0) -> np.ndarray:
    """Long-only tangency portfolio. With excess returns e = mu - rf, maximizing
    e'w / sqrt(w'Sw) over the simplex is equivalent to the convex problem
    min y'Sy s.t. e'y = 1, y >= 0, then w = y / sum(y) (Cornuejols & Tutuncu)."""
    _check_inputs(cov, mean_returns)
    excess = np.asarray(mean_returns, dtype=float) - risk_free
    if not np.any(excess > 0):
        raise OptimizationError("no holding has a positive expected excess return, so the maximum-Sharpe portfolio is undefined")
    k = int(np.argmax(excess))
    y0 = np.zeros(len(excess))
    y0[k] = 1 / excess[k]
    y = _qp(cov, excess.reshape(1, -1), np.array([1.0]), y0)
    if y.sum() <= 0:
        raise OptimizationError("optimizer produced an empty portfolio")
    return y / y.sum()


def efficient_frontier(mean_returns: np.ndarray, cov: np.ndarray, n_points: int = 20) -> list[dict]:
    """Minimum-variance long-only portfolio for each target return between the
    lowest and highest single-asset expected return."""
    n = cov.shape[0]
    mu = np.asarray(mean_returns, dtype=float)
    i_lo, i_hi = int(np.argmin(mu)), int(np.argmax(mu))
    lo, hi = float(mu[i_lo]), float(mu[i_hi])
    A = np.vstack([np.ones(n), mu])
    frontier = []
    steps = n_points if hi > lo else 1
    for i, target in enumerate(np.linspace(lo, hi, steps)):
        lam = 0.0 if steps == 1 else i / (steps - 1)  # exact 0 and 1 at the ends
        x0 = np.zeros(n)
        x0[i_lo] += 1 - lam
        x0[i_hi] += lam
        at_end = lam in (0.0, 1.0)
        extreme = mu[i_hi] if lam == 1.0 else mu[i_lo]
        if at_end and np.count_nonzero(np.isclose(mu, extreme, rtol=0, atol=1e-15)) == 1:
            w = x0  # a unique highest/lowest-return asset is the only feasible portfolio
        else:
            try:
                w = _qp(cov, A, np.array([1.0, target]), x0)
            except OptimizationError:
                continue  # leave out points the solver could not reach rather than mislabel them
        frontier.append({"return": float(target), "volatility": float(np.sqrt(max(w @ cov @ w, 0.0)))})
    return frontier


def optimizer_report(returns: pd.DataFrame, weights: dict[str, float]) -> dict:
    tickers = list(weights.keys())
    sub_returns = returns[tickers]
    cov = _annualized_cov(sub_returns)
    mean_returns = _annualized_mean(sub_returns)
    current_w = np.array([weights[t] for t in tickers])

    def solved(fn, *args) -> dict:
        try:
            w = fn(*args)
        except OptimizationError as e:
            return {"status": "failed", "message": str(e), "weights": None, "return": None, "volatility": None, "sharpe": None}
        return {"status": "ok", "weights": dict(zip(tickers, w.tolist())), **_portfolio_stats(w, mean_returns, cov)}

    _check_inputs(cov, mean_returns)
    return {
        "tickers": tickers,
        "current": {
            "status": "ok",
            "weights": dict(zip(tickers, current_w.tolist())),
            **_portfolio_stats(current_w, mean_returns, cov),
        },
        "min_variance": solved(min_variance_weights, cov),
        "max_sharpe": solved(max_sharpe_weights, mean_returns, cov),
        "efficient_frontier": efficient_frontier(mean_returns, cov),
    }
