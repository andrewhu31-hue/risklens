import { useState } from "react";
import { getToken, logout } from "./api";
import Dashboard from "./pages/Dashboard.jsx";
import Login from "./pages/Login.jsx";
import Upload from "./pages/Upload.jsx";

export default function App() {
  const [authed, setAuthed] = useState(() => Boolean(getToken()));
  const [portfolioId, setPortfolioId] = useState(null);

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
