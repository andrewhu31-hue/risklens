import { useState } from "react";
import { login, register } from "../api";
import { Wordmark } from "../components/ui/TopBar.jsx";

export default function Login({ onAuthenticated, notice }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password);
      }
      onAuthenticated();
    } catch (err) {
      setError(err?.response?.data?.detail || "Couldn't reach the server. Check your connection and try again.");
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1fr_minmax(420px,520px)]">
      <section className="hidden lg:flex flex-col justify-between bg-ink text-white px-12 py-12">
        <Wordmark size="lg" className="text-white" />
        <div className="max-w-md">
          <p className="text-[34px] leading-[1.15] font-semibold tracking-tight">
            See how your holdings behave together, not one at a time.
          </p>
          <p className="mt-5 text-[15px] leading-relaxed text-white/70">
            Volatility, drawdowns, value at risk, hidden factor exposure and how your portfolio would have done in
            2008 and 2020, computed from real price history.
          </p>
        </div>
        <FrontierSketch />
      </section>

      <main className="flex flex-col justify-center px-6 py-16 sm:px-12">
        <div className="w-full max-w-sm mx-auto">
          <div className="lg:hidden mb-10">
            <Wordmark size="lg" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">
            {mode === "login" ? "Log in" : "Create your account"}
          </h1>
          <p className="mt-1.5 text-sm text-muted">
            {mode === "login" ? "Pick up where you left off." : "It takes a few seconds. No card needed."}
          </p>

          {notice && (
            <p role="status" className="mt-6 text-sm text-caution border-l-2 border-caution/40 pl-3">
              {notice}
            </p>
          )}

          <form onSubmit={submit} className="mt-8 space-y-5">
            <label className="field-label">
              Email
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="field"
              />
            </label>

            <label className="field-label">
              Password
              <input
                type="password"
                required
                minLength={8}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field"
              />
              {mode === "register" && <span className="text-xs font-normal text-muted">At least 8 characters</span>}
            </label>

            {error && (
              <p role="alert" className="error-text">
                {error}
              </p>
            )}

            <button type="submit" disabled={submitting} className="btn-primary w-full py-2.5">
              {submitting ? (mode === "login" ? "Logging in…" : "Creating account…") : mode === "login" ? "Log in" : "Create account"}
            </button>
          </form>

          <p className="mt-6 text-sm text-muted">
            {mode === "login" ? "New to RiskLens? " : "Already have an account? "}
            <button
              type="button"
              className="link font-medium"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
            >
              {mode === "login" ? "Create an account" : "Log in"}
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}

// A quiet drawing of an efficient frontier, the curve the optimizer traces.
function FrontierSketch() {
  const pts = Array.from({ length: 13 }, (_, i) => {
    const t = i / 12;
    return [40 + t * 360, 170 - Math.sqrt(t) * 130];
  });
  return (
    <svg viewBox="0 0 440 200" className="w-full max-w-md text-white/25" aria-hidden="true">
      {[50, 100, 150].map((y) => (
        <line key={y} x1="20" x2="430" y1={y} y2={y} stroke="currentColor" strokeWidth="0.6" />
      ))}
      <polyline
        points={pts.map((p) => p.join(",")).join(" ")}
        fill="none"
        stroke="rgba(255,255,255,0.7)"
        strokeWidth="1.5"
      />
      {pts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2.6" fill="#FFFFFF" />
      ))}
      <rect x="196" y="112" width="9" height="9" transform="rotate(45 200.5 116.5)" fill="#E2735F" />
    </svg>
  );
}
