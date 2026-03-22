import test from "node:test";
import assert from "node:assert/strict";
import { createMemoryStorage, readWatchlist, toggleWatchlist } from "./watchlist.js";

test("toggleWatchlist stores lowercase addresses", () => {
  const storage = createMemoryStorage();
  const result = toggleWatchlist("0xABC", storage);
  assert.deepEqual(result, ["0xabc"]);
  assert.deepEqual(readWatchlist(storage), ["0xabc"]);
});

test("toggleWatchlist removes an address when toggled twice", () => {
  const storage = createMemoryStorage();
  toggleWatchlist("0xabc", storage);
  const result = toggleWatchlist("0xabc", storage);
  assert.deepEqual(result, []);
});
