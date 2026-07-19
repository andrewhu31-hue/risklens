import { useState } from "react";
import Dashboard from "./pages/Dashboard.jsx";
import Upload from "./pages/Upload.jsx";

export default function App() {
  const [portfolioId, setPortfolioId] = useState(null);

  if (!portfolioId) {
    return <Upload onReady={setPortfolioId} />;
  }

  return <Dashboard portfolioId={portfolioId} onReset={() => setPortfolioId(null)} />;
}
