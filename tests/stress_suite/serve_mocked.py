"""Start the real RiskLens app under uvicorn with an offline FakeMarket.

    python -m tests.stress_suite.serve_mocked --port 8765 [--delay 0.0] [--tickers 10] [--today 2026-10-26]

Used by live_curl_checks.sh and concurrency_bench.py. Production code is not
modified; yfinance and date.today() are patched in-process before serving.
"""
import argparse
import os
import tempfile
from datetime import date

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8765)
ap.add_argument("--delay", type=float, default=0.0, help="seconds per provider call")
ap.add_argument("--tickers", type=int, default=30)
ap.add_argument("--today", default="2026-10-26")
ap.add_argument("--db", default=None)
ap.add_argument("--proxy-headers", action="store_true", help="trust X-Forwarded-For from 127.0.0.1 (uvicorn default)")
args = ap.parse_args()

os.environ.setdefault("JWT_SECRET", "live-secret-that-is-long-enough-0123456789abcdef")
os.environ["DATABASE_URL"] = args.db or f"sqlite:///{tempfile.mkdtemp(prefix='risklens-live-')}/live.db"
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

import uvicorn

import app.services.prices as prices_mod
from tests.stress_suite.conftest import FakeMarket
from tests.stress_suite.perf_bench import synthetic_prices

frozen = date.fromisoformat(args.today)


class _Frozen(date):
    @classmethod
    def today(cls):
        return frozen


prices_mod.date = _Frozen
mkt = FakeMarket()
mkt.delay = args.delay
df, cols = synthetic_prices(args.tickers, 5200, seed=42)
for c in df.columns:
    mkt.series[c] = df[c]
prices_mod.yf = mkt

from app.main import app  # noqa: E402

if __name__ == "__main__":
    print(f"tickers available: {cols[:5]}... SPY; provider delay {args.delay}s; today={frozen}", flush=True)
    # A server exposed directly must not trust client-supplied X-Forwarded-For
    # (it is the rate-limit key for anonymous requests); only enable it behind
    # a proxy that overwrites the header.
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", proxy_headers=args.proxy_headers)
