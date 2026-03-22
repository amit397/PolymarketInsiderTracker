export const DEFAULT_WHALE_SORT = { key: "followability_score", direction: "desc" };

export function normalizePercent(value) {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return 0;
  return num <= 1 ? num * 100 : num;
}

export function getWhaleMetric(whale, key, followedAddresses = new Set()) {
  switch (key) {
    case "followed":
      return followedAddresses.has(whale.address) ? 1 : 0;
    case "win_rate":
      return normalizePercent(whale.win_rate ?? whale.analysis?.win_rate ?? 0);
    case "total_profit":
    case "total_volume":
    case "risk_score":
    case "followability_score":
    case "resolved_markets_count":
      return Number(whale[key] ?? whale.analysis?.[key] ?? 0);
    default:
      return Number(whale[key] ?? 0);
  }
}

export function sortWhales(whales, sort = DEFAULT_WHALE_SORT, followedAddresses = new Set()) {
  const { key, direction } = sort;
  const multiplier = direction === "asc" ? 1 : -1;
  return [...whales].sort((left, right) => {
    const a = getWhaleMetric(left, key, followedAddresses);
    const b = getWhaleMetric(right, key, followedAddresses);
    if (a !== b) {
      return (a - b) * multiplier;
    }
    return left.address.localeCompare(right.address);
  });
}
