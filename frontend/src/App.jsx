import { useState } from "react";
import { getToken, logout } from "./api";
import Dashboard from "./pages/Dashboard.jsx";
import Login from "./pages/Login.jsx";
import Upload from "./pages/Upload.jsx";

const PORTFOLIO_KEY = "risklens_portfolio";

export default function App() {
  const [authed, setAuthed] = useState(() => Boolean(getToken()));
  const [portfolioId, setPortfolioIdState] = useState(() => {
    try {
      return localStorage.getItem(PORTFOLIO_KEY);
    } catch {
      return null;
    }
  });

  // Remember the open portfolio so a page refresh doesn't lose it.
  const setPortfolioId = (id) => {
    setPortfolioIdState(id);
    try {
      if (id) localStorage.setItem(PORTFOLIO_KEY, id);
      else localStorage.removeItem(PORTFOLIO_KEY);
    } catch {
      /* storage unavailable */
    }
  };

  if (!authed) {
    return <Login onAuthenticated={() => setAuthed(true)} />;
  }

  const handleLogout = () => {
    logout();
    setPortfolioId(null);
    setAuthed(false);
  };

  if (!portfolioId) {
    return <Upload onReady={setPortfolioId} onLogout={handleLogout} />;
  }

  return (
    <Dashboard portfolioId={portfolioId} onReset={() => setPortfolioId(null)} onLogout={handleLogout} />
  );
}
