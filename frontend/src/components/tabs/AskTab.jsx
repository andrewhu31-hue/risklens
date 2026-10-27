import { useEffect, useRef, useState } from "react";
import { askQuestion } from "../../api";

const SUGGESTIONS = [
  "What's my biggest risk right now?",
  "Am I diversified, or do my holdings move together?",
  "How would I have done in a 2008-style crash?",
  "Which single change would lower my volatility most?",
  "Explain my Sharpe ratio in plain terms.",
];

export default function AskTab({ portfolioId }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [messages, loading]);

  const ask = async (text) => {
    const q = text.trim();
    if (!q || loading) return;
    setMessages((m) => [...m, { role: "user", text: q }]);
    setQuestion("");
    setLoading(true);
    setError(null);
    try {
      const res = await askQuestion(portfolioId, q);
      setMessages((m) => [...m, { role: "assistant", text: res.answer }]);
    } catch (err) {
      setError(err?.response?.data?.detail || "Couldn't get an answer. Try again in a moment.");
    } finally {
      setLoading(false);
    }
  };

  const unasked = SUGGESTIONS.filter((s) => !messages.some((m) => m.text === s));

  return (
    <div className="max-w-3xl">
      <h2 className="text-base font-semibold text-ink">Ask about this portfolio</h2>
      <p className="text-sm text-muted mt-1">Answers use this portfolio's computed numbers, not general market talk.</p>

      <div className="mt-6 space-y-5" aria-live="polite">
        {messages.map((m, i) =>
          m.role === "user" ? (
            <p key={i} className="ml-auto w-fit max-w-[85%] rounded-panel bg-ink px-4 py-2.5 text-sm text-white">
              {m.text}
            </p>
          ) : (
            <div key={i} className="panel px-5 py-4">
              <p className="text-[15px] leading-[1.7] text-ink-soft whitespace-pre-line">{m.text}</p>
            </div>
          )
        )}
        {loading && (
          <div className="panel px-5 py-4 text-sm text-muted" aria-busy="true">
            Reading your numbers…
          </div>
        )}
        {error && (
          <p role="alert" className="error-text">
            {error}
          </p>
        )}
        <div ref={endRef} />
      </div>

      {unasked.length > 0 && (
        <div className={`flex flex-wrap gap-2 ${messages.length ? "mt-6" : ""}`}>
          {unasked.slice(0, messages.length ? 3 : 5).map((s) => (
            <button
              key={s}
              type="button"
              disabled={loading}
              onClick={() => ask(s)}
              className="rounded-full border border-rule bg-panel px-3.5 py-1.5 text-sm text-ink-soft hover:border-data hover:text-data disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-data"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
        className="mt-4 flex gap-2"
      >
        <label htmlFor="ask-input" className="sr-only">
          Your question
        </label>
        <input
          id="ask-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Or type your own question"
          className="field flex-1 py-2.5"
        />
        <button type="submit" disabled={loading || !question.trim()} className="btn-primary">
          Ask
        </button>
      </form>
    </div>
  );
}
