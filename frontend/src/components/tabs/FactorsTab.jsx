import { useEffect, useState } from "react";
import { getFactors } from "../../api";
import { BarChart } from "../ui/Charts.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { BlockSkeleton } from "../ui/Skeleton.jsx";

const pct = (v) => `${(v * 100).toFixed(1)}%`;

export default function FactorsTab({ portfolioId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getFactors(portfolioId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e?.response?.data?.detail || "Failed to load"));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <div className="glass-card p-4 text-red-400 text-sm">{error}</div>;
  if (!data) return <BlockSkeleton />;

  const scree = data.factors.map((f) => ({ name: `Factor ${f.factor}`, variance: f.variance_explained }));
  const contributions = data.risk_contributions.map((c) => ({
    name: c.ticker,
    contribution: c.risk_contribution_pct,
  }));
  const firstFactorLoadings = data.factors[0].loadings;

  return (
    <div className="space-y-6">
      <div className="glass-card p-5">
        <SectionHeader
          title="Principal Risk Factors"
          subtitle="Eigendecomposition of the return covariance matrix — how much of total variance each factor explains"
        />
        <BarChart data={scree} xKey="name" yKey="variance" formatValue={pct} />
      </div>

      <div className="glass-card p-5">
        <SectionHeader
          title="Risk Contribution by Holding"
          subtitle="Share of total portfolio variance each position drives — independent of position size"
        />
        <BarChart data={contributions} xKey="name" yKey="contribution" color="#f472b6" formatValue={pct} />
      </div>

      <div className="glass-card p-5 overflow-x-auto">
        <SectionHeader title="Factor Loadings" subtitle="How each holding loads onto each principal factor" />
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-400 text-left border-b border-white/10">
              <th className="py-2 pr-4">Holding</th>
              {data.factors.map((f) => (
                <th key={f.factor} className="py-2 pr-4 tabular-nums">
                  Factor {f.factor}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.keys(firstFactorLoadings).map((ticker) => (
              <tr key={ticker} className="border-b border-white/5">
                <td className="py-2 pr-4 font-medium text-slate-200">{ticker}</td>
                {data.factors.map((f) => (
                  <td key={f.factor} className="py-2 pr-4 tabular-nums text-slate-300">
                    {f.loadings[ticker].toFixed(3)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
