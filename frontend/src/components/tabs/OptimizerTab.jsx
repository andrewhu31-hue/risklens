import { useEffect, useState } from "react";
import { getOptimizer } from "../../api";
import { num, pct } from "../../format.js";
import { COLORS, FrontierScatter } from "../ui/Charts.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { BlockSkeleton, ErrorNote } from "../ui/Skeleton.jsx";

const PLANS = [
  { key: "current", label: "Today", note: "Your weights" },
  { key: "min_variance", label: "Lowest risk", note: "Least volatile mix" },
  { key: "max_sharpe", label: "Best trade-off", note: "Highest Sharpe ratio" },
];

function WeightCell({ w, base }) {
  if (w == null) return <td className="px-4 py-2.5 text-right text-muted-faint">—</td>;
  const diff = base == null ? 0 : w - base;
  return (
    <td className="px-4 py-2.5">
      <div className="flex items-center justify-end gap-3">
        <div className="hidden sm:block h-1.5 w-20 rounded-full bg-rule-soft overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${Math.min(w, 1) * 100}%`, background: COLORS.data }} />
        </div>
        <span className="w-14 text-right tabular-nums text-ink">{pct(w)}</span>
        {base != null && (
          <span
            className={`w-14 text-right text-xs tabular-nums ${
              Math.abs(diff) < 0.005 ? "text-muted-faint" : diff > 0 ? "text-gain" : "text-loss"
            }`}
          >
            {Math.abs(diff) < 0.005 ? "same" : `${diff > 0 ? "+" : "−"}${(Math.abs(diff) * 100).toFixed(1)}`}
          </span>
        )}
      </div>
    </td>
  );
}

export default function OptimizerTab({ portfolioId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getOptimizer(portfolioId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e?.response?.data?.detail || "Couldn't run the optimizer."));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!data) return <BlockSkeleton height="h-96" />;

  const current = data.current.weights;
  const tickers = Object.keys(current).sort((a, b) => current[b] - current[a]);
  const failed = PLANS.filter((p) => data[p.key].status === "failed");

  return (
    <div className="space-y-10">
      <section>
        <SectionHeader
          title="Three ways to weight the same holdings"
          subtitle="Long-only mixes solved from the same return history. Changes are in percentage points against today."
        />
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-left align-bottom">
                <th scope="col" className="px-5 py-3 font-medium text-muted">Holding</th>
                {PLANS.map((p) => (
                  <th key={p.key} scope="col" className="px-4 py-3 text-right">
                    <span className="block font-semibold text-ink">{p.label}</span>
                    <span className="block text-xs font-normal text-muted">{p.note}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tickers.map((t) => (
                <tr key={t} className="border-b border-rule-soft">
                  <th scope="row" className="px-5 py-2.5 text-left font-semibold text-ink">{t}</th>
                  {PLANS.map((p) => (
                    <WeightCell
                      key={p.key}
                      w={data[p.key].weights?.[t]}
                      base={p.key === "current" ? null : current[t]}
                    />
                  ))}
                </tr>
              ))}
              {[
                ["Return per year", "return", (v) => pct(v)],
                ["Volatility per year", "volatility", (v) => pct(v)],
                ["Sharpe ratio", "sharpe", (v) => num(v)],
              ].map(([label, key, fmt], i) => (
                <tr key={key} className={i === 0 ? "border-t-2 border-rule" : ""}>
                  <th scope="row" className="px-5 py-2.5 text-left font-medium text-muted">{label}</th>
                  {PLANS.map((p) => (
                    <td key={p.key} className="px-4 py-2.5 text-right tabular-nums font-semibold text-ink">
                      {fmt(data[p.key][key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {failed.length > 0 && (
          <p className="mt-3 text-sm text-caution">
            {failed.map((p) => p.label).join(" and ")}: no solution for this portfolio.{" "}
            {data[failed[0].key].message}
          </p>
        )}
      </section>

      <section>
        <SectionHeader
          title="Efficient frontier"
          subtitle="Each blue point is the least volatile mix for its level of return. The red diamond is you; the gap to the curve is avoidable risk."
        />
        <div className="panel p-5 sm:p-6">
          <FrontierScatter frontier={data.efficient_frontier} current={data.current} />
        </div>
      </section>
    </div>
  );
}
