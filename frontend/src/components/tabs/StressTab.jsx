import { useEffect, useState } from "react";
import { getStress } from "../../api";
import { pct } from "../../format.js";
import DataNotes from "../ui/DataNotes.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { SkeletonGrid } from "../ui/Skeleton.jsx";

function Scenario({ s }) {
  const assets = Object.entries(s.asset_returns || {}).sort((a, b) => a[1] - b[1]);
  return (
    <div className="glass-card p-5 flex flex-col gap-2">
      <span className="text-sm font-medium text-slate-200">{s.label}</span>
      <span className="text-xs text-slate-500">
        {s.observed_start && s.observed_end ? `${s.observed_start} to ${s.observed_end}` : `${s.start} to ${s.end}`}
      </span>
      {s.applicable ? (
        <>
          <span
            className={`text-2xl font-semibold tabular-nums ${
              s.portfolio_return >= 0 ? "text-emerald-400" : "text-red-400"
            }`}
          >
            {pct(s.portfolio_return)}
          </span>
          <span className={`text-xs ${s.coverage === "full" ? "text-slate-500" : "text-amber-400"}`}>
            {s.coverage === "full"
              ? "Covers the whole portfolio"
              : `Covers ${pct(s.coverage_weight, 0)} of the portfolio by current weight (re-weighted)`}
          </span>
        </>
      ) : (
        <span className="text-sm text-amber-400">
          Not available — none of the holdings traded through this whole window
        </span>
      )}
      {assets.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {assets.map(([t, r]) => (
            <div key={t} className="flex justify-between text-xs tabular-nums">
              <span className="text-slate-400">{t}</span>
              <span className={r >= 0 ? "text-emerald-400/80" : "text-red-400/80"}>{pct(r)}</span>
            </div>
          ))}
        </div>
      )}
      {s.missing_tickers.length > 0 && (
        <span className="text-xs text-slate-500">No data in window: {s.missing_tickers.join(", ")}</span>
      )}
      {s.partial_tickers?.length > 0 && (
        <span className="text-xs text-slate-500">
          Excluded, traded only part of the window:{" "}
          {s.partial_tickers.map((t) => `${t} (${s.partial_ranges[t].join(" to ")})`).join(", ")}
        </span>
      )}
    </div>
  );
}

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
        subtitle="Each holding's actual price change over past crisis windows, weighted by today's portfolio"
      />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {data.scenarios.map((s) => (
          <Scenario key={s.scenario} s={s} />
        ))}
      </div>
      <DataNotes warnings={data.warnings} />
    </div>
  );
}
