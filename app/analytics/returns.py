import numpy as np
import pandas as pd


def log_returns(price_matrix: pd.DataFrame) -> pd.DataFrame:
    """Daily log returns for each column (ticker) in the price matrix."""
    rets = np.log(price_matrix / price_matrix.shift(1))
    return rets.dropna(how="all").dropna()


def aligned_returns(price_matrix: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Daily *simple* returns for `tickers`, measured between dates on which every
    one of them has a price.

    Aligning prices first (rather than forward-filling) means a gap in one asset
    — a weekend for an equity next to a 7-day crypto asset, a holiday, a missing
    day — becomes one multi-day return instead of a fake 0% day. Simple returns
    are used because portfolio returns are value-weighted sums of simple returns
    and wealth compounds as prod(1 + r).
    """
    prices = price_matrix[tickers].dropna()
    return prices.pct_change().iloc[1:]
