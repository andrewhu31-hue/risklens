# RiskLens

AI-powered portfolio risk & factor analyzer. Enter your holdings — RiskLens pulls historical prices, decomposes the return covariance matrix into principal risk factors, prices Value-at-Risk, solves for minimum-variance and maximum-Sharpe portfolios, replays your holdings through past market crashes, and delivers a Claude-generated risk debrief grounded in the actual numbers.

## What it does

- Enter holdings manually (ticker + shares) or upload a CSV
- Historical daily prices are pulled via `yfinance` and cached, so repeat analysis is fast
- **Eigendecomposition of the return covariance matrix** into principal risk factors, with per-holding factor loadings and % variance explained
- **Marginal risk contribution per holding** — ranks which positions actually drive portfolio risk, independent of position size
- Full risk report: annualized return/volatility, Sharpe, Sortino, max drawdown, historical VaR/CVaR (95%/99%), beta vs. a benchmark
- Correlation matrix heatmap across holdings
- **Minimum-variance and maximum-Sharpe portfolios** solved via constrained quadratic optimization (`scipy.optimize`), plus an efficient frontier, compared against your current weights
- Historical stress tests: replays your actual holdings' returns through the 2008 GFC, 2020 COVID crash, and 2022 rate-hike selloff
- An AI risk debrief and "ask the AI" chat, both grounded in the portfolio's actual computed statistics — no invented numbers

## Architecture

```
Browser
  │
  ├─ POST /portfolios ──────────────────────────────► FastAPI
  ├─ POST /portfolios/{id}/holdings (JSON or CSV)         │
  ├─ POST /portfolios/{id}/refresh ──── fetch/cache prices (yfinance)
  │                                     │                  │
  │                              SQLite/Postgres      Claude API
  │                              (Portfolio,          (risk debrief)
  │                               Holding,
  │                               PriceHistory)
  │                                     │
  │                          analytics pipeline:
  │                          prices → log returns → covariance (Σ)
  │                          → eigendecomposition (factors)
  │                          → risk metrics (vol, Sharpe, VaR, CVaR)
  │                          → optimizer (min-variance / max-Sharpe)
  │                          → stress replay
  │                                     │
  │  GET /risk, /factors, /correlation,│
  │      /optimize, /stress  ◄─────────┘
  │
  └─ POST /ask ──────────► build_context(stats) ─────► Claude API
```

## Analytics Pipeline

Every endpoint shares one context loader (`app/services/context.py`): given a portfolio, it fetches/caches price history for every holding plus the benchmark, builds a price matrix, computes daily log returns, and derives each holding's weight from its latest market value. All analytics operate on this shared `PortfolioContext`.

| Stage | Module | What it computes |
|---|---|---|
| Returns | `analytics/returns.py` | Daily log returns from the cached price matrix |
| Risk | `analytics/risk.py` | Annualized return/vol (`sqrt(wᵀΣw)`), Sharpe, Sortino, max drawdown, historical VaR/CVaR, beta |
| Factors | `analytics/factors.py` | Eigendecomposition of Σ (`np.linalg.eigh`) → principal factors, % variance explained, per-holding loadings, marginal risk contribution (`wᵢ·(Σw)ᵢ / σₚ²`) |
| Optimizer | `analytics/optimizer.py` | Minimum-variance and maximum-Sharpe weights via `scipy.optimize.minimize` (SLSQP, `Σw=1`, `w≥0`), plus a swept efficient frontier |
| Stress | `analytics/stress.py` | Replays current holdings' actual historical returns across 2008 GFC / 2020 COVID crash / 2022 selloff windows; holdings that didn't exist yet are excluded and flagged |

The factor decomposition is the core of the app: the return covariance matrix Σ is a real symmetric matrix, so `Σ = VΛVᵀ` — its eigenvectors are the portfolio's principal risk factors and its eigenvalues are how much variance each factor explains. This is computed directly (`np.linalg.eigh`), not hidden behind a black-box library call.

## Price Caching

`app/services/prices.py` fetches daily prices per ticker via `yfinance` (in parallel, with a timeout) and caches them in `PriceHistory(ticker, date, adj_close)`, with a per-ticker `PriceFetch` log:

- First fetch pulls everything from 2006-01-01 (covers the 2008 stress window); a cache that was never fully loaded is backfilled.
- Later fetches pull only the tail, with a 10-day overlap. If the overlapping adjusted closes changed (a split or dividend re-based history), the full history is re-pulled so old- and new-basis prices never mix.
- The cache counts as fresh once it holds the last complete weekday session, and a ticker checked today isn't re-asked for 6 hours (this includes tickers with no data).
- If the provider fails, cached prices are used with a warning; only a ticker with nothing cached returns HTTP 503.

