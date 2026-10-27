import { useEffect, useState } from "react";
import { getRisk } from "../../api";
import { num, pct as fmtPct } from "../../format.js";
import DataNotes from "../ui/DataNotes.jsx";
import Figures from "../ui/Figures.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { BlockSkeleton, ErrorNote } from "../ui/Skeleton.jsx";

const pct = (v) => fmtPct(v, 2);

export default function RiskTab({ portfolioId }) {
  const [risk, setRisk] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getRisk(portfolioId)
      .then((d) => !cancelled && setRisk(d))
      .catch((e) => !cancelled && setError(e?.response?.data?.detail || "Couldn't load risk metrics."));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!risk) return <BlockSkeleton height="h-72" />;

  return (
    <div className="space-y-10">
      <section>
        <SectionHeader
          title="Return and volatility"
          subtitle={`Annualized from ${risk.num_observations.toLocaleString()} daily returns at today's weights.`}
        />
        <Figures
          columns={5}
          items={[
            {
              label: "Return per year",
              value: pct(risk.annualized_return),
              tone: risk.annualized_return >= 0 ? "positive" : "negative",
            },
            { label: "Volatility per year", value: pct(risk.annualized_volatility) },
            { label: "Sharpe ratio", value: num(risk.sharpe_ratio), sublabel: "Return per unit of volatility" },
            { label: "Sortino ratio", value: num(risk.sortino_ratio), sublabel: "Counts only downside moves" },
            {
              label: "Beta",
              value: num(risk.beta),
              sublabel: risk.benchmark ? `1.00 moves in step with ${risk.benchmark}` : "No benchmark data",
            },
          ]}
        />
      </section>

      <section>
        <SectionHeader
          title="Bad days"
          subtitle="Value at risk is the loss a bad day reaches; expected shortfall is the average loss once it does."
        />
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead>
              <tr className="text-left text-muted border-b border-rule">
                <th scope="col" className="px-5 py-3 font-medium">How bad a day</th>
                <th scope="col" className="px-5 py-3 font-medium text-right">You lose at least</th>
                <th scope="col" className="px-5 py-3 font-medium text-right">Average loss on those days</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Worst 1 day in 20", risk.var_95, risk.cvar_95],
                ["Worst 1 day in 100", risk.var_99, risk.cvar_99],
              ].map(([label, v, c]) => (
                <tr key={label} className="border-b border-rule-soft last:border-0">
                  <th scope="row" className="px-5 py-4 text-left font-medium text-ink">{label}</th>
                  <td className="px-5 py-4 text-right text-xl font-semibold text-loss">{pct(v)}</td>
                  <td className="px-5 py-4 text-right text-xl font-semibold text-loss">{pct(c)}</td>
                </tr>
              ))}
              <tr>
                <th scope="row" className="px-5 py-4 text-left font-medium text-ink">
                  Worst stretch on record
                  <span className="block text-xs font-normal text-muted">Peak to trough, over many days</span>
                </th>
                <td className="px-5 py-4 text-right text-xl font-semibold text-loss">{pct(Math.abs(risk.max_drawdown ?? NaN))}</td>
                <td className="px-5 py-4" />
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <DataNotes window={risk.window} warnings={risk.warnings} />
    </div>
  );
}
