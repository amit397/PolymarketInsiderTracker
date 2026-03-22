export const WATCHLIST_STORAGE_KEY = "polymarket-insider-watchlist:v1";

export function readWatchlist(storage = globalThis?.localStorage) {
  try {
    const raw = storage?.getItem?.(WATCHLIST_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((value) => typeof value === "string")
      : [];
  } catch {
    return [];
  }
}

export function writeWatchlist(addresses, storage = globalThis?.localStorage) {
  const deduped = [...new Set(addresses.map((value) => value.toLowerCase()))];
  storage?.setItem?.(WATCHLIST_STORAGE_KEY, JSON.stringify(deduped));
  return deduped;
}

export function toggleWatchlist(address, storage = globalThis?.localStorage) {
  const normalized = address.toLowerCase();
  const current = readWatchlist(storage);
  return current.includes(normalized)
    ? writeWatchlist(current.filter((value) => value !== normalized), storage)
    : writeWatchlist([...current, normalized], storage);
}

export function createMemoryStorage(initial = {}) {
  const state = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return state.has(key) ? state.get(key) : null;
    },
    setItem(key, value) {
      state.set(key, String(value));
    },
    removeItem(key) {
      state.delete(key);
    },
  };
}
