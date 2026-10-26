import { useEffect, useState } from "react";
import { getRisk } from "../../api";
import MetricCard from "../ui/MetricCard.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { SkeletonGrid } from "../ui/Skeleton.jsx";

import { num, pct as fmtPct } from "../../format.js";
import DataNotes from "../ui/DataNotes.jsx";

const pct = (v) => fmtPct(v, 2);

export default function RiskTab({ portfolioId }) {
  const [risk, setRisk] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getRisk(portfolioId)
      .then((d) => !cancelled && setRisk(d))
      .catch((e) => !cancelled && setError(e?.response?.data?.detail || "Failed to load"));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <div className="glass-card p-4 text-red-400 text-sm">{error}</div>;
  if (!risk) return <SkeletonGrid count={8} />;

  return (
    <div className="space-y-6">
      <SectionHeader title="Risk Metrics" subtitle={`Based on ${risk.num_observations} daily observations`} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Annualized Return"
          value={pct(risk.annualized_return)}
          tone={risk.annualized_return >= 0 ? "positive" : "negative"}
        />
        <MetricCard label="Annualized Volatility" value={pct(risk.annualized_volatility)} />
        <MetricCard label="Sharpe Ratio" value={num(risk.sharpe_ratio)} />
        <MetricCard label="Sortino Ratio" value={num(risk.sortino_ratio)} />
        <MetricCard label="Max Drawdown" value={pct(risk.max_drawdown)} tone="negative" />
        <MetricCard label="Beta" value={num(risk.beta)} sublabel={risk.benchmark ? `vs ${risk.benchmark}` : "no benchmark data"} />
        <MetricCard label="95% VaR (1-day)" value={pct(risk.var_95)} tone="negative" />
        <MetricCard label="95% CVaR (1-day)" value={pct(risk.cvar_95)} tone="negative" />
        <MetricCard label="99% VaR (1-day)" value={pct(risk.var_99)} tone="negative" />
        <MetricCard label="99% CVaR (1-day)" value={pct(risk.cvar_99)} tone="negative" />
      </div>
      <DataNotes window={risk.window} warnings={risk.warnings} />
    </div>
  );
}
