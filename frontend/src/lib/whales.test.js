import test from "node:test";
import assert from "node:assert/strict";
import { normalizePercent, sortWhales } from "./whales.js";

test("normalizePercent supports fractions and percentages", () => {
  assert.equal(normalizePercent(0.62), 62);
  assert.equal(normalizePercent(62), 62);
});

test("sortWhales sorts descending by the selected metric", () => {
  const whales = [
    { address: "0xbbb", win_rate: 55, followability_score: 40, total_profit: 1000, total_volume: 5000, resolved_markets_count: 2, risk_score: 10 },
    { address: "0xaaa", win_rate: 72, followability_score: 90, total_profit: 4000, total_volume: 15000, resolved_markets_count: 8, risk_score: 12 },
  ];

  const result = sortWhales(whales, { key: "followability_score", direction: "desc" });
  assert.equal(result[0].address, "0xaaa");
});

test("sortWhales can prioritize followed wallets", () => {
  const whales = [
    { address: "0xbbb", win_rate: 55, followability_score: 40 },
    { address: "0xaaa", win_rate: 72, followability_score: 90 },
  ];

  const result = sortWhales(whales, { key: "followed", direction: "desc" }, new Set(["0xbbb"]));
  assert.equal(result[0].address, "0xbbb");
});
