import numpy as np
import pandas as pd


def log_returns(price_matrix: pd.DataFrame) -> pd.DataFrame:
    """Daily log returns for each column (ticker) in the price matrix."""
    rets = np.log(price_matrix / price_matrix.shift(1))
    return rets.dropna(how="all").dropna()
