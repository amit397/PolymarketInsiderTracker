"""Test Data API limits and per-market filtering."""
import httpx
import json

# How many pages can we fetch?
print("=== Pagination limits ===")
for offset in [1000, 2000, 3000]:
    r = httpx.get("https://data-api.polymarket.com/trades",
        params={"limit": 100, "offset": offset}, timeout=10)
    if r.status_code != 200:
        print(f"  Offset {offset}: HTTP {r.status_code} (limit)")
        break
    data = r.json()
    if data:
        oldest = data[-1].get("timestamp", "?")
        print(f"  Offset {offset}: {len(data)} trades, oldest_ts={oldest}")
    else:
        print(f"  Offset {offset}: empty")
        break

# What conditionIds appear in the global feed? Count unique markets
print("\n=== Market diversity in global feed ===")
all_trades = []
for offset in range(0, 2000, 100):
    r = httpx.get("https://data-api.polymarket.com/trades",
        params={"limit": 100, "offset": offset}, timeout=10)
    if r.status_code != 200:
        break
    batch = r.json()
    if not batch:
        break
    all_trades.extend(batch)
    if len(batch) < 100:
        break

print(f"Total trades fetched: {len(all_trades)}")

# Count unique conditionIds (markets)
cids = set(t.get("conditionId", "") for t in all_trades)
print(f"Unique conditionIds (markets): {len(cids)}")

# Count unique wallets
wallets = set(t.get("proxyWallet", "") for t in all_trades)
print(f"Unique wallets: {len(wallets)}")

# Show top markets by trade count
from collections import Counter
market_counts = Counter(t.get("slug", "unknown") for t in all_trades)
print(f"\n=== Top 10 markets by trade count ===")
for slug, cnt in market_counts.most_common(10):
    print(f"  {cnt:4d} trades | {slug[:60]}")

# Classify the non-crypto ones
from app.services.market_classifier import classify_market
print(f"\n=== Event-based markets (non-crypto/sports/entertainment) ===")
event_slugs = {}
for t in all_trades:
    slug = t.get("slug", "")
    title = t.get("title", "")
    cls = classify_market(slug, title)
    if cls.should_scan:
        if slug not in event_slugs:
            event_slugs[slug] = {"title": title, "count": 0, "wallets": set()}
        event_slugs[slug]["count"] += 1
        event_slugs[slug]["wallets"].add(t.get("proxyWallet", ""))

for slug, info in sorted(event_slugs.items(), key=lambda x: -x[1]["count"])[:15]:
    print(f"  {info['count']:4d} trades, {len(info['wallets']):3d} wallets | {info['title'][:70]}")
