import { useEffect, useState } from "react";
import { getOptimizer } from "../../api";
import { FrontierScatter } from "../ui/Charts.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { BlockSkeleton } from "../ui/Skeleton.jsx";

const pct = (v) => `${(v * 100).toFixed(1)}%`;

function WeightBar({ label, weights }) {
  const entries = Object.entries(weights).sort((a, b) => b[1] - a[1]);
  return (
    <div className="glass-card p-4">
      <span className="text-sm font-medium text-slate-200">{label}</span>
      <div className="mt-3 space-y-2">
        {entries.map(([ticker, w]) => (
          <div key={ticker} className="flex items-center gap-2">
            <span className="text-xs text-slate-400 w-14">{ticker}</span>
            <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
              <div className="h-full bg-sky-400" style={{ width: `${Math.max(w * 100, 1)}%` }} />
            </div>
            <span className="text-xs text-slate-400 w-12 text-right tabular-nums">{pct(w)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function OptimizerTab({ portfolioId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getOptimizer(portfolioId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e?.response?.data?.detail || "Failed to load"));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <div className="glass-card p-4 text-red-400 text-sm">{error}</div>;
  if (!data) return <BlockSkeleton />;

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Portfolio Optimizer"
        subtitle="Current weights vs. minimum-variance and maximum-Sharpe portfolios, solved via constrained quadratic optimization"
      />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <WeightBar label={`Current (Sharpe ${data.current.sharpe.toFixed(2)})`} weights={data.current.weights} />
        <WeightBar
          label={`Min Variance (Sharpe ${data.min_variance.sharpe.toFixed(2)})`}
          weights={data.min_variance.weights}
        />
        <WeightBar
          label={`Max Sharpe (Sharpe ${data.max_sharpe.sharpe.toFixed(2)})`}
          weights={data.max_sharpe.weights}
        />
      </div>

      <div className="glass-card p-5">
        <SectionHeader title="Efficient Frontier" subtitle="Current portfolio marked in pink" />
        <FrontierScatter frontier={data.efficient_frontier} current={data.current} />
      </div>
    </div>
  );
}
