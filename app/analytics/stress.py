from datetime import date

import pandas as pd

SCENARIOS = {
    "2008_gfc": {"label": "2008 Financial Crisis", "start": date(2008, 9, 1), "end": date(2009, 3, 1)},
    "2020_covid": {"label": "2020 COVID Crash", "start": date(2020, 2, 15), "end": date(2020, 3, 23)},
    "2022_selloff": {"label": "2022 Rate-Hike Selloff", "start": date(2022, 1, 1), "end": date(2022, 10, 1)},
}


def run_stress_tests(prices: pd.DataFrame, weights: dict[str, float]) -> list[dict]:
    """Replay each holding's actual historical return during past crisis windows.

    Holdings that didn't exist yet in a given window are excluded and flagged; the
    remaining weights are renormalized so the scenario still reflects the portfolio's
    actual tilt rather than silently erroring out.
    """
    tickers = list(weights.keys())
    results = []

    for key, scenario in SCENARIOS.items():
        mask = (prices.index.date >= scenario["start"]) & (prices.index.date <= scenario["end"])
        window = prices.loc[mask, tickers]

        available = [t for t in tickers if t in window.columns and window[t].notna().sum() > 1]
        missing = [t for t in tickers if t not in available]

        if not available:
            results.append(
                {
                    "scenario": key,
                    "label": scenario["label"],
                    "start": scenario["start"].isoformat(),
                    "end": scenario["end"].isoformat(),
                    "applicable": False,
                    "missing_tickers": missing,
                    "portfolio_return": None,
                }
            )
            continue

        sub = window[available].dropna()
        renorm_total = sum(weights[t] for t in available)
        renorm_weights = {t: weights[t] / renorm_total for t in available}

        start_prices = sub.iloc[0]
        end_prices = sub.iloc[-1]
        asset_returns = (end_prices / start_prices) - 1
        port_return = float(sum(asset_returns[t] * renorm_weights[t] for t in available))

        results.append(
            {
                "scenario": key,
                "label": scenario["label"],
                "start": scenario["start"].isoformat(),
                "end": scenario["end"].isoformat(),
                "applicable": True,
                "missing_tickers": missing,
                "portfolio_return": port_return,
            }
        )

    return results
