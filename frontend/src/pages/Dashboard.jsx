import { useEffect, useState } from "react";
import { getPortfolio } from "../api";
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

export default function Dashboard({ portfolioId, onReset }) {
  const [tab, setTab] = useState("overview");
  const [portfolio, setPortfolio] = useState(null);

  useEffect(() => {
    getPortfolio(portfolioId)
      .then(setPortfolio)
      .catch(() => {});
  }, [portfolioId]);

  const ActiveTab = TABS.find((t) => t.id === tab)?.Component;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">{portfolio?.name || "Portfolio"}</h1>
          <p className="text-sm text-slate-400">
            {portfolio ? `${portfolio.holdings.length} holdings · benchmark ${portfolio.benchmark}` : ""}
          </p>
        </div>
        <button
          onClick={onReset}
          className="text-sm text-slate-400 hover:text-slate-200 border border-white/10 rounded-lg px-3 py-1.5"
        >
          New portfolio
        </button>
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

      {ActiveTab && <ActiveTab portfolioId={portfolioId} />}
    </div>
  );
}