Each ticker keeps its own history in the price matrix (no forward-fill, no shared row-dropping). Return-based statistics use simple returns on the dates where all holdings traded; responses include that `window` and any `warnings` (e.g. a young holding limiting the window, or a delisted holding with a stale last price). The benchmark never shortens the window. Stress replays use each holding's own prices inside each crisis window and report `coverage`, `coverage_weight`, `partial_tickers` and per-asset returns.

## AI Layer

`app/services/review.py` builds a context block from the actual computed risk/factor stats (weights, return, volatility, Sharpe/Sortino, max drawdown, VaR/CVaR, beta, dominant factor's variance explained, top risk contributors) and hands it to Claude (`app/services/ai.py`) with an explicit instruction not to invent numbers. This same context block powers both the automatic post-refresh debrief and the `/ask` chat endpoint.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Recharts |
| Backend API | FastAPI, SQLAlchemy 2.0, python-dotenv, slowapi |
| AI | Anthropic Claude API |
| Analytics | NumPy (eigendecomposition), SciPy (constrained optimization), pandas |
| Market data | yfinance |
| Database | SQLite (dev) / Postgres-ready via `DATABASE_URL` |

## Database Schema

```
Portfolio
  id · name · benchmark · created_at

Holding
  id · portfolio_id → Portfolio
  ticker · shares · cost_basis · sector

PriceHistory
  id · ticker · date · adj_close   (unique on ticker+date)

User
  id · email · hashed_password · created_at
```

## API Reference

All `/portfolios/*` endpoints require an `Authorization: Bearer <token>` header from `/auth/login` or `/auth/register`.

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create an account, returns a bearer token |
| POST | `/auth/login` | Log in, returns a bearer token |
| GET | `/portfolios` | List the caller's portfolios |
| POST | `/portfolios` | Create a portfolio (`name`, `benchmark`), owned by the caller |
| GET | `/portfolios/{id}` | Portfolio details: individual lots (`holdings`) and lots summed per ticker (`positions`) |
| DELETE | `/portfolios/{id}` | Delete a portfolio |
| DELETE | `/portfolios/{id}/holdings/{ticker}` | Remove every lot of a ticker |
| POST | `/portfolios/{id}/holdings` | Add holdings (JSON list, max 500 per request and per portfolio) |
| POST | `/portfolios/{id}/holdings/csv` | Add holdings from a CSV (`ticker`, `shares`, optional `cost_basis`, `sector`) |
| POST | `/portfolios/{id}/refresh` | Sync price history + generate AI debrief |
| GET | `/portfolios/{id}/risk` | Return, volatility, Sharpe, Sortino, max drawdown, VaR/CVaR, beta |
| GET | `/portfolios/{id}/factors` | Eigendecomposition: factors, variance explained, loadings, risk contributions |
| GET | `/portfolios/{id}/correlation` | Pairwise return correlation matrix |
| GET | `/portfolios/{id}/optimize` | Current vs. min-variance vs. max-Sharpe weights + efficient frontier |
| GET | `/portfolios/{id}/stress` | 2008 / 2020 / 2022 historical scenario replays |
| POST | `/portfolios/{id}/ask` | AI Q&A grounded in this portfolio's stats |

### Rate limits

| Endpoint | Limit |
|---|---|
Signed-in requests are limited per user, anonymous ones per client IP, and each limit applies per endpoint (not per URL, so changing the portfolio id does not reset it). Limits are declared with explicit decorators on every route.

| Endpoint | Limit |
|---|---|
| Analytics (`/risk`, `/factors`, `/correlation`, `/optimize`, `/stress`) | 60 / minute |
| Reads (`GET /portfolios`, `GET /portfolios/{id}`) | 120 / minute |
| Writes (create, add holdings, delete) | 30 / minute |
| `/auth/register`, `/auth/login` | 10 / minute |
| `/refresh` | 10 / minute |
| `/ask` | 20 / minute (questions up to 2,000 characters) |
| `/holdings/csv` | 10 / minute |

Limit counters are kept in memory by default (per server instance). Set `RATE_LIMIT_STORAGE_URI` (e.g. a Redis URL) to share them across instances.

## Security

- **Authentication & ownership** — every portfolio belongs to a `User`, created via `/auth/register`/`/auth/login` (JWT bearer tokens, bcrypt-hashed passwords). Every portfolio-touching endpoint requires a valid token and verifies the requester actually owns the portfolio; a non-owner gets the identical "not found" response whether the ID is invalid or just belongs to someone else, so an attacker can't distinguish the two. See `app/services/auth.py` and `get_owned_portfolio` in `app/services/context.py`.
- **Rate limiting** — every route carries an explicit limit (see the table above), keyed per user when signed in and per IP otherwise; auth and the AI endpoints (`/refresh`, `/ask`) are tighter since they're the most expensive to abuse.
- **Non-enumerable IDs** — portfolio and user IDs are UUIDs, not sequential integers, on top of the ownership check above.
- **Locked-down CORS** — the API only accepts cross-origin requests from an explicit allowlist (`CORS_ORIGINS` in `.env`), not a wildcard. `allow_credentials` is `False` since auth uses a bearer token, not cookies.
- **Input validation** — tickers are validated against a strict `[A-Z0-9.-]{1,10}` pattern and share counts must be positive, on both the JSON and CSV ingestion paths, rejecting malformed or injection-shaped input before it ever reaches the database.
- **CSV upload limits** — capped at 1 MB and 500 rows, so a malicious or malformed file can't be used to exhaust memory or flood the database.
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` are set on every response.
- **No secrets in source** — `.env` is gitignored; only `.env.example` (placeholder values) is committed.

**Known tradeoff:** the frontend stores its JWT in `localStorage` and attaches it via an `Authorization` header rather than an httpOnly cookie. That's the standard pattern for a token-based SPA and avoids needing CSRF protection, but it does mean a successful XSS attack could exfiltrate the token — an httpOnly cookie would close that gap at the cost of adding CSRF machinery, which wasn't worth it at this project's scope.

## Project Structure

```
risklens/
├── app/
│   ├── api/                  # Route handlers (one file per resource)
│   │   └── auth.py           # register/login
│   ├── analytics/            # returns, risk, factors, optimizer, stress — pure functions
│   ├── models/
│   │   └── database.py       # SQLAlchemy ORM (User, Portfolio, Holding, PriceHistory)
│   ├── services/
│   │   ├── prices.py         # yfinance fetch + cache
│   │   ├── auth.py           # password hashing, JWT issue/verify, get_current_user dependency
│   │   ├── context.py        # shared PortfolioContext loader + ownership check, used by every endpoint
│   │   ├── ai.py             # Anthropic client wrapper
│   │   └── review.py         # context-block builder + debrief/ask prompts
│   ├── limiter.py
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── api/index.js      # axios instance + auth token interceptor
│   │   ├── pages/
│   │   │   ├── Login.jsx     # register/login
│   │   │   ├── Upload.jsx    # create portfolio, manual entry or CSV
│   │   │   └── Dashboard.jsx # 7-tab layout
│   │   └── components/
│   │       ├── tabs/         # Overview, Risk, Factors, Correlation, Stress, Optimizer, Ask
│   │       └── ui/           # MetricCard, Charts, Skeleton, SectionHeader
├── tests/
│   ├── test_risk.py          # vol/Sharpe/VaR/CVaR against hand-computed reference values
│   ├── test_factors.py       # eigenvalues sum to trace(Σ); eigenvectors orthonormal
│   ├── test_optimizer.py     # min-variance weights sum to 1, beat every single-asset vol
│   └── test_auth.py          # password hashing + JWT round-trip, tampered/expired token rejection
├── requirements.txt
└── .env.example
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### 1. Backend

```bash
cd risklens
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY

uvicorn app.main:app --reload
```

Tables are created automatically on startup. No API key is required for `/risk`, `/factors`, `/correlation`, `/optimize`, or `/stress` — only `/refresh` and `/ask` call Claude, and they fail with a clear 503 if the key isn't set.

### 2. Frontend

```bash
cd frontend
cp .env.example .env   # VITE_API_URL defaults to http://localhost:8000
npm install
npm run dev             # http://localhost:5173
```

### 3. Tests

```bash
pip install -r requirements-dev.txt
pytest tests/                       # 242 tests (1 skipped), offline: market data is faked
TEST_DATABASE_URL=postgresql://user@host/db pytest tests/   # same suite on Postgres
```

`tests/stress_suite/` holds the stress-test suite: hand-computed math checks, crisis-replay fixtures, adversarial inputs, cache and alignment behaviour, auth/authorization/rate limits, plus `perf_bench.py`, `concurrency_bench.py` and `live_curl_checks.sh` (run against `python -m tests.stress_suite.serve_mocked`).

## Deploying to Vercel

One Vercel project serves both the React build and the API (`api/index.py` runs the FastAPI app as a Python function under `/api`; see `vercel.json`).

1. Import the repository in Vercel. No framework preset is needed; `vercel.json` sets the build.
2. Add a Postgres database (e.g. Neon from the Vercel Marketplace). Its `DATABASE_URL` / `POSTGRES_URL` is picked up automatically. Without one, the API falls back to SQLite in `/tmp`, which is wiped whenever an instance is recycled — fine for a demo, not for real accounts.
3. Optional environment variables: `ANTHROPIC_API_KEY` (enables the AI debrief and Ask tab), `JWT_SECRET` (otherwise a random secret is generated once and stored in the database), `RATE_LIMIT_STORAGE_URI`.

## Design

Dark theme with glassmorphism cards (`rgba(255,255,255,0.03)` backgrounds, blurred borders), a blue/cyan "quant" accent palette, and tabular numerals throughout. Gains render in emerald-400, losses in red-400, consistent with standard finance convention. No router — `App.jsx` switches between the Upload and Dashboard views directly.

## License

MIT
