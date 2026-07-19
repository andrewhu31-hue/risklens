import { useEffect, useState } from "react";
import { getRisk } from "../../api";
import MetricCard from "../ui/MetricCard.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { SkeletonGrid } from "../ui/Skeleton.jsx";

const pct = (v) => `${(v * 100).toFixed(2)}%`;

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
        <MetricCard label="Sharpe Ratio" value={risk.sharpe_ratio.toFixed(2)} />
        <MetricCard label="Sortino Ratio" value={risk.sortino_ratio.toFixed(2)} />
        <MetricCard label="Max Drawdown" value={pct(risk.max_drawdown)} tone="negative" />
        <MetricCard label="Beta" value={risk.beta.toFixed(2)} sublabel="vs benchmark" />
        <MetricCard label="95% VaR (1-day)" value={pct(risk.var_95)} tone="negative" />
        <MetricCard label="95% CVaR (1-day)" value={pct(risk.cvar_95)} tone="negative" />
        <MetricCard label="99% VaR (1-day)" value={pct(risk.var_99)} tone="negative" />
        <MetricCard label="99% CVaR (1-day)" value={pct(risk.cvar_99)} tone="negative" />
      </div>
    </div>
  );
}
