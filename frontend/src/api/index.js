import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  headers: import.meta.env.VITE_API_KEY ? { "X-API-Key": import.meta.env.VITE_API_KEY } : {},
});

export const createPortfolio = (name, benchmark) =>
  api.post("/portfolios", { name, benchmark }).then((r) => r.data);

export const getPortfolio = (id) => api.get(`/portfolios/${id}`).then((r) => r.data);

export const addHoldings = (id, holdings) =>
  api.post(`/portfolios/${id}/holdings`, holdings).then((r) => r.data);

export const addHoldingsCsv = (id, file) => {
  const form = new FormData();
  form.append("file", file);
  return api
    .post(`/portfolios/${id}/holdings/csv`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
};

export const refreshPortfolio = (id) => api.post(`/portfolios/${id}/refresh`).then((r) => r.data);

export const getRisk = (id) => api.get(`/portfolios/${id}/risk`).then((r) => r.data);

export const getFactors = (id) => api.get(`/portfolios/${id}/factors`).then((r) => r.data);

export const getCorrelation = (id) => api.get(`/portfolios/${id}/correlation`).then((r) => r.data);

export const getOptimizer = (id) => api.get(`/portfolios/${id}/optimize`).then((r) => r.data);

export const getStress = (id) => api.get(`/portfolios/${id}/stress`).then((r) => r.data);

export const askQuestion = (id, question) =>
  api.post(`/portfolios/${id}/ask`, { question }).then((r) => r.data);

export default api;
