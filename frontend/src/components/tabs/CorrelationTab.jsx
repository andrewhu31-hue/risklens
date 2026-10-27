import { useEffect, useState } from "react";
import { getCorrelation } from "../../api";
import { CorrelationHeatmap } from "../ui/Charts.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { BlockSkeleton, ErrorNote } from "../ui/Skeleton.jsx";

function pairs(tickers, matrix) {
  const out = [];
  for (let i = 0; i < tickers.length; i++)
    for (let j = i + 1; j < tickers.length; j++)
      if (matrix[i][j] != null) out.push({ a: tickers[i], b: tickers[j], v: matrix[i][j] });
  return out.sort((x, y) => y.v - x.v);
}

export default function CorrelationTab({ portfolioId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getCorrelation(portfolioId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e?.response?.data?.detail || "Couldn't load correlations."));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!data) return <BlockSkeleton />;

  const ranked = pairs(data.tickers, data.matrix);
  const most = ranked[0];
  const least = ranked[ranked.length - 1];

  return (
    <div className="space-y-8">
      <div>
        <SectionHeader
          title="Which holdings move together"
          subtitle="Correlation of daily returns, from −1 (always opposite) to +1 (always together). Pairs near +1 add little diversification."
        />
        {ranked.length > 0 && (
          <dl className="grid gap-4 sm:grid-cols-2 mb-6">
            <div className="panel px-5 py-4">
              <dt className="text-[13px] text-muted">Most alike</dt>
              <dd className="mt-1 text-lg font-semibold text-ink">
                {most.a} and {most.b} <span className="tabular-nums text-data">{most.v.toFixed(2)}</span>
              </dd>
            </div>
            {ranked.length > 1 && (
              <div className="panel px-5 py-4">
                <dt className="text-[13px] text-muted">Least alike</dt>
                <dd className="mt-1 text-lg font-semibold text-ink">
                  {least.a} and {least.b}{" "}
                  <span className={`tabular-nums ${least.v < 0 ? "text-loss" : "text-muted"}`}>{least.v.toFixed(2)}</span>
                </dd>
              </div>
            )}
          </dl>
        )}
        <div className="panel p-5 sm:p-6">
          <CorrelationHeatmap tickers={data.tickers} matrix={data.matrix} />
        </div>
      </div>
    </div>
  );
}
