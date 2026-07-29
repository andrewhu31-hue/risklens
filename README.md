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

`app/services/prices.py` fetches daily prices per ticker via `yfinance` and caches them in `PriceHistory(ticker, date, adj_close)`. On each request, it only pulls the date range not already cached (from the last cached day to today, or from 2006-01-01 on first fetch — far enough back to cover the 2008 stress window). Repeated analysis on an already-synced portfolio hits the database, not the network.

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
```

## API Reference

| Method | Path | Description |
|---|---|---|
| POST | `/portfolios` | Create a portfolio (`name`, `benchmark`) |
| GET | `/portfolios/{id}` | Portfolio details + holdings |
| POST | `/portfolios/{id}/holdings` | Add holdings (JSON list) |
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
| Every endpoint (default) | 60 / minute per IP |
| `/refresh` | 10 / minute |
| `/ask` | 20 / minute |
| `/holdings/csv` | 10 / minute |

## Security

- **Rate limiting** — a default 60/minute-per-IP limit applies to every endpoint via `SlowAPIMiddleware`; the AI endpoints (`/refresh`, `/ask`) and CSV upload tighten this further since they're the most expensive to abuse (external API calls, file parsing).
- **Non-enumerable IDs** — portfolio IDs are UUIDs, not sequential integers. There's no authentication layer yet, so a guessable ID would let anyone browse another portfolio just by incrementing it (an IDOR vulnerability); UUIDs close that off without requiring a full auth system.
- **Locked-down CORS** — the API only accepts cross-origin requests from an explicit allowlist (`CORS_ORIGINS` in `.env`), not a wildcard. `allow_credentials` is `False` since the app doesn't use cookies/sessions.
- **Input validation** — tickers are validated against a strict `[A-Z0-9.-]{1,10}` pattern and share counts must be positive, on both the JSON and CSV ingestion paths, rejecting malformed or injection-shaped input before it ever reaches the database.
- **CSV upload limits** — capped at 1 MB and 500 rows, so a malicious or malformed file can't be used to exhaust memory or flood the database.
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` are set on every response.
- **No secrets in source** — `.env` is gitignored; only `.env.example` (placeholder values) is committed.

**Known gap:** there's no authentication — anyone with a portfolio's ID can view or modify it. UUIDs make that ID practically un-guessable, but they don't replace real access control. Adding user accounts/ownership would be the next real step if this went past a portfolio project.

## Project Structure

```
risklens/
├── app/
│   ├── api/                  # Route handlers (one file per resource)
│   ├── analytics/            # returns, risk, factors, optimizer, stress — pure functions
│   ├── models/
│   │   └── database.py       # SQLAlchemy ORM (Portfolio, Holding, PriceHistory)
│   ├── services/
│   │   ├── prices.py         # yfinance fetch + cache
│   │   ├── context.py        # shared PortfolioContext loader used by every endpoint
│   │   ├── ai.py             # Anthropic client wrapper
│   │   └── review.py         # context-block builder + debrief/ask prompts
│   ├── limiter.py
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── api/index.js
│   │   ├── pages/
│   │   │   ├── Upload.jsx    # create portfolio, manual entry or CSV
│   │   │   └── Dashboard.jsx # 7-tab layout
│   │   └── components/
│   │       ├── tabs/         # Overview, Risk, Factors, Correlation, Stress, Optimizer, Ask
│   │       └── ui/           # MetricCard, Charts, Skeleton, SectionHeader
├── tests/
│   ├── test_risk.py          # vol/Sharpe/VaR/CVaR against hand-computed reference values
│   ├── test_factors.py       # eigenvalues sum to trace(Σ); eigenvectors orthonormal
│   └── test_optimizer.py     # min-variance weights sum to 1, beat every single-asset vol
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
pip install -r requirements.txt

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
pytest tests/
```

18 tests validate the analytics against independently-computed reference values — not just "it ran": covariance matches `np.cov`, eigenvalues sum to the covariance matrix's trace, eigenvectors are orthonormal, risk contributions sum to 1, minimum-variance weights beat every single-asset volatility, and VaR/CVaR match a percentile-based reference computed directly in the test.

## Design

Dark theme with glassmorphism cards (`rgba(255,255,255,0.03)` backgrounds, blurred borders), a blue/cyan "quant" accent palette, and tabular numerals throughout. Gains render in emerald-400, losses in red-400, consistent with standard finance convention. No router — `App.jsx` switches between the Upload and Dashboard views directly.

## License

MIT
