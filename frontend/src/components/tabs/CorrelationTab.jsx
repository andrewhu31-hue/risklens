import { useEffect, useState } from "react";
import { getCorrelation } from "../../api";
import { CorrelationHeatmap } from "../ui/Charts.jsx";
import SectionHeader from "../ui/SectionHeader.jsx";
import { BlockSkeleton } from "../ui/Skeleton.jsx";

export default function CorrelationTab({ portfolioId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getCorrelation(portfolioId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e?.response?.data?.detail || "Failed to load"));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  if (error) return <div className="glass-card p-4 text-red-400 text-sm">{error}</div>;
  if (!data) return <BlockSkeleton />;

  return (
    <div className="glass-card p-5">
      <SectionHeader title="Correlation Matrix" subtitle="Pairwise correlation of daily returns" />
      <CorrelationHeatmap tickers={data.tickers} matrix={data.matrix} />
    </div>
  );
}
