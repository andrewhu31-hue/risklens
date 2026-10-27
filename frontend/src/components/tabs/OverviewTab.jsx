import { useEffect, useState } from "react";
import { getPerformance, getRisk, refreshPortfolio } from "../../api";
import { longDate, num, pct, signedPct } from "../../format.js";
import { COLORS, PerformanceChart } from "../ui/Charts.jsx";
import DataNotes from "../ui/DataNotes.jsx";
import Figures from "../ui/Figures.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { BlockSkeleton, ErrorNote } from "../ui/Skeleton.jsx";

function Headline({ perf }) {
  const start = perf.series[0]?.date;
  const t = perf.total_return;
  const b = perf.benchmark_total_return;
  const verb = t >= 0 ? "Up" : "Down";
  return (
    <div className="max-w-[60ch]">
      <p className="text-[13px] text-muted">If you had held today's mix since {longDate(start)}</p>
      <p className="mt-1 text-[clamp(1.9rem,4.2vw,2.75rem)] leading-[1.05] font-semibold tracking-tight tabular-nums">
        <span className={t >= 0 ? "text-ink" : "text-loss"}>
          {verb} {pct(Math.abs(t), 0)}
        </span>
        {b != null && (
          <span className="text-muted-faint font-normal">
            {" "}
            vs {perf.benchmark} {signedPct(b, 0)}
          </span>
        )}
      </p>
    </div>
  );
}

function Legend({ benchmark, drawdown }) {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-0.5 w-4" style={{ background: COLORS.data }} /> Your portfolio
      </span>
      {benchmark && (
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0 w-4 border-t-[1.5px] border-dashed" style={{ borderColor: COLORS.faint }} /> {benchmark}
        </span>
      )}
      <span className="inline-flex items-center gap-1.5">
        <span className="h-0.5 w-4" style={{ background: COLORS.loss }} /> Below previous high
      </span>
      {drawdown && (
        <span className="text-muted-faint">
          Worst fall {pct(Math.abs(drawdown.depth))} from {longDate(drawdown.peak_date)} to {longDate(drawdown.trough_date)}
          {drawdown.recovered_date ? `, recovered ${longDate(drawdown.recovered_date)}` : ", not yet recovered"}
        </span>
      )}
    </div>
  );
}

export default function OverviewTab({ portfolioId }) {
  const [risk, setRisk] = useState(null);
  const [perf, setPerf] = useState(null);
  const [perfError, setPerfError] = useState(null);
  const [debrief, setDebrief] = useState(null);
  const [debriefError, setDebriefError] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const errText = (e, fallback) => e?.response?.data?.detail || fallback;

    getRisk(portfolioId)
      .then((d) => !cancelled && setRisk(d))
      .catch((e) => !cancelled && setError(errText(e, "Couldn't load risk metrics. Refresh to try again.")));
    getPerformance(portfolioId)
      .then((d) => !cancelled && setPerf(d))
      .catch((e) => !cancelled && setPerfError(errText(e, "Couldn't load the performance history.")));
    refreshPortfolio(portfolioId)
      .then((d) => !cancelled && setDebrief(d.debrief))
      .catch((e) => !cancelled && setDebriefError(errText(e, "The AI summary isn't available right now.")));

    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <ErrorNote>{error}</ErrorNote>;

  return (
    <div className="space-y-8">
      <section className="panel p-5 sm:p-6" aria-label="Performance">
        {perf ? (
          <>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <Headline perf={perf} />
            </div>
            <div className="mt-6 -ml-2">
              <PerformanceChart series={perf.series} benchmark={perf.benchmark} />
            </div>
            <div className="mt-4">
              <Legend benchmark={perf.benchmark} drawdown={perf.max_drawdown} />
            </div>
          </>
        ) : perfError ? (
          <p className="text-sm text-muted">{perfError}</p>
        ) : (
          <div className="h-[460px] animate-pulse rounded bg-rule-soft/60" aria-busy="true" aria-label="Loading" />
        )}
      </section>

      {risk ? (
        <Figures
          items={[
            {
              label: "Return per year",
              value: pct(risk.annualized_return),
              tone: risk.annualized_return >= 0 ? "positive" : "negative",
            },
            { label: "Volatility per year", value: pct(risk.annualized_volatility) },
            { label: "Sharpe ratio", value: num(risk.sharpe_ratio), sublabel: "Return per unit of risk" },
            { label: "Worst drawdown", value: pct(risk.max_drawdown), tone: "negative" },
          ]}
        />
      ) : (
        <BlockSkeleton height="h-24" />
      )}

      <section className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <div>
          <SectionHeader title="AI summary" subtitle="Written from the numbers on this page." />
          {debrief ? (
            <div className="panel p-5 sm:p-6">
              <p className="text-[15px] leading-[1.7] text-ink-soft whitespace-pre-line max-w-[70ch]">{debrief}</p>
            </div>
          ) : debriefError ? (
            <p className="text-sm text-muted">{debriefError}</p>
          ) : (
            <BlockSkeleton height="h-32" />
          )}
        </div>
        {risk && (
          <aside className="lg:pt-11">
            <DataNotes window={risk.window} warnings={risk.warnings} />
          </aside>
        )}
      </section>
    </div>
  );
}
