import { useState } from "react";
import { addHoldings, addHoldingsCsv, createPortfolio } from "../api";

const emptyRow = () => ({ ticker: "", shares: "" });

export default function Upload({ onReady, onLogout }) {
  const [name, setName] = useState("My Portfolio");
  const [benchmark, setBenchmark] = useState("SPY");
  const [rows, setRows] = useState([emptyRow(), emptyRow(), emptyRow()]);
  const [csvFile, setCsvFile] = useState(null);
  const [mode, setMode] = useState("manual");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const updateRow = (i, field, value) => {
    setRows((r) => r.map((row, idx) => (idx === i ? { ...row, [field]: value } : row)));
  };

  const addRow = () => setRows((r) => [...r, emptyRow()]);
  const removeRow = (i) => setRows((r) => r.filter((_, idx) => idx !== i));

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const portfolio = await createPortfolio(
        name.trim() || "My Portfolio",
        benchmark.trim().toUpperCase() || "SPY"
      );

      if (mode === "csv") {
        if (!csvFile) throw new Error("Choose a CSV file first");
        await addHoldingsCsv(portfolio.id, csvFile);
      } else {
        const holdings = rows
          .filter((r) => r.ticker.trim() && r.shares)
          .map((r) => ({ ticker: r.ticker.trim().toUpperCase(), shares: parseFloat(r.shares) }));
        if (holdings.length === 0) throw new Error("Add at least one holding");
        await addHoldings(portfolio.id, holdings);
      }

      onReady(portfolio.id);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Something went wrong");
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-16">
      <div className="flex justify-end">
        <button onClick={onLogout} className="text-sm text-slate-500 hover:text-slate-300">
          Log out
        </button>
      </div>
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold text-slate-100">RiskLens</h1>
        <p className="text-slate-400 mt-2">
          Portfolio risk &amp; factor analysis — covariance, PCA, VaR, and AI-grounded review.
        </p>
      </div>

      <form onSubmit={submit} className="glass-card p-6 space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <label className="flex flex-col gap-1 text-sm text-slate-300">
            Portfolio name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="glass-card px-3 py-2 bg-transparent outline-none focus:border-sky-400/50"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-slate-300">
            Benchmark
            <input
              value={benchmark}
              onChange={(e) => setBenchmark(e.target.value)}
              className="glass-card px-3 py-2 bg-transparent outline-none focus:border-sky-400/50"
            />
          </label>
        </div>

        <div className="flex gap-2 text-sm">
          <button
            type="button"
            onClick={() => setMode("manual")}
            className={`px-3 py-1.5 rounded-lg border ${
              mode === "manual" ? "border-sky-400 text-sky-300" : "border-white/10 text-slate-400"
            }`}
          >
            Manual entry
          </button>
          <button
            type="button"
            onClick={() => setMode("csv")}
            className={`px-3 py-1.5 rounded-lg border ${
              mode === "csv" ? "border-sky-400 text-sky-300" : "border-white/10 text-slate-400"
            }`}
          >
            Upload CSV
          </button>
        </div>

        {mode === "manual" ? (
          <div className="space-y-2">
            {rows.map((row, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input
                  placeholder="Ticker (e.g. AAPL)"
                  value={row.ticker}
                  onChange={(e) => updateRow(i, "ticker", e.target.value)}
                  className="glass-card px-3 py-2 text-sm bg-transparent outline-none flex-1 focus:border-sky-400/50"
                />
                <input
                  placeholder="Shares"
                  type="number"
                  step="any"
                  value={row.shares}
                  onChange={(e) => updateRow(i, "shares", e.target.value)}
                  className="glass-card px-3 py-2 text-sm bg-transparent outline-none w-28 focus:border-sky-400/50"
                />
                <button type="button" onClick={() => removeRow(i)} className="text-slate-500 hover:text-red-400 px-2">
                  ✕
                </button>
              </div>
            ))}
            <button type="button" onClick={addRow} className="text-sm text-sky-400 hover:text-sky-300">
              + Add holding
            </button>
          </div>
        ) : (
          <div>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
              className="text-sm text-slate-300"
            />
            <p className="text-xs text-slate-500 mt-2">CSV columns: ticker, shares (optional: cost_basis, sector)</p>
          </div>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-medium transition-colors"
        >
          {submitting ? "Creating…" : "Analyze Portfolio"}
        </button>
      </form>
    </div>
  );
}
