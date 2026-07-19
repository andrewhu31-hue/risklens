import numpy as np
import pandas as pd
from scipy.optimize import minimize

TRADING_DAYS = 252


def _annualized_cov(returns: pd.DataFrame) -> np.ndarray:
    return returns.cov().values * TRADING_DAYS


def _annualized_mean(returns: pd.DataFrame) -> np.ndarray:
    return returns.mean().values * TRADING_DAYS


def _portfolio_stats(w: np.ndarray, mean_returns: np.ndarray, cov: np.ndarray) -> dict:
    ret = float(w @ mean_returns)
    vol = float(np.sqrt(max(w @ cov @ w, 0.0)))
    sharpe = ret / vol if vol > 0 else 0.0
    return {"return": ret, "volatility": vol, "sharpe": sharpe}


def _solve(objective, n: int, extra_constraints: list | None = None) -> np.ndarray:
    x0 = np.repeat(1 / n, n)
    bounds = [(0.0, 1.0)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    if extra_constraints:
        constraints += extra_constraints

    result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    if not result.success:
        return x0
    return result.x


def min_variance_weights(cov: np.ndarray) -> np.ndarray:
    return _solve(lambda w: w @ cov @ w, cov.shape[0])


def max_sharpe_weights(mean_returns: np.ndarray, cov: np.ndarray, risk_free: float = 0.0) -> np.ndarray:
    def neg_sharpe(w: np.ndarray) -> float:
        vol = np.sqrt(max(w @ cov @ w, 1e-12))
        return -(w @ mean_returns - risk_free) / vol

    return _solve(neg_sharpe, cov.shape[0])


def efficient_frontier(mean_returns: np.ndarray, cov: np.ndarray, n_points: int = 20) -> list[dict]:
    n = cov.shape[0]
    lo, hi = float(mean_returns.min()), float(mean_returns.max())
    frontier = []
    for target in np.linspace(lo, hi, n_points):
        extra = [{"type": "eq", "fun": lambda w, t=target: w @ mean_returns - t}]
        w = _solve(lambda w: w @ cov @ w, n, extra_constraints=extra)
        frontier.append({"return": float(target), "volatility": float(np.sqrt(max(w @ cov @ w, 0.0)))})
    return frontier


def optimizer_report(returns: pd.DataFrame, weights: dict[str, float]) -> dict:
    tickers = list(weights.keys())
    sub_returns = returns[tickers]
    cov = _annualized_cov(sub_returns)
    mean_returns = _annualized_mean(sub_returns)
    current_w = np.array([weights[t] for t in tickers])

    min_var_w = min_variance_weights(cov)
    max_sharpe_w = max_sharpe_weights(mean_returns, cov)

    return {
        "tickers": tickers,
        "current": {
            "weights": dict(zip(tickers, current_w.tolist())),
            **_portfolio_stats(current_w, mean_returns, cov),
        },
        "min_variance": {
            "weights": dict(zip(tickers, min_var_w.tolist())),
            **_portfolio_stats(min_var_w, mean_returns, cov),
        },
        "max_sharpe": {
            "weights": dict(zip(tickers, max_sharpe_w.tolist())),
            **_portfolio_stats(max_sharpe_w, mean_returns, cov),
        },
        "efficient_frontier": efficient_frontier(mean_returns, cov),
    }
