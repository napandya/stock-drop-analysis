// Thin API client for the FastAPI backend. Same-origin in production (FastAPI
// serves the built bundle); proxied to :8000 by Vite during `npm run dev`.
const API = "/api";

export async function getJSON(path) {
  const res = await fetch(`${API}${path}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(body.detail || res.statusText);
    err.kind = body.error || `HTTP ${res.status}`;
    err.status = res.status;
    throw err;
  }
  return body;
}

export const getHealth = () => getJSON("/health");
export const getSections = () => getJSON("/sections");
export const analyzeSection = (key) => getJSON(`/analyze/${key}`);
export const analyzeAll = () => getJSON("/analyze");
