const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

async function parseJsonOrThrow(res, label) {
  if (!res.ok) {
    throw new Error(`${label}: ${res.status}`);
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
  const res = await fetch(`${API_BASE}/api/alerts?${params}`);
  return parseJsonOrThrow(res, "Alerts");
}

/**
 * Fetch recent alerts.
 * @param {{ minScore?: number, category?: string, limit?: number }} opts
 */
export async function fetchInsiders(limit = 100, minScore = 50, category = "") {
  let url = `${API_BASE}/api/insiders?limit=${limit}&min_score=${minScore}`;
  if (category && category !== "all") {
    url += `&category=${category}`;
  }
  const res = await fetch(url, { next: { revalidate: 30 } }); // 30s ISR
  return parseJsonOrThrow(res, "Insiders");
}

/**
 * Fetch wallet profile.
 */
export async function fetchWallet(address) {
  const res = await fetch(`${API_BASE}/api/wallet/${address}`);
  return parseJsonOrThrow(res, "Wallet");
}

/**
 * Fetch wallet trades.
 */
export async function fetchWalletTrades(address, { limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const res = await fetch(`${API_BASE}/api/wallet/${address}/trades?${params}`);
  return parseJsonOrThrow(res, "Trades");
}

/**
 * Fetch suspicious markets.
 */
export async function fetchSuspiciousMarkets({ limit = 20 } = {}) {
  const res = await fetch(`${API_BASE}/api/markets/suspicious?limit=${limit}`);
  return parseJsonOrThrow(res, "Suspicious");
}

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/api/stats`);
  return parseJsonOrThrow(res, "Stats");
}

/**
 * Trigger a manual scan.
 */
export async function triggerScan({ lookbackHours = 24 } = {}) {
  const res = await fetch(`${API_BASE}/api/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lookback_hours: lookbackHours }),
  });
  return parseJsonOrThrow(res, "Scan");
}

/**
 * Fetch high-win-rate whale profiles.
 */
export async function fetchWhales({ limit = 50, minVolume = 10000 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), min_volume: String(minVolume) });
  const res = await fetch(`${API_BASE}/api/whales?${params}`);
  return parseJsonOrThrow(res, "Whales");
}
