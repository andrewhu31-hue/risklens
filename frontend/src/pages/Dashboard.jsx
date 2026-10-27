import { useEffect, useState } from "react";
import { deleteHolding, getPortfolio } from "../api";
import AskTab from "../components/tabs/AskTab.jsx";
import CorrelationTab from "../components/tabs/CorrelationTab.jsx";
import FactorsTab from "../components/tabs/FactorsTab.jsx";
import OptimizerTab from "../components/tabs/OptimizerTab.jsx";
import OverviewTab from "../components/tabs/OverviewTab.jsx";
import RiskTab from "../components/tabs/RiskTab.jsx";
import StressTab from "../components/tabs/StressTab.jsx";
import TopBar from "../components/ui/TopBar.jsx";

const TABS = [
  { id: "overview", label: "Overview", Component: OverviewTab },
  { id: "risk", label: "Risk", Component: RiskTab },
  { id: "factors", label: "Factors", Component: FactorsTab },
  { id: "correlation", label: "Correlation", Component: CorrelationTab },
  { id: "stress", label: "Stress tests", Component: StressTab },
  { id: "optimizer", label: "Optimizer", Component: OptimizerTab },
  { id: "ask", label: "Ask AI", Component: AskTab },
];

const tabFromHash = () => {
  const id = window.location.hash.replace("#", "");
  return TABS.some((t) => t.id === id) ? id : "overview";
};

export default function Dashboard({ portfolioId, onReset, onLogout }) {
  const [tab, setTabState] = useState(tabFromHash);
  const [portfolio, setPortfolio] = useState(null);
  const [version, setVersion] = useState(0); // bump to reload every tab after an edit
  const [notFound, setNotFound] = useState(false);

  const setTab = (id) => {
    setTabState(id);
    try {
      window.history.replaceState(null, "", `#${id}`);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    getPortfolio(portfolioId)
      .then(setPortfolio)
      .catch((e) => {
        if (e?.response?.status === 404) setNotFound(true);
      });
  }, [portfolioId, version]);

  const removePosition = async (ticker) => {
    if (!window.confirm(`Remove ${ticker} from this portfolio?`)) return;
    await deleteHolding(portfolioId, ticker);
    setVersion((v) => v + 1);
  };

  const leave = () => {
    try {
      window.history.replaceState(null, "", window.location.pathname);
    } catch {
      /* ignore */
    }
    onReset();
  };

  const bar = (
    <TopBar>
      <button onClick={leave} className="btn-quiet py-1.5">
        All portfolios
      </button>
      <button onClick={onLogout} className="btn-quiet py-1.5">
        Log out
      </button>
    </TopBar>
  );

  if (notFound) {
    return (
      <div className="min-h-screen">
        {bar}
        <main className="max-w-6xl mx-auto px-4 sm:px-6 py-16">
          <p className="text-ink">This portfolio no longer exists.</p>
          <button onClick={leave} className="link mt-3 text-sm font-medium">
            Back to your portfolios
          </button>
        </main>
      </div>
    );
  }

  const ActiveTab = TABS.find((t) => t.id === tab)?.Component;

  return (
    <div className="min-h-screen">
      {bar}
      <div className="border-b border-rule bg-panel">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-8">
          <h1 className="text-[28px] leading-tight font-semibold tracking-tight text-ink">
            {portfolio?.name || " "}
          </h1>
          <p className="mt-1 text-sm text-muted min-h-[1.25rem]">
            {portfolio
              ? `${portfolio.positions.length} ${portfolio.positions.length === 1 ? "holding" : "holdings"}, compared with ${portfolio.benchmark}`
              : ""}
          </p>
          {portfolio && (
            <ul className="flex flex-wrap gap-1.5 mt-4" aria-label="Holdings">
              {portfolio.positions.map((p) => (
                <li
                  key={p.ticker}
                  className="group inline-flex items-center gap-1.5 rounded-panel border border-rule bg-paper pl-2.5 pr-1 py-1 text-xs"
                >
                  <span className="font-semibold text-ink">{p.ticker}</span>
                  <span className="text-muted tabular-nums">{p.shares.toLocaleString()} sh</span>
                  <button
                    onClick={() => removePosition(p.ticker)}
                    aria-label={`Remove ${p.ticker}`}
                    className="h-5 w-5 grid place-items-center rounded text-muted-faint hover:text-loss hover:bg-panel"
                  >
                    <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" stroke="currentColor" strokeWidth="1.8">
                      <path d="M2 2l8 8M10 2l-8 8" />
                    </svg>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <nav className="mt-6 -mb-px flex gap-6 overflow-x-auto" aria-label="Analysis">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                aria-current={tab === t.id ? "page" : undefined}
                className={`pb-3 text-sm whitespace-nowrap border-b-2 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-data rounded-t ${
                  tab === t.id
                    ? "border-ink text-ink font-semibold"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {ActiveTab && <ActiveTab key={`${tab}-${version}`} portfolioId={portfolioId} portfolio={portfolio} />}
      </main>
    </div>
  );
}
