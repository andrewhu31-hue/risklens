"""Historical crisis replay.

Each holding is replayed on its OWN price history inside the window; one asset's
missing dates never shift another asset's start or end. Holdings are classified:

  * full    — traded on the window's first and last market day: included
  * partial — first traded after the window opened or stopped before it closed
              (IPO / delisting inside the window): excluded and listed, so the
              portfolio number is never a silent mix of different sub-windows
  * missing — fewer than 2 usable prices in the window: excluded and listed

Included weights are renormalized, and the response says how much of the
portfolio (by current weight) the number covers.
"""
from datetime import date

import numpy as np
import pandas as pd

SCENARIOS = {
    "2008_gfc": {"label": "2008 Financial Crisis", "start": date(2008, 9, 1), "end": date(2009, 3, 1)},
    "2020_covid": {"label": "2020 COVID Crash", "start": date(2020, 2, 15), "end": date(2020, 3, 23)},
    "2022_selloff": {"label": "2022 Rate-Hike Selloff", "start": date(2022, 1, 1), "end": date(2022, 10, 1)},
}

EDGE_TOLERANCE_DAYS = 5


def _usable(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    return s[np.isfinite(s) & (s > 0)]


def run_stress_tests(prices: pd.DataFrame, weights: dict[str, float], reference: str | None = None) -> list[dict]:
    """Replay current weights through each crisis window.

    `reference` is a market series (usually the benchmark) whose first/last trading
    day in the window defines "the window" when deciding whether a holding covered
    it fully; without one, the earliest/latest date any holding traded is used.
    """
    tickers = list(weights.keys())
    results = []

    for key, scenario in SCENARIOS.items():
        start, end = pd.Timestamp(scenario["start"]), pd.Timestamp(scenario["end"])
        in_window = {}
        for t in tickers:
            s = _usable(prices[t]) if t in prices.columns else pd.Series(dtype=float)
            s = s[(s.index >= start) & (s.index <= end)]
            if len(s) >= 2:
                in_window[t] = s

        ref_dates = None
        if reference and reference in prices.columns:
            r = _usable(prices[reference])
            r = r[(r.index >= start) & (r.index <= end)]
            if len(r) >= 2:
                ref_dates = (r.index.min(), r.index.max())
        if ref_dates is None and in_window:
            ref_dates = (min(s.index.min() for s in in_window.values()), max(s.index.max() for s in in_window.values()))

        missing = [t for t in tickers if t not in in_window]
        # A few days' slack absorbs exchange-holiday differences between markets.
        slack = pd.Timedelta(days=EDGE_TOLERANCE_DAYS)
        partial = [
            t
            for t, s in in_window.items()
            if s.index.min() > ref_dates[0] + slack or s.index.max() < ref_dates[1] - slack
        ]
        included = [t for t in tickers if t in in_window and t not in partial]

        base = {
            "scenario": key,
            "label": scenario["label"],
            "start": scenario["start"].isoformat(),
            "end": scenario["end"].isoformat(),
            "missing_tickers": missing,
            "partial_tickers": partial,
            "partial_ranges": {
                t: [in_window[t].index.min().date().isoformat(), in_window[t].index.max().date().isoformat()]
                for t in partial
            },
        }

        total = sum(weights[t] for t in included)
        if not included or total <= 0:
            results.append(
                {
                    **base,
                    "applicable": False,
                    "coverage": "none",
                    "coverage_weight": 0.0,
                    "observed_start": None,
                    "observed_end": None,
                    "asset_returns": {},
                    "portfolio_return": None,
                }
            )
            continue

        asset_returns = {t: float(in_window[t].iloc[-1] / in_window[t].iloc[0] - 1) for t in included}
        renorm = {t: weights[t] / total for t in included}
        port_return = float(sum(asset_returns[t] * renorm[t] for t in included))

        results.append(
            {
                **base,
                "applicable": True,
                "coverage": "full" if len(included) == len(tickers) else "partial",
                "coverage_weight": float(total / sum(weights.values())),
                "observed_start": ref_dates[0].date().isoformat(),
                "observed_end": ref_dates[1].date().isoformat(),
                "asset_returns": asset_returns,
                "portfolio_return": port_return,
            }
        )

    return results
