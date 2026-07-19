import { useState } from "react";
import { askQuestion } from "../../api";
import SectionHeader from "../ui/SectionHeader.jsx";

export default function AskTab({ portfolioId }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    const q = question.trim();
    setMessages((m) => [...m, { role: "user", text: q }]);
    setQuestion("");
    setLoading(true);
    setError(null);
    try {
      const res = await askQuestion(portfolioId, q);
      setMessages((m) => [...m, { role: "assistant", text: res.answer }]);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to get an answer");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <SectionHeader title="Ask the AI" subtitle="Answers are grounded in this portfolio's actual computed stats" />
      <div className="glass-card p-5 min-h-[300px] flex flex-col gap-4">
        {messages.length === 0 && (
          <p className="text-sm text-slate-500">
            Try: "What's my biggest risk?" or "Am I too concentrated in one factor?"
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`text-sm ${m.role === "user" ? "text-slate-200" : "text-sky-300"}`}>
            <span className="text-xs uppercase tracking-wide text-slate-500 block mb-1">
              {m.role === "user" ? "You" : "RiskLens AI"}
            </span>
            <p className="whitespace-pre-line leading-relaxed">{m.text}</p>
          </div>
        ))}
        {loading && <p className="text-sm text-slate-500">Thinking…</p>}
        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your portfolio's risk..."
          className="flex-1 glass-card px-4 py-2 text-sm bg-transparent outline-none focus:border-sky-400/50"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 text-sm rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-medium"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
