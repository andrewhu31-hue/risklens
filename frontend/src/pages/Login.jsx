import { useState } from "react";
import { login, register } from "../api";

export default function Login({ onAuthenticated }) {
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
      setError(err?.response?.data?.detail || "Something went wrong");
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-24">
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold text-slate-100">RiskLens</h1>
        <p className="text-slate-400 mt-2">
          {mode === "login" ? "Log in to your portfolios" : "Create an account"}
        </p>
      </div>

      <form onSubmit={submit} className="glass-card p-6 space-y-4">
        <div className="flex gap-2 text-sm">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`px-3 py-1.5 rounded-lg border ${
              mode === "login" ? "border-sky-400 text-sky-300" : "border-white/10 text-slate-400"
            }`}
          >
            Log in
          </button>
          <button
            type="button"
            onClick={() => setMode("register")}
            className={`px-3 py-1.5 rounded-lg border ${
              mode === "register" ? "border-sky-400 text-sky-300" : "border-white/10 text-slate-400"
            }`}
          >
            Register
          </button>
        </div>

        <label className="flex flex-col gap-1 text-sm text-slate-300">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="glass-card px-3 py-2 bg-transparent outline-none focus:border-sky-400/50"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-300">
          Password
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="glass-card px-3 py-2 bg-transparent outline-none focus:border-sky-400/50"
          />
          {mode === "register" && <span className="text-xs text-slate-500">At least 8 characters</span>}
        </label>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-medium transition-colors"
        >
          {submitting ? "..." : mode === "login" ? "Log in" : "Create account"}
        </button>
      </form>
    </div>
  );
}
