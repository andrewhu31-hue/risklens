import axios from "axios";

const TOKEN_KEY = "risklens_token";
export const SESSION_EXPIRED_EVENT = "risklens:session-expired";

const api = axios.create({
  // Production builds call the API on the same origin under /api (see vercel.json).
  baseURL: import.meta.env.VITE_API_URL || (import.meta.env.PROD ? "/api" : "http://localhost:8000"),
  headers: import.meta.env.VITE_API_KEY ? { "X-API-Key": import.meta.env.VITE_API_KEY } : {},
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // A rejected token: clear it and tell the app, so it returns to the login
    // screen instead of carrying on and sending requests with no token at all.
    // (Wrong-password responses on /auth/* are 401s too, but there's no session to end.)
    const url = error.config?.url || "";
    if (error.response?.status === 401 && !url.startsWith("/auth/")) {
      localStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
    }
    return Promise.reject(error);
  }
);

export const getToken = () => localStorage.getItem(TOKEN_KEY);

export const register = (email, password) =>
  api.post("/auth/register", { email, password }).then((r) => {
    localStorage.setItem(TOKEN_KEY, r.data.access_token);
    return r.data;
  });

export const login = (email, password) =>
  api.post("/auth/login", { email, password }).then((r) => {
    localStorage.setItem(TOKEN_KEY, r.data.access_token);
    return r.data;
  });

export const logout = () => localStorage.removeItem(TOKEN_KEY);

export const createPortfolio = (name, benchmark) =>
  api.post("/portfolios", { name, benchmark }).then((r) => r.data);

export const getPortfolio = (id) => api.get(`/portfolios/${id}`).then((r) => r.data);

export const listPortfolios = () => api.get("/portfolios").then((r) => r.data.portfolios);

export const deletePortfolio = (id) => api.delete(`/portfolios/${id}`).then((r) => r.data);

export const deleteHolding = (id, ticker) =>
  api.delete(`/portfolios/${id}/holdings/${encodeURIComponent(ticker)}`).then((r) => r.data);

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

export const getPerformance = (id) => api.get(`/portfolios/${id}/performance`).then((r) => r.data);

export const getStress = (id) => api.get(`/portfolios/${id}/stress`).then((r) => r.data);

export const askQuestion = (id, question) =>
  api.post(`/portfolios/${id}/ask`, { question }).then((r) => r.data);

export default api;
