import { useEffect, useState } from "react";
import { addHoldings, addHoldingsCsv, createPortfolio, deletePortfolio, listPortfolios } from "../api";
import TopBar from "../components/ui/TopBar.jsx";

const emptyRow = () => ({ ticker: "", shares: "" });

// A deliberately mixed sample: tech, a bank, energy, gold and long bonds.
const EXAMPLE = {
  name: "Example: mixed portfolio",
  rows: [
    { ticker: "AAPL", shares: "40" },
    { ticker: "MSFT", shares: "20" },
    { ticker: "NVDA", shares: "30" },
    { ticker: "JPM", shares: "35" },
    { ticker: "XOM", shares: "50" },
    { ticker: "GLD", shares: "15" },
    { ticker: "TLT", shares: "60" },
  ],
};

export default function Upload({ onReady, onLogout }) {
  const [name, setName] = useState("My portfolio");
  const [benchmark, setBenchmark] = useState("SPY");
  const [rows, setRows] = useState([emptyRow(), emptyRow(), emptyRow()]);
  const [csvFile, setCsvFile] = useState(null);
  const [mode, setMode] = useState("manual");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(null);

  useEffect(() => {
    listPortfolios()
      .then(setSaved)
      .catch(() => setSaved([]));
  }, []);

  const removeSaved = async (p) => {
    if (!window.confirm(`Delete "${p.name}"? This can't be undone.`)) return;
    try {
      await deletePortfolio(p.id);
      setSaved((s) => s.filter((x) => x.id !== p.id));
    } catch (err) {
      setError(err?.response?.data?.detail || "Couldn't delete that portfolio. Try again.");
    }
  };

  const updateRow = (i, field, value) => {
    setRows((r) => r.map((row, idx) => (idx === i ? { ...row, [field]: value } : row)));
  };
  const addRow = () => setRows((r) => [...r, emptyRow()]);
  const removeRow = (i) => setRows((r) => (r.length > 1 ? r.filter((_, idx) => idx !== i) : [emptyRow()]));

  const useExample = () => {
    setMode("manual");
    setName(EXAMPLE.name);
    setBenchmark("SPY");
    setRows(EXAMPLE.rows.map((r) => ({ ...r })));
    setError(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError(null);

    const holdings = rows
      .filter((r) => r.ticker.trim() && r.shares)
      .map((r) => ({ ticker: r.ticker.trim().toUpperCase(), shares: parseFloat(r.shares) }));
    if (mode === "csv" && !csvFile) return setError("Choose a CSV file first.");
    if (mode === "manual" && holdings.length === 0) return setError("Add at least one holding with a ticker and a share count.");

    setSubmitting(true);
    try {
      const portfolio = await createPortfolio(name.trim() || "My portfolio", benchmark.trim().toUpperCase() || "SPY");
      if (mode === "csv") await addHoldingsCsv(portfolio.id, csvFile);
      else await addHoldings(portfolio.id, holdings);
      onReady(portfolio.id);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Couldn't create the portfolio. Try again.");
      setSubmitting(false);
    }
  };

  const hasSaved = saved && saved.length > 0;

  return (
    <div className="min-h-screen">
      <TopBar>
        <button onClick={onLogout} className="btn-quiet py-1.5">
          Log out
        </button>
      </TopBar>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <div className={hasSaved ? "grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]" : "max-w-2xl"}>
          {hasSaved && (
            <section aria-labelledby="saved-heading">
              <h1 id="saved-heading" className="text-2xl font-semibold tracking-tight">
                Your portfolios
              </h1>
              <ul className="mt-6 panel divide-y divide-rule-soft">
                {saved.map((p) => (
                  <li key={p.id} className="flex items-center gap-3 px-4 py-3">
                    <button onClick={() => onReady(p.id)} className="flex-1 min-w-0 text-left group">
                      <span className="block font-medium text-ink truncate group-hover:text-data">{p.name}</span>
                      <span className="block text-xs text-muted mt-0.5">
                        {p.holdings} {p.holdings === 1 ? "holding" : "holdings"}, compared with {p.benchmark}
                      </span>
                    </button>
                    <button
                      onClick={() => removeSaved(p)}
                      className="text-xs text-muted-faint hover:text-loss px-2 py-1 rounded"
                      aria-label={`Delete ${p.name}`}
                    >
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section aria-labelledby="new-heading">
            <div className="flex items-end justify-between gap-4 flex-wrap">
              <div>
                <h2 id="new-heading" className={`${hasSaved ? "text-lg" : "text-2xl"} font-semibold tracking-tight`}>
                  {hasSaved ? "Analyze another portfolio" : "Analyze a portfolio"}
                </h2>
                <p className="text-sm text-muted mt-1">Enter what you hold. Prices come from market history.</p>
              </div>
              <button type="button" onClick={useExample} className="btn-quiet py-1.5">
                Fill in an example
              </button>
            </div>

            <form onSubmit={submit} className="mt-6 panel p-5 sm:p-6 space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-[1fr_9rem] gap-4">
                <label className="field-label">
                  Name
                  <input value={name} onChange={(e) => setName(e.target.value)} className="field" />
                </label>
                <label className="field-label">
                  Compare with
                  <input
                    value={benchmark}
                    onChange={(e) => setBenchmark(e.target.value)}
                    className="field uppercase"
                    aria-describedby="benchmark-help"
                  />
                </label>
              </div>
              <p id="benchmark-help" className="-mt-3 text-xs text-muted">
                The benchmark is used for beta and the performance comparison. SPY tracks the S&amp;P 500.
              </p>

              <div className="seg" role="group" aria-label="How to add holdings">
                <button type="button" aria-pressed={mode === "manual"} className="seg-item" onClick={() => setMode("manual")}>
                  Type them in
                </button>
                <button type="button" aria-pressed={mode === "csv"} className="seg-item" onClick={() => setMode("csv")}>
                  Upload a CSV
                </button>
              </div>

              {mode === "manual" ? (
                <div>
                  <div className="grid grid-cols-[1fr_8rem_2rem] gap-2 text-xs font-medium text-muted pb-1.5">
                    <span>Ticker</span>
                    <span>Shares</span>
                    <span />
                  </div>
                  <div className="space-y-2">
                    {rows.map((row, i) => (
                      <div key={i} className="grid grid-cols-[1fr_8rem_2rem] gap-2 items-center">
                        <input
                          aria-label={`Ticker ${i + 1}`}
                          placeholder={i === 0 ? "AAPL" : ""}
                          value={row.ticker}
                          onChange={(e) => updateRow(i, "ticker", e.target.value)}
                          className="field uppercase"
                        />
                        <input
                          aria-label={`Shares ${i + 1}`}
                          placeholder={i === 0 ? "10" : ""}
                          type="number"
                          step="any"
                          min="0"
                          value={row.shares}
                          onChange={(e) => updateRow(i, "shares", e.target.value)}
                          className="field tabular-nums"
                        />
                        <button
                          type="button"
                          onClick={() => removeRow(i)}
                          className="h-9 w-8 grid place-items-center rounded text-muted-faint hover:text-loss hover:bg-paper"
                          aria-label={`Remove row ${i + 1}`}
                        >
                          <svg viewBox="0 0 12 12" className="h-3 w-3" stroke="currentColor" strokeWidth="1.6">
                            <path d="M2 2l8 8M10 2l-8 8" />
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>
                  <button type="button" onClick={addRow} className="link mt-3 text-sm font-medium">
                    Add a row
                  </button>
                </div>
              ) : (
                <div className="rounded-panel border border-dashed border-rule bg-paper px-4 py-6">
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                    className="text-sm text-ink-soft file:mr-3 file:btn-quiet file:py-1.5"
                  />
                  <p className="text-xs text-muted mt-3">
                    Columns: <code className="text-ink-soft">ticker</code>, <code className="text-ink-soft">shares</code>.
                    Optional: <code className="text-ink-soft">cost_basis</code>, <code className="text-ink-soft">sector</code>.
                  </p>
                </div>
              )}

              {error && (
                <p role="alert" className="error-text">
                  {error}
                </p>
              )}

              <button type="submit" disabled={submitting} className="btn-primary w-full py-2.5">
                {submitting ? "Analyzing…" : "Analyze portfolio"}
              </button>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
}
