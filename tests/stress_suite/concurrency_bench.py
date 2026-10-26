"""Section 6b — concurrency against a live uvicorn server (offline FakeMarket).

    python -m tests.stress_suite.concurrency_bench --out reports/concurrency_results.json

Phases (each starts small and grows):
  1. cold-cache race: K concurrent first requests for tickers not yet cached
  2. warm cache: concurrency 1..32 against /risk, /factors, /correlation, /stress
  3. stale cache + slow provider (0.5 s/call): concurrency 4..48 on /risk
SQLite file DB only — PostgreSQL behaviour is NOT covered here.
"""
import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

import httpx

SERVER_LOG = None
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def start_server(port, db, delay=0.0, today="2026-10-26", tickers=30, log_path=None):
    # Server output goes to a file: an undrained pipe fills with tracebacks and blocks the server.
    log = open(log_path or os.devnull, "a")
    p = subprocess.Popen(
        [sys.executable, "-m", "tests.stress_suite.serve_mocked", "--port", str(port), "--db", db, "--delay", str(delay), "--today", today, "--tickers", str(tickers)],
        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, text=True,
    )
    for _ in range(100):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return p
        except Exception:
            time.sleep(0.2)
    p.kill()
    raise RuntimeError("server did not start")


def stop(p):
    p.terminate()
    try:
        p.wait(10)
    except subprocess.TimeoutExpired:
        p.kill()


def setup_user(base, n_holdings, offset=0, email="load@example.com"):
    c = httpx.Client(base_url=base, timeout=60)
    r = c.post("/auth/register", json={"email": email, "password": "load-password"})
    if r.status_code == 409:
        r = c.post("/auth/login", json={"email": email, "password": "load-password"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    pid = c.post("/portfolios", json={"name": "load", "benchmark": "SPY"}, headers=h).json()["id"]
    c.post(f"/portfolios/{pid}/holdings", json=[{"ticker": f"T{i:03d}", "shares": 10 + i} for i in range(offset, offset + n_holdings)], headers=h)
    return h, pid


async def burst(base, h, paths, concurrency, total):
    sem = asyncio.Semaphore(concurrency)
    lat, codes = [], {}

    async with httpx.AsyncClient(base_url=base, timeout=180, limits=httpx.Limits(max_connections=concurrency + 4)) as c:
        async def one(i):
            async with sem:
                t0 = time.perf_counter()
                try:
                    r = await c.get(paths[i % len(paths)], headers=h)
                    code = r.status_code
                except Exception as e:
                    code = type(e).__name__
                lat.append(time.perf_counter() - t0)
                codes[code] = codes.get(code, 0) + 1

        t0 = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(total)))
        wall = time.perf_counter() - t0
    lat.sort()
    return {
        "concurrency": concurrency, "requests": total, "wall_s": round(wall, 3),
        "throughput_rps": round(total / wall, 2),
        "p50_s": round(statistics.median(lat), 3), "p95_s": round(lat[max(0, -(-95 * len(lat) // 100) - 1)], 3),
        "max_s": round(lat[-1], 3), "status_counts": {str(k): v for k, v in codes.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/concurrency_results.json")
    ap.add_argument("--holdings", type=int, default=10)
    args = ap.parse_args()
    global SERVER_LOG
    SERVER_LOG = os.path.join(os.path.dirname(os.path.abspath(args.out)), "server.log")
    open(SERVER_LOG, "w").close()
    db = f"sqlite:///{tempfile.mkdtemp(prefix='risklens-conc-')}/conc.db"
    port, base = 8771, "http://127.0.0.1:8771"
    out = {"db": "sqlite (file)", "holdings": args.holdings}

    srv = start_server(port, db, log_path=SERVER_LOG)
    try:
        # Phase 1: cold-cache race, a fresh set of tickers per level.
        out["cold_race"] = []
        for k, off in [(2, 0), (4, 10), (8, 20)]:
            h, pid = setup_user(base, args.holdings, offset=off, email=f"cold{k}@example.com")
            res = asyncio.run(burst(base, h, [f"/portfolios/{pid}/risk"], k, k))
            res["new_tickers"] = args.holdings
            out["cold_race"].append(res)
            print("cold", json.dumps(res), flush=True)

        # Phase 2: warm cache.
        h, pid = setup_user(base, args.holdings, offset=0, email="warm@example.com")
        asyncio.run(burst(base, h, [f"/portfolios/{pid}/risk"], 1, 1))  # ensure warm
        paths = [f"/portfolios/{pid}/{e}" for e in ("risk", "factors", "correlation", "stress")]
        out["warm"] = []
        for conc in (1, 2, 4, 8, 16, 32):
            res = asyncio.run(burst(base, h, paths, conc, max(16, conc * 2)))
            out["warm"].append(res)
            print("warm", json.dumps(res), flush=True)
    finally:
        stop(srv)

    # Phase 3: same DB, but 'today' is two days later (cache stale) and provider is slow.
    srv = start_server(port, db, delay=0.5, today="2026-10-28", log_path=SERVER_LOG)
    try:
        h, pid = setup_user(base, args.holdings, offset=0, email="warm@example.com")
        out["stale_slow_provider"] = []
        for conc in (4, 16, 32, 48):
            res = asyncio.run(burst(base, h, [f"/portfolios/{pid}/risk"], conc, conc))
            res["provider_delay_s"] = 0.5
            res["provider_calls_per_request"] = args.holdings + 1
            out["stale_slow_provider"].append(res)
            print("stale", json.dumps(res), flush=True)
            if res["max_s"] > 90:
                break
    finally:
        stop(srv)
        log = open(SERVER_LOG).read()
        errs = [l.strip()[:160] for l in log.splitlines() if l.strip().startswith(("sqlalchemy.", "sqlite3.", "ValueError", "TimeoutError"))]
        out["server_log_errors"] = {e: errs.count(e) for e in sorted(set(errs))}

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
