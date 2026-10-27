import { useEffect, useState } from "react";
import { getStress } from "../../api";
import { longDate, pct, signedPct } from "../../format.js";
import { COLORS } from "../ui/Charts.jsx";
import DataNotes from "../ui/DataNotes.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { BlockSkeleton, ErrorNote } from "../ui/Skeleton.jsx";

function AssetBars({ assets }) {
  const max = Math.max(...assets.map(([, r]) => Math.abs(r)), 0.01);
  return (
    <ul className="space-y-1.5">
      {assets.map(([t, r]) => (
        <li key={t} className="grid grid-cols-[3.5rem_1fr_3.5rem] items-center gap-2 text-xs tabular-nums">
          <span className="text-ink-soft font-medium">{t}</span>
          <div className="relative h-2">
            <div className="absolute inset-y-0 left-1/2 w-px bg-rule" />
            <div
              className="absolute inset-y-0 rounded-sm"
              style={{
                background: r >= 0 ? COLORS.gain : COLORS.loss,
                width: `${(Math.abs(r) / max) * 50}%`,
                [r >= 0 ? "left" : "right"]: "50%",
              }}
            />
          </div>
          <span className={`text-right ${r >= 0 ? "text-gain" : "text-loss"}`}>{signedPct(r)}</span>
        </li>
      ))}
    </ul>
  );
}

function Scenario({ s }) {
  const assets = Object.entries(s.asset_returns || {}).sort((a, b) => a[1] - b[1]);
  const start = s.observed_start || s.start;
  const end = s.observed_end || s.end;
  return (
    <article className="panel p-5 sm:p-6 grid gap-6 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)]">
      <div>
        <h3 className="font-semibold text-ink">{s.label}</h3>
        <p className="text-xs text-muted mt-0.5">
          {longDate(start)} to {longDate(end)}
        </p>
        {s.applicable ? (
          <>
            <p
              className={`mt-4 text-[40px] leading-none font-semibold tracking-tight tabular-nums ${
                s.portfolio_return >= 0 ? "text-gain" : "text-loss"
              }`}
            >
              {signedPct(s.portfolio_return)}
            </p>
            <p className={`mt-2 text-xs ${s.coverage === "full" ? "text-muted" : "text-caution"}`}>
              {s.coverage === "full"
                ? "Your whole portfolio"
                : `Covers ${pct(s.coverage_weight, 0)} of your portfolio by weight, re-weighted`}
            </p>
          </>
        ) : (
          <p className="mt-4 text-sm text-caution">None of your holdings traded through this whole period.</p>
        )}
      </div>
      <div className="space-y-3">
        {assets.length > 0 && <AssetBars assets={assets} />}
        {s.missing_tickers.length > 0 && (
          <p className="text-xs text-muted">Not trading yet: {s.missing_tickers.join(", ")}</p>
        )}
        {s.partial_tickers?.length > 0 && (
          <p className="text-xs text-muted">
            Left out, traded for only part of the period:{" "}
            {s.partial_tickers.map((t) => `${t} (${s.partial_ranges[t].map(longDate).join(" to ")})`).join(", ")}
          </p>
        )}
      </div>
    </article>
  );
}

export default function StressTab({ portfolioId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getStress(portfolioId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e?.response?.data?.detail || "Couldn't run the stress tests."));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!data) return <BlockSkeleton height="h-96" />;

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Past crises, replayed on today's portfolio"
        subtitle="What each holding actually did during these periods, combined at your current weights."
      />
      {data.scenarios.map((s) => (
        <Scenario key={s.scenario} s={s} />
      ))}
      <DataNotes warnings={data.warnings} />
    </div>
  );
}
