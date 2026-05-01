/**
 * api/client.js
 * ─────────────
 * Fetch wrapper for the FastAPI backend at /api/*.
 */

const BASE = 'http://localhost:8000';

async function request(path, options = {}) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  // Health
  health: () => request('/api/health'),

  // LiveKit token
  getToken: (room) =>
    request(`/api/token${room ? `?room=${encodeURIComponent(room)}` : ''}`),

  // Conversions
  getConversions: (limit = 20) => request(`/api/conversions?limit=${limit}`),
  getConversion: (id) => request(`/api/conversions/${id}`),

  // Sessions
  getSessions: (limit = 10) => request(`/api/sessions?limit=${limit}`),

  // Stats
  getStats: () => request('/api/stats'),

  // User prefs
  getPrefs: () => request('/api/user/prefs'),
  updatePrefs: (prefs) =>
    request('/api/user/prefs', {
      method: 'PUT',
      body: JSON.stringify(prefs),
    }),

  // Direct translation
  translate: (text, grade = 1) =>
    request('/api/translate', {
      method: 'POST',
      body: JSON.stringify({ text, grade }),
    }),
};
