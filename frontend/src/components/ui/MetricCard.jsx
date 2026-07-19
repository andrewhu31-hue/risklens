export default function MetricCard({ label, value, sublabel, tone = "neutral" }) {
  const toneClass =
    tone === "positive" ? "text-emerald-400" : tone === "negative" ? "text-red-400" : "text-slate-100";

  return (
    <div className="glass-card p-4 flex flex-col gap-1 transition-colors">
      <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
      <span className={`text-2xl font-semibold tabular-nums ${toneClass}`}>{value}</span>
      {sublabel ? <span className="text-xs text-slate-500">{sublabel}</span> : null}
    </div>
  );
}
