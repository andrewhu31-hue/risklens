"""Portfolio risk metrics.

Inputs are daily *simple* returns (see `returns.aligned_returns`). Metrics that are
undefined for the data (e.g. Sortino with no losing days, beta against a constant
benchmark) are returned as None rather than a misleading 0.
"""
import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _finite_or_none(x) -> float | None:
    if x is None:
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def _weight_vector(tickers: list[str], weights: dict[str, float]) -> np.ndarray:
    return np.array([weights[t] for t in tickers])


def covariance_matrix(returns: pd.DataFrame) -> np.ndarray:
    """Annualized sample covariance matrix (Sigma, n-1 denominator)."""
    return returns.cov().values * TRADING_DAYS


def portfolio_returns(returns: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Daily portfolio return as the value-weighted sum of simple asset returns."""
    tickers = list(weights.keys())
    w = _weight_vector(tickers, weights)
    return returns[tickers].dot(w)


def volatility(returns: pd.DataFrame, weights: dict[str, float]) -> float:
    """Annualized portfolio volatility: sqrt(w^T Sigma w)."""
    tickers = list(weights.keys())
    cov = covariance_matrix(returns[tickers])
    w = _weight_vector(tickers, weights)
    variance = float(w @ cov @ w)
    return float(np.sqrt(max(variance, 0.0)))


def annualized_return(port_rets: pd.Series) -> float:
    return float(port_rets.mean() * TRADING_DAYS)


def sharpe_ratio(port_rets: pd.Series, risk_free: float = 0.0) -> float | None:
    vol = float(port_rets.std() * np.sqrt(TRADING_DAYS))
    if not math.isfinite(vol) or vol <= 1e-12:
        return None
    return _finite_or_none((annualized_return(port_rets) - risk_free) / vol)


def downside_deviation(port_rets: pd.Series, mar: float = 0.0) -> float:
    """Daily downside deviation below `mar`: sqrt(mean(min(r - mar, 0)^2)) over ALL days."""
    shortfall = np.minimum(np.asarray(port_rets, dtype=float) - mar, 0.0)
    return float(np.sqrt(np.mean(shortfall**2))) if len(shortfall) else float("nan")


def sortino_ratio(port_rets: pd.Series, risk_free: float = 0.0) -> float | None:
    """Sortino ratio with MAR = 0 (Sortino & Price, 1994). None when there is no
    downside (no losing days), where the ratio is undefined."""
    dd = downside_deviation(port_rets)
    if not math.isfinite(dd) or dd <= 1e-12:
        return None
    return _finite_or_none((annualized_return(port_rets) - risk_free) / (dd * np.sqrt(TRADING_DAYS)))


def max_drawdown(port_rets: pd.Series) -> float:
    """Largest peak-to-trough fall of wealth that starts at 1.0 (simple returns)."""
    wealth = np.concatenate([[1.0], np.cumprod(1.0 + np.asarray(port_rets, dtype=float))])
    running_max = np.maximum.accumulate(wealth)
    return float((wealth / running_max - 1.0).min())


def _tail(port_rets: pd.Series, confidence: float) -> tuple[float, np.ndarray]:
    """Empirical lower quantile without interpolation: the k-th worst return with
    k = ceil(n * (1 - confidence)), plus the k worst returns."""
    values = np.sort(np.asarray(port_rets, dtype=float))
    k = max(1, math.ceil(len(values) * (1 - confidence) - 1e-9))
    return float(values[k - 1]), values[:k]


def historical_var(port_rets: pd.Series, confidence: float = 0.95) -> float:
    """1-day historical VaR as a positive loss: minus the k-th worst return."""
    threshold, _ = _tail(port_rets, confidence)
    return float(-threshold)


def historical_cvar(port_rets: pd.Series, confidence: float = 0.95) -> float:
    """Expected shortfall: minus the mean of the k worst returns."""
    _, tail = _tail(port_rets, confidence)
    return float(-tail.mean())


def beta(port_rets: pd.Series, benchmark_rets: pd.Series | None) -> float | None:
    """Cov(p, b) / Var(b), both with the n-1 denominator. None if undefined."""
    if benchmark_rets is None:
        return None
    aligned = pd.concat([port_rets, benchmark_rets], axis=1).dropna()
    if aligned.shape[0] < 2:
        return None
    p, b = aligned.iloc[:, 0].values, aligned.iloc[:, 1].values
    bench_var = np.var(b, ddof=1)
    if not math.isfinite(bench_var) or bench_var <= 1e-18:
        return None
    return _finite_or_none(np.cov(p, b, ddof=1)[0, 1] / bench_var)


def risk_report(returns: pd.DataFrame, weights: dict[str, float], benchmark_rets: pd.Series | None) -> dict:
    port_rets = portfolio_returns(returns, weights)
    return {
        "annualized_return": _finite_or_none(annualized_return(port_rets)),
        "annualized_volatility": _finite_or_none(volatility(returns, weights)),
        "sharpe_ratio": sharpe_ratio(port_rets),
        "sortino_ratio": sortino_ratio(port_rets),
        "max_drawdown": _finite_or_none(max_drawdown(port_rets)),
        "var_95": _finite_or_none(historical_var(port_rets, 0.95)),
        "cvar_95": _finite_or_none(historical_cvar(port_rets, 0.95)),
        "var_99": _finite_or_none(historical_var(port_rets, 0.99)),
        "cvar_99": _finite_or_none(historical_cvar(port_rets, 0.99)),
        "beta": beta(port_rets, benchmark_rets),
        "num_observations": int(port_rets.shape[0]),
    }
