// Null-safe number formatting: the API returns null for metrics that are
// undefined for the data (e.g. Sortino with no losing days).
const ok = (v) => typeof v === "number" && Number.isFinite(v);

export const pct = (v, digits = 1) => (ok(v) ? `${(v * 100).toFixed(digits)}%` : "—");
export const signedPct = (v, digits = 1) => (ok(v) ? `${v > 0 ? "+" : ""}${(v * 100).toFixed(digits)}%` : "—");
export const num = (v, digits = 2) => (ok(v) ? v.toFixed(digits) : "—");
export const isNum = ok;

// "2006-01-04" -> "Jan 4, 2006"
export const longDate = (iso) => {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
};
