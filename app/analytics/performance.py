"""Growth of 1 over time for the portfolio and its benchmark, plus drawdown.

The portfolio path uses the same daily simple returns as the risk metrics
(today's weights, the window where every holding has prices), so the deepest
point of the drawdown series equals `max_drawdown` on the risk page.
"""
import math

import numpy as np
import pandas as pd

MAX_POINTS = 520  # enough for a smooth chart; long histories are thinned


def _thin(n: int, keep: set[int]) -> list[int]:
    """Evenly spaced positions in range(n), always including the ends and `keep`."""
    if n <= MAX_POINTS:
        return list(range(n))
    step = (n - 1) / (MAX_POINTS - 1)
    picks = {round(i * step) for i in range(MAX_POINTS)} | {0, n - 1} | keep
    return sorted(p for p in picks if 0 <= p < n)


def _r(x: float | None, digits: int = 6) -> float | None:
    if x is None or not math.isfinite(x):
        return None
    return round(float(x), digits)


def performance_report(
    port_rets: pd.Series,
    start_date: pd.Timestamp | None,
    benchmark_prices: pd.Series | None,
) -> dict:
    """`port_rets`: daily portfolio simple returns. `start_date`: the price date
    before the first return (where wealth is 1.0). `benchmark_prices`: the
    benchmark's price series (any dates); it is read on the portfolio's dates."""
    dates = list(port_rets.index)
    wealth = np.cumprod(1.0 + port_rets.to_numpy(dtype=float))
    if start_date is not None:
        dates = [start_date] + dates
        wealth = np.concatenate([[1.0], wealth])

    peak = np.maximum.accumulate(np.concatenate([[1.0], wealth]))[1:]
    drawdown = wealth / peak - 1.0

    bench = None
    if benchmark_prices is not None:
        b = benchmark_prices.dropna().sort_index()
        b = b.reindex(b.index.union(pd.DatetimeIndex(dates))).ffill().reindex(dates)
        if b.notna().all() and float(b.iloc[0]) > 0:
            bench = (b / float(b.iloc[0])).to_numpy(dtype=float)

    trough = int(np.argmin(drawdown))
    max_dd = float(drawdown[trough])
    drawdown_info = None
    if max_dd < 0:
        peak_pos = int(np.argmax(wealth[: trough + 1])) if wealth[: trough + 1].max() >= 1.0 else None
        recovered = next((i for i in range(trough + 1, len(wealth)) if wealth[i] >= peak[trough]), None)
        drawdown_info = {
            "depth": _r(max_dd),
            "peak_date": dates[peak_pos].date().isoformat() if peak_pos is not None else None,
            "trough_date": dates[trough].date().isoformat(),
            "recovered_date": dates[recovered].date().isoformat() if recovered is not None else None,
        }

    keep = {trough}
    series = [
        {
            "date": dates[i].date().isoformat(),
            "portfolio": _r(wealth[i]),
            "benchmark": _r(bench[i]) if bench is not None else None,
            "drawdown": _r(drawdown[i]),
        }
        for i in _thin(len(dates), keep)
    ]
    return {
        "series": series,
        "total_return": _r(wealth[-1] - 1.0),
        "benchmark_total_return": _r(bench[-1] - 1.0) if bench is not None else None,
        "max_drawdown": drawdown_info,
    }
