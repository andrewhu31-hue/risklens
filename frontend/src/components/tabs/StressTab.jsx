import { useEffect, useState } from "react";
import { getStress } from "../../api";
import SectionHeader from "../ui/SectionHeader.jsx";
import { SkeletonGrid } from "../ui/Skeleton.jsx";

const pct = (v) => `${(v * 100).toFixed(1)}%`;

export default function StressTab({ portfolioId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getStress(portfolioId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e?.response?.data?.detail || "Failed to load"));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <div className="glass-card p-4 text-red-400 text-sm">{error}</div>;
  if (!data) return <SkeletonGrid count={3} />;

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Historical Stress Tests"
        subtitle="Replays the portfolio's actual holdings through past crisis windows"
      />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {data.scenarios.map((s) => (
          <div key={s.scenario} className="glass-card p-5 flex flex-col gap-2">
            <span className="text-sm font-medium text-slate-200">{s.label}</span>
            <span className="text-xs text-slate-500">
              {s.start} to {s.end}
            </span>
            {s.applicable ? (
              <span
                className={`text-2xl font-semibold tabular-nums ${
                  s.portfolio_return >= 0 ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {pct(s.portfolio_return)}
              </span>
            ) : (
              <span className="text-sm text-amber-400">Not applicable — no holdings existed yet</span>
            )}
            {s.missing_tickers.length > 0 && (
              <span className="text-xs text-slate-500">Excluded (no data): {s.missing_tickers.join(", ")}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
