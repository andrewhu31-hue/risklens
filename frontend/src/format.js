// Null-safe number formatting: the API returns null for metrics that are
// undefined for the data (e.g. Sortino with no losing days).
const ok = (v) => typeof v === "number" && Number.isFinite(v);

export const pct = (v, digits = 1) => (ok(v) ? `${(v * 100).toFixed(digits)}%` : "—");
export const num = (v, digits = 2) => (ok(v) ? v.toFixed(digits) : "—");
export const isNum = ok;
