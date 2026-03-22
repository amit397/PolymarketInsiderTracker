import { normalizePercent } from "./whales";

/**
 * Get CSS class for a suspicion score badge.
 */
export function scoreClass(score) {
  if (score >= 80) return "score-critical";
  if (score >= 60) return "score-high";
  if (score >= 40) return "score-medium";
  return "score-low";
}

/**
 * Format a wallet address for display (0x1234...abcd).
 */
export function shortAddr(addr) {
  if (!addr || addr.length < 10) return addr || "—";
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

/**
 * Format a number with commas and optional decimals.
 */
export function formatNum(n, decimals = 0) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Format a dollar amount.
 */
export function formatUSD(n) {
  if (n == null) return "—";
  const absolute = Math.abs(Number(n));
  const prefix = Number(n) < 0 ? "-$" : "$";
  if (absolute >= 1_000_000) return `${prefix}${(absolute / 1_000_000).toFixed(1)}M`;
  if (absolute >= 1_000) return `${prefix}${(absolute / 1_000).toFixed(1)}K`;
  return `${prefix}${absolute.toFixed(2)}`;
}

export function formatPercent(value, decimals = 0) {
  return `${normalizePercent(value).toFixed(decimals)}%`;
}

/**
 * Convert hours to a human-readable countdown string.
 */
export function formatCountdown(hours) {
  if (hours <= 0) return "Expired";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.round(hours)}h`;
  const days = Math.floor(hours / 24);
  const hrs = Math.round(hours % 24);
  return hrs > 0 ? `${days}d ${hrs}h` : `${days}d`;
}

/**
 * Relative time string (e.g., "2m ago", "3h ago").
 */
export function timeAgo(isoString) {
  if (!isoString) return "";
  const diffMs = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

/**
 * Human-readable factor names.
 */
export const FACTOR_LABELS = {
  win_rate_anomaly: "Win Rate Anomaly",
  bet_concentration: "Bet Concentration",
  timing_signal: "Timing Signal",
  entry_price_edge: "Entry Price Edge",
  account_pattern: "Account Pattern",
  position_size_signal: "Position Size Signal",
};

export function FactorCard({ title, weight, desc, accent = "var(--brand-primary)" }) {
  return (
    <div className="panel" style={{ padding: "var(--space-4)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "var(--space-3)" }}>
        <span className="mono" style={{ color: "var(--text-main)", fontWeight: 600, fontSize: "0.9rem" }}>{title}</span>
        <span className="badge" style={{ fontSize: "0.7rem", color: accent, borderColor: accent }}>
          {weight}{String(weight).includes("%") ? " weight" : ""}
        </span>
      </div>
      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", lineHeight: 1.5 }}>
        {desc}
      </div>
    </div>
  );
}
