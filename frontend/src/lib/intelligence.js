import { FACTOR_LABELS } from "./utils";

const FACTOR_REASONS = {
  win_rate_anomaly: "unusually strong outcomes",
  bet_concentration: "capital concentrated in one market",
  timing_signal: "late entry close to resolution",
  entry_price_edge: "favorable odds before the crowd",
  account_pattern: "fresh or single-purpose wallet behavior",
  position_size_signal: "large low-odds conviction bet",
};

export function scoreTone(score) {
  if (score >= 75) return "critical";
  if (score >= 55) return "high";
  if (score >= 35) return "elevated";
  return "low";
}

export function explainFactors(factors = {}, limit = 3) {
  return Object.entries(factors)
    .filter(([key, value]) => key in FACTOR_LABELS && Number(value) >= 0.3)
    .sort(([, left], [, right]) => Number(right) - Number(left))
    .slice(0, limit)
    .map(([key]) => FACTOR_REASONS[key] || FACTOR_LABELS[key]);
}
