import { useEffect, useState } from "react";
import { deleteHolding, getPortfolio } from "../api";
import AskTab from "../components/tabs/AskTab.jsx";
import CorrelationTab from "../components/tabs/CorrelationTab.jsx";
import FactorsTab from "../components/tabs/FactorsTab.jsx";
import OptimizerTab from "../components/tabs/OptimizerTab.jsx";
import OverviewTab from "../components/tabs/OverviewTab.jsx";
import RiskTab from "../components/tabs/RiskTab.jsx";
import StressTab from "../components/tabs/StressTab.jsx";

const TABS = [
  { id: "overview", label: "Overview", Component: OverviewTab },
  { id: "risk", label: "Risk", Component: RiskTab },
  { id: "factors", label: "Factors", Component: FactorsTab },
  { id: "correlation", label: "Correlation", Component: CorrelationTab },
  { id: "stress", label: "Stress Test", Component: StressTab },
  { id: "optimizer", label: "Optimizer", Component: OptimizerTab },
  { id: "ask", label: "Ask AI", Component: AskTab },
];

export default function Dashboard({ portfolioId, onReset, onLogout }) {
  const [tab, setTab] = useState("overview");
  const [portfolio, setPortfolio] = useState(null);
  const [version, setVersion] = useState(0); // bump to reload every tab after an edit
  const [notFound, setNotFound] = useState(false);

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

  if (notFound) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-4">
        <p className="text-slate-300">This portfolio no longer exists.</p>
        <button onClick={onReset} className="text-sky-400 hover:text-sky-300 text-sm">
          Back to your portfolios
        </button>
      </div>
    );
  }

  const ActiveTab = TABS.find((t) => t.id === tab)?.Component;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">{portfolio?.name || "Portfolio"}</h1>
          <p className="text-sm text-slate-400">
            {portfolio ? `${portfolio.positions.length} positions · benchmark ${portfolio.benchmark}` : ""}
          </p>
          {portfolio && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {portfolio.positions.map((p) => (
                <span
                  key={p.ticker}
                  className="text-xs text-slate-300 border border-white/10 rounded-md pl-2 pr-1 py-0.5 flex items-center gap-1"
                >
                  {p.ticker} · {p.shares.toLocaleString()}
                  <button
                    onClick={() => removePosition(p.ticker)}
                    title={`Remove ${p.ticker}`}
                    className="text-slate-500 hover:text-red-400 px-1"
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={onReset}
            className="text-sm text-slate-400 hover:text-slate-200 border border-white/10 rounded-lg px-3 py-1.5"
          >
            All portfolios
          </button>
          <button
            onClick={onLogout}
            className="text-sm text-slate-400 hover:text-slate-200 border border-white/10 rounded-lg px-3 py-1.5"
          >
            Log out
          </button>
        </div>
      </header>

      <nav className="flex gap-1 mb-6 border-b border-white/10 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
              tab === t.id ? "border-sky-400 text-sky-300" : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {ActiveTab && <ActiveTab key={`${tab}-${version}`} portfolioId={portfolioId} />}
    </div>
  );
}
