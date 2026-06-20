// Thin API client for the FastAPI backend. Same-origin in production (FastAPI
// serves the built bundle); proxied to :8000 by Vite during `npm run dev`.
const API = "/api";

async function request(path, options) {
  const res = await fetch(`${API}${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(body.detail || res.statusText);
    err.kind = body.error || `HTTP ${res.status}`;
    err.status = res.status;
    throw err;
  }
  return body;
}

export const getJSON = (path) => request(path);

export const getHealth = () => getJSON("/health");
export const getSections = () => getJSON("/sections");
export const getTickers = () => getJSON("/tickers");
export const analyzeSection = (key) => getJSON(`/analyze/${key}`);
export const analyzeAll = () => getJSON("/analyze");

export const analyzeSelection = (tickers) =>
  request("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tickers }),
  });
