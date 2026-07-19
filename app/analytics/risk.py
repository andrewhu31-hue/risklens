import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _weight_vector(tickers: list[str], weights: dict[str, float]) -> np.ndarray:
    return np.array([weights[t] for t in tickers])


def covariance_matrix(returns: pd.DataFrame) -> np.ndarray:
    """Annualized covariance matrix (Sigma) of asset returns."""
    return returns.cov().values * TRADING_DAYS


def portfolio_returns(returns: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
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


def sharpe_ratio(port_rets: pd.Series, risk_free: float = 0.0) -> float:
    vol = float(port_rets.std() * np.sqrt(TRADING_DAYS))
    if vol == 0:
        return 0.0
    return float((annualized_return(port_rets) - risk_free) / vol)


def sortino_ratio(port_rets: pd.Series, risk_free: float = 0.0) -> float:
    downside = port_rets[port_rets < 0]
    if downside.empty:
        return 0.0
    downside_vol = float(downside.std() * np.sqrt(TRADING_DAYS))
    if not downside_vol or np.isnan(downside_vol):
        return 0.0
    return float((annualized_return(port_rets) - risk_free) / downside_vol)


def max_drawdown(port_rets: pd.Series) -> float:
    cumulative = (1 + port_rets).cumprod()
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1
    return float(drawdown.min())


def historical_var(port_rets: pd.Series, confidence: float = 0.95) -> float:
    """Positive loss number: the return threshold below which (1-confidence) of days fall."""
    threshold = np.percentile(port_rets, (1 - confidence) * 100)
    return float(-threshold)


def historical_cvar(port_rets: pd.Series, confidence: float = 0.95) -> float:
    """Expected loss given a day falls beyond the VaR threshold."""
    threshold = np.percentile(port_rets, (1 - confidence) * 100)
    tail = port_rets[port_rets <= threshold]
    if tail.empty:
        return float(-threshold)
    return float(-tail.mean())


def beta(port_rets: pd.Series, benchmark_rets: pd.Series) -> float:
    aligned = pd.concat([port_rets, benchmark_rets], axis=1).dropna()
    if aligned.shape[0] < 2:
        return 0.0
    cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1]
    bench_var = np.var(aligned.iloc[:, 1])
    if bench_var == 0:
        return 0.0
    return float(cov / bench_var)


def risk_report(returns: pd.DataFrame, weights: dict[str, float], benchmark_rets: pd.Series) -> dict:
    port_rets = portfolio_returns(returns, weights)
    return {
        "annualized_return": annualized_return(port_rets),
        "annualized_volatility": volatility(returns, weights),
        "sharpe_ratio": sharpe_ratio(port_rets),
        "sortino_ratio": sortino_ratio(port_rets),
        "max_drawdown": max_drawdown(port_rets),
        "var_95": historical_var(port_rets, 0.95),
        "cvar_95": historical_cvar(port_rets, 0.95),
        "var_99": historical_var(port_rets, 0.99),
        "cvar_99": historical_cvar(port_rets, 0.99),
        "beta": beta(port_rets, benchmark_rets),
        "num_observations": int(port_rets.shape[0]),
    }
