const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

async function fetchJson(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    throw new Error(`${path}: ${res.status}`);
  }
  return res.json();
}

/**
 * Fetch recent alerts.
 * @param {{ minScore?: number, category?: string, limit?: number }} opts
 */
export async function fetchAlerts({ minScore = 0, category, limit = 50 } = {}) {
  const params = new URLSearchParams({ min_score: String(minScore), limit: String(limit) });
  if (category) params.set("category", category);
  return fetchJson(`/api/alerts?${params}`);
}

export async function fetchInsiders(limit = 100, minScore = 50, category = "") {
  const params = new URLSearchParams({ limit: String(limit), min_score: String(minScore) });
  if (category && category !== "all") {
    params.set("category", category);
  }
  return fetchJson(`/api/insiders?${params}`);
}

export async function fetchWallet(address) {
  return fetchJson(`/api/wallet/${address}`);
}

export async function fetchWalletTrades(address, { limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return fetchJson(`/api/wallet/${address}/trades?${params}`);
}

export async function fetchSuspiciousMarkets({ limit = 20 } = {}) {
  return fetchJson(`/api/markets/suspicious?limit=${limit}`);
}

export async function fetchStats() {
  return fetchJson(`/api/stats`);
}

export async function triggerScan({ lookbackHours = 24 } = {}) {
  return fetchJson(`/api/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lookback_hours: lookbackHours }),
  });
}

export async function fetchWhales({ limit = 50, minVolume = 10000 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), min_volume: String(minVolume) });
  return fetchJson(`/api/whales?${params}`);
}

export async function exportIntelligenceSnapshot() {
  return fetchJson(`/api/intelligence/export`);
}
