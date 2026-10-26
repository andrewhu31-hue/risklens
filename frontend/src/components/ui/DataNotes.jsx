// Shows what period the statistics cover and any data caveats from the API.
export default function DataNotes({ window, warnings }) {
  if (!window && !(warnings && warnings.length)) return null;
  return (
    <div className="glass-card p-4 text-xs text-slate-400 space-y-1">
      {window && (
        <p>
          Statistics cover {window.start} to {window.end} ({window.observations.toLocaleString()} daily returns)
          {window.limited_by ? ` — the common history of all holdings, limited by ${window.limited_by}.` : "."}
        </p>
      )}
      {(warnings || []).map((w, i) => (
        <p key={i} className="text-amber-400/90">
          {w}
        </p>
      ))}
    </div>
  );
}
