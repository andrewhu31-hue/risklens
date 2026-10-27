import { useEffect, useState } from "react";
import { getFactors, getOptimizer } from "../../api";
import { pct } from "../../format.js";
import { BarChart, COLORS } from "../ui/Charts.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { BlockSkeleton, ErrorNote } from "../ui/Skeleton.jsx";

// Each holding's share of the money next to its share of the risk.
function RiskVsSize({ contributions, weights }) {
  const rows = contributions
    .map((c) => ({ ticker: c.ticker, risk: c.risk_contribution_pct, weight: weights?.[c.ticker] ?? null }))
    .sort((a, b) => b.risk - a.risk);
  const max = Math.max(...rows.map((r) => Math.max(r.risk, r.weight ?? 0)), 0.01);
  const outsized = rows.filter((r) => r.weight != null && r.risk > r.weight * 1.25 && r.risk - r.weight > 0.02);

  return (
    <div className="panel p-5 sm:p-6">
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted mb-4">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-4 rounded-sm" style={{ background: COLORS.rule, outline: "1px solid #DCE0E6" }} /> Share of money
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-4 rounded-sm" style={{ background: COLORS.data }} /> Share of risk
        </span>
      </div>
      <ul className="space-y-3">
        {rows.map((r) => {
          const hot = outsized.includes(r);
          return (
            <li key={r.ticker} className="grid grid-cols-[4.5rem_1fr_7.5rem] items-center gap-3 text-sm">
              <span className="font-semibold text-ink">{r.ticker}</span>
              <div className="relative h-5">
                {r.weight != null && (
                  <div
                    className="absolute inset-y-0 left-0 rounded-sm bg-rule-soft border border-rule"
                    style={{ width: `${(r.weight / max) * 100}%` }}
                  />
                )}
                <div
                  className="absolute left-0 top-1/2 -translate-y-1/2 h-2 rounded-sm"
                  style={{ width: `${(Math.max(r.risk, 0) / max) * 100}%`, background: hot ? COLORS.loss : COLORS.data }}
                />
              </div>
              <span className="text-right tabular-nums text-xs text-muted">
                <span className={`font-semibold ${hot ? "text-loss" : "text-ink"}`}>{pct(r.risk)}</span> of risk
                {r.weight != null && <span className="block">{pct(r.weight)} of money</span>}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-5 text-sm text-ink-soft max-w-[70ch]">
        {outsized.length
          ? `${outsized.map((r) => r.ticker).join(" and ")} ${outsized.length === 1 ? "drives" : "drive"} noticeably more risk than ${outsized.length === 1 ? "its" : "their"} share of the money. Trimming ${outsized.length === 1 ? "it" : "them"} lowers volatility the most per dollar moved.`
          : "No holding carries much more risk than its share of the money. Risk is spread roughly in line with position sizes."}
      </p>
    </div>
  );
}

export default function FactorsTab({ portfolioId }) {
  const [data, setData] = useState(null);
  const [weights, setWeights] = useState(undefined);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getFactors(portfolioId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e?.response?.data?.detail || "Couldn't load the factor analysis."));
    getOptimizer(portfolioId)
      .then((d) => !cancelled && setWeights(d.current.weights))
      .catch(() => !cancelled && setWeights(null));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!data) return <BlockSkeleton height="h-96" />;

  const scree = data.factors.map((f) => ({ name: `Factor ${f.factor}`, variance: f.variance_explained }));
  const firstFactorLoadings = data.factors[0].loadings;
  const top = data.factors[0];

  return (
    <div className="space-y-10">
      <section>
        <SectionHeader
          title="Risk compared with size"
          subtitle="A holding can be a small slice of your money and still drive a large slice of the swings."
        />
        {weights === undefined ? (
          <BlockSkeleton height="h-56" />
        ) : (
          <RiskVsSize contributions={data.risk_contributions} weights={weights} />
        )}
      </section>

      <section>
        <SectionHeader
          title="Hidden drivers"
          subtitle={`Principal component analysis finds the few patterns behind most of the movement. The strongest explains ${pct(top.variance_explained, 0)} of it.`}
        />
        <div className="panel p-5 sm:p-6">
          <BarChart data={scree} xKey="name" yKey="variance" formatValue={pct} name="Movement explained" />
        </div>
      </section>

      <section>
        <SectionHeader
          title="How each holding loads on each driver"
          subtitle="Same-sign loadings on a driver move together when it moves. Darker means stronger."
        />
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead>
              <tr className="text-muted text-left border-b border-rule">
                <th scope="col" className="px-5 py-3 font-medium">Holding</th>
                {data.factors.map((f) => (
                  <th key={f.factor} scope="col" className="px-5 py-3 font-medium text-right">
                    Factor {f.factor}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.keys(firstFactorLoadings).map((ticker) => (
                <tr key={ticker} className="border-b border-rule-soft last:border-0">
                  <th scope="row" className="px-5 py-2.5 text-left font-semibold text-ink">{ticker}</th>
                  {data.factors.map((f) => {
                    const v = f.loadings[ticker];
                    const a = Math.min(Math.abs(v), 1);
                    return (
                      <td
                        key={f.factor}
                        className="px-5 py-2.5 text-right"
                        style={{ color: v >= 0 ? COLORS.data : COLORS.loss, opacity: 0.45 + a * 0.55, fontWeight: a > 0.5 ? 600 : 400 }}
                      >
                        {v.toFixed(3)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
