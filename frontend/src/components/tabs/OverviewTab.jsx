import { useEffect, useState } from "react";
import { getRisk, refreshPortfolio } from "../../api";
import MetricCard from "../ui/MetricCard.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { BlockSkeleton, SkeletonGrid } from "../ui/Skeleton.jsx";

const pct = (v) => `${(v * 100).toFixed(1)}%`;

export default function OverviewTab({ portfolioId }) {
  const [risk, setRisk] = useState(null);
  const [debrief, setDebrief] = useState(null);
  const [debriefError, setDebriefError] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDebriefError(null);
    setDebrief(null);

    getRisk(portfolioId)
      .then((data) => {
        if (!cancelled) setRisk(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.response?.data?.detail || "Failed to load risk metrics");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    refreshPortfolio(portfolioId)
      .then((data) => {
        if (!cancelled) setDebrief(data.debrief);
      })
      .catch((e) => {
        if (!cancelled) setDebriefError(e?.response?.data?.detail || "AI debrief unavailable");
      });

    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (loading) return <SkeletonGrid count={4} />;
  if (error) return <div className="glass-card p-4 text-red-400 text-sm">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Annualized Return"
          value={pct(risk.annualized_return)}
          tone={risk.annualized_return >= 0 ? "positive" : "negative"}
        />
        <MetricCard label="Annualized Volatility" value={pct(risk.annualized_volatility)} />
        <MetricCard label="Sharpe Ratio" value={risk.sharpe_ratio.toFixed(2)} />
        <MetricCard label="Max Drawdown" value={pct(risk.max_drawdown)} tone="negative" />
      </div>

      <div className="glass-card p-5">
        <SectionHeader title="AI Risk Debrief" subtitle="Grounded in the numbers above" />
        {debrief ? (
          <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{debrief}</p>
        ) : debriefError ? (
          <p className="text-sm text-amber-400">
            {debriefError}. Set ANTHROPIC_API_KEY in the backend .env to enable this.
          </p>
        ) : (
          <BlockSkeleton height="h-20" />
        )}
      </div>
    </div>
  );
}
