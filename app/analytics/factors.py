import numpy as np
import pandas as pd

TRADING_DAYS = 252


def eigendecompose(returns: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Eigendecomposition of the daily return covariance matrix (Sigma = V diag(lambda) V^T).

    Returns eigenvalues sorted descending and the matching eigenvectors as columns.
    """
    cov = returns.cov().values
    eigenvalues, eigenvectors = np.linalg.eigh(cov)  # symmetric -> ascending order
    order = np.argsort(eigenvalues)[::-1]
    return eigenvalues[order], eigenvectors[:, order]


def factor_report(returns: pd.DataFrame, weights: dict[str, float]) -> dict:
    tickers = list(returns.columns)
    eigenvalues, eigenvectors = eigendecompose(returns)
    total_variance = float(np.sum(eigenvalues))

    factors = []
    for i in range(len(eigenvalues)):
        loadings = {tickers[j]: float(eigenvectors[j, i]) for j in range(len(tickers))}
        variance_explained = float(eigenvalues[i] / total_variance) if total_variance > 0 else 0.0
        factors.append(
            {
                "factor": i + 1,
                "eigenvalue": float(eigenvalues[i]),
                "variance_explained": variance_explained,
                "loadings": loadings,
            }
        )

    # Marginal risk contribution: contribution_i = w_i * (Sigma w)_i, which sums exactly
    # to the portfolio variance w^T Sigma w, so contribution_i / variance is each
    # holding's share of total portfolio risk.
    cov_annualized = returns.cov().values * TRADING_DAYS
    w = np.array([weights[t] for t in tickers])
    port_variance = float(w @ cov_annualized @ w)
    port_vol = float(np.sqrt(max(port_variance, 0.0)))

    marginal = cov_annualized @ w
    contribution = w * marginal
    pct_contribution = contribution / port_variance if port_variance > 0 else np.zeros_like(contribution)

    risk_contributions = sorted(
        (
            {
                "ticker": tickers[i],
                "weight": float(w[i]),
                "risk_contribution_pct": float(pct_contribution[i]),
            }
            for i in range(len(tickers))
        ),
        key=lambda r: r["risk_contribution_pct"],
        reverse=True,
    )

    return {
        "factors": factors,
        "total_variance": total_variance,
        "portfolio_volatility": port_vol,
        "risk_contributions": risk_contributions,
    }
