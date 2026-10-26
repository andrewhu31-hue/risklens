import numpy as np
import pandas as pd
from scipy.optimize import minimize

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


def _solve(objective, n: int, extra_constraints: list | None = None) -> np.ndarray:
    x0 = np.repeat(1 / n, n)
    bounds = [(0.0, 1.0)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    if extra_constraints:
        constraints += extra_constraints

    result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    if not result.success or not np.all(np.isfinite(result.x)):
        raise OptimizationError(f"optimizer did not converge: {result.message}")
    w = np.clip(result.x, 0.0, 1.0)
    return w / w.sum()


def _check_inputs(cov: np.ndarray, mean_returns: np.ndarray | None = None) -> None:
    if not np.all(np.isfinite(cov)) or (mean_returns is not None and not np.all(np.isfinite(mean_returns))):
        raise OptimizationError("covariance or mean returns contain non-finite values")


def min_variance_weights(cov: np.ndarray) -> np.ndarray:
    _check_inputs(cov)
    return _solve(lambda w: w @ cov @ w, cov.shape[0])


def max_sharpe_weights(mean_returns: np.ndarray, cov: np.ndarray, risk_free: float = 0.0) -> np.ndarray:
    def neg_sharpe(w: np.ndarray) -> float:
        vol = np.sqrt(max(w @ cov @ w, 1e-12))
        return -(w @ mean_returns - risk_free) / vol

    _check_inputs(cov, mean_returns)
    return _solve(neg_sharpe, cov.shape[0])


def efficient_frontier(mean_returns: np.ndarray, cov: np.ndarray, n_points: int = 20) -> list[dict]:
    n = cov.shape[0]
    lo, hi = float(mean_returns.min()), float(mean_returns.max())
    frontier = []
    for target in np.linspace(lo, hi, n_points):
        extra = [{"type": "eq", "fun": lambda w, t=target: w @ mean_returns - t}]
        try:
            w = _solve(lambda w: w @ cov @ w, n, extra_constraints=extra)
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
