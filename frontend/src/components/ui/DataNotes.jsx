import { longDate } from "../../format.js";

// Shows what period the statistics cover and any data caveats from the API.
export default function DataNotes({ window, warnings }) {
  if (!window && !(warnings && warnings.length)) return null;
  return (
    <div className="text-xs text-muted space-y-1.5 max-w-[80ch] leading-relaxed">
      {window && (
        <p>
          Statistics cover {longDate(window.start)} to {longDate(window.end)} ({window.observations.toLocaleString()} daily returns)
          {window.limited_by ? `, the common history of all holdings, limited by ${window.limited_by}.` : "."}
        </p>
      )}
      {(warnings || []).map((w, i) => (
        <p key={i} className="text-caution border-l-2 border-caution/40 pl-2">
          {w}
        </p>
      ))}
    </div>
  );
}
