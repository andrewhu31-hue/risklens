"""Section 6a — analytics scaling and in-process API benchmarks.

Run:  python -m tests.stress_suite.perf_bench --out perf_results.json

Grows portfolio size and history length gradually and stops a series early if
a single call exceeds --max-seconds. Everything is offline (FakeMarket).
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
import time
import tracemalloc
from datetime import date

os.environ.setdefault("JWT_SECRET", "perf-secret-that-is-long-enough-0123456789abcdef")
_tmp = tempfile.mkdtemp(prefix="risklens-perf-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/perf.db"

import numpy as np
import pandas as pd

from app.analytics import optimizer as opt_mod
from app.analytics.factors import factor_report
from app.analytics.optimizer import optimizer_report
from app.analytics.returns import log_returns
from app.analytics.risk import risk_report
from app.analytics.stress import run_stress_tests

from tests.stress_suite.conftest import FIXTURE_TODAY, FakeMarket, trading_days


def synthetic_prices(n_assets, n_days, seed=0):
    rng = np.random.default_rng(seed)
    idx = trading_days("2000-01-03", FIXTURE_TODAY)[-n_days:]
    market = rng.normal(0.0003, 0.011, n_days)
    betas = rng.uniform(0.4, 1.6, n_assets)
    idio = rng.normal(0, 0.012, (n_days, n_assets))
    rets = market[:, None] * betas + idio
    prices = 100 * np.exp(np.cumsum(rets, axis=0))
    cols = [f"T{i:03d}" for i in range(n_assets)]
    df = pd.DataFrame(prices, index=idx, columns=cols)
    df["SPY"] = 100 * np.exp(np.cumsum(market))
    return df, cols


def timed(fn, *a, **k):
    tracemalloc.start()
    t0 = time.perf_counter()
    out = fn(*a, **k)
    dt = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return out, dt, peak / 1e6


def bench_analytics(sizes, lengths, max_seconds):
    rows = []
    real_minimize = opt_mod.minimize
    for n_days in lengths:
        skip_opt = False
        for n in sizes:
            prices, cols = synthetic_prices(n, n_days, seed=n * 7 + n_days)
            rets = log_returns(prices)
            w = {t: 1 / n for t in cols}
            row = {"assets": n, "days": n_days}
            _, row["risk_s"], row["risk_mb"] = timed(risk_report, rets[cols], w, rets["SPY"])
            _, row["factors_s"], row["factors_mb"] = timed(factor_report, rets[cols], w)
            _, row["stress_s"], row["stress_mb"] = timed(run_stress_tests, prices, w)
            if n >= 2 and not skip_opt:
                stats = {"calls": 0, "fail": 0}

                def counting(*a, **k):
                    r = real_minimize(*a, **k)
                    stats["calls"] += 1
                    stats["fail"] += 0 if r.success else 1
                    return r

                opt_mod.minimize = counting
                try:
                    _, row["optimize_s"], row["optimize_mb"] = timed(optimizer_report, rets[cols], w)
                finally:
                    opt_mod.minimize = real_minimize
                row["slsqp_solves"] = stats["calls"]
                row["slsqp_failures"] = stats["fail"]
                if row["optimize_s"] > max_seconds:
                    skip_opt = True  # don't grow optimizer further at this length
            rows.append(row)
            print(json.dumps(row), flush=True)
    return rows


def bench_api(sizes, provider_delay):
    """End-to-end through FastAPI with the SQLite price cache."""
    import app.services.prices as prices_mod
    from fastapi.testclient import TestClient

    from app.limiter import limiter
    from app.main import app
    from app.models import database as dbmod

    class Frozen(date):
        _today = FIXTURE_TODAY

        @classmethod
        def today(cls):
            return cls._today

    prices_mod.date = Frozen
    limiter.reset()
    out = []
    for n in sizes:
        dbmod.Base.metadata.drop_all(dbmod.engine)
        dbmod.Base.metadata.create_all(dbmod.engine)
        limiter.reset()
        mkt = FakeMarket()
        prices_mod.yf = mkt
        df, cols = synthetic_prices(n, 5200, seed=n)
        for c in df.columns:
            mkt.series[c] = df[c]
        client = TestClient(app, raise_server_exceptions=False)
        tok = client.post("/auth/register", json={"email": f"perf{n}@x.com", "password": "perfpassword"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        pid = client.post("/portfolios", json={"name": "p", "benchmark": "SPY"}, headers=h).json()["id"]
        client.post(f"/portfolios/{pid}/holdings", json=[{"ticker": t, "shares": 10} for t in cols], headers=h)

        res = {"assets": n, "history_days": len(df)}
        t0 = time.perf_counter()
        r = client.get(f"/portfolios/{pid}/risk", headers=h)
        res["cold_risk_s"] = time.perf_counter() - t0
        res["cold_status"] = r.status_code
        res["cold_provider_calls"] = len(mkt.calls)

        for ep in ["risk", "factors", "correlation", "optimize", "stress"]:
            times = []
            for _ in range(5):
                t0 = time.perf_counter()
                st = client.get(f"/portfolios/{pid}/{ep}", headers=h).status_code
                times.append(time.perf_counter() - t0)
            res[f"warm_{ep}_median_s"] = statistics.median(times)
            res[f"warm_{ep}_status"] = st
        res["warm_provider_calls"] = len(mkt.calls) - res["cold_provider_calls"]

        # Stale-by-one-day cache (e.g. a Sunday / Monday pre-close) with a slow provider.
        mkt.delay = provider_delay
        Frozen._today = date(2026, 10, 28)
        before = len(mkt.calls)
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            client.get(f"/portfolios/{pid}/risk", headers=h)
            times.append(time.perf_counter() - t0)
        res["stale_slow_provider_risk_median_s"] = statistics.median(times)
        res["stale_provider_calls_per_request"] = (len(mkt.calls) - before) / 3
        res["provider_delay_s"] = provider_delay
        Frozen._today = FIXTURE_TODAY
        out.append(res)
        print(json.dumps(res), flush=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="perf_results.json")
    ap.add_argument("--max-seconds", type=float, default=30.0)
    args = ap.parse_args()
    results = {
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
        "analytics": bench_analytics([2, 5, 10, 25, 50, 100], [252, 1260, 2520, 5040], args.max_seconds),
        "api": bench_api([2, 5, 10, 25], provider_delay=0.25),
    }
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print("wrote", args.out)
