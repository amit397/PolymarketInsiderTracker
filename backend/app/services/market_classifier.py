"""
Market classifier — categorises Polymarket markets by slug/title
and decides whether they are candidates for insider-trading detection.

Only *event-based* markets (politics, corporate, regulatory) are
scanned.  Crypto-price, sports, and entertainment markets are skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Skip-patterns  (compiled once at import time)
# ---------------------------------------------------------------------------

# Slug sub-strings that indicate a crypto-price market
_CRYPTO_SLUG_PARTS: list[str] = [
    "btc-updown",
    "bitcoin-up-or-down",
    "eth-updown",
    "ethereum-up-or-down",
    "xrp-updown",
    "xrp-up-or-down",
    "sol-updown",
    "solana-up-or-down",
    "doge-updown",
    "doge-up-or-down",
    "price-of-bitcoin",
    "price-of-ethereum",
    "price-of-solana",
    "price-of-eth",
    "price-of-btc",
    "price-of-xrp",
    "price-of-doge",
    "price-of-bnb",
    "price-of-ada",
    "price-of-dot",
    "price-of-avax",
    "price-of-link",
    "price-of-matic",
    "price-of-sui",
    "crypto-price",
    "btc-price",
    "eth-price",
    "sol-price",
    "xrp-price",
    "bitcoin-above",
    "bitcoin-below",
    "ethereum-above",
    "ethereum-below",
    "solana-above",
    "solana-below",
    "will-bitcoin-reach",
    "will-ethereum-reach",
    "will-solana-reach",
    "will-xrp-reach",
    "will-the-price-of-",
    "bitcoin-dip",
    "ethereum-dip",
]

# Title keywords (case-insensitive) that signal crypto-price markets
_CRYPTO_TITLE_KW: list[str] = [
    "bitcoin up or down",
    "ethereum up or down",
    "btc up or down",
    "xrp up or down",
    "solana up or down",
    "doge up or down",
    "price of bitcoin",
    "price of ethereum",
    "price of solana",
    "price of xrp",
    "price of doge",
    "crypto price",
    "will bitcoin reach",
    "will ethereum reach",
    "will the price of",
    "bitcoin dip",
    "ethereum dip",
]

# Slug sub-strings for sports
_SPORTS_SLUG_PARTS: list[str] = [
    "-la-liga",
    "-champions-league",
    "-premier-league",
    "-serie-a",
    "-bundesliga",
    "-nhl-",
    "-nba-",
    "-nfl-",
    "-mlb-",
    "-mls-",
    "-stanley-cup",
    "-super-bowl",
    "-world-series",
    "-march-madness",
    "-world-cup",
    "-grand-slam",
    "-wimbledon",
    "-us-open",
    "-french-open",
    "-australian-open",
    "-euro-2",    # Euro 2024/2028 etc.
    "-copa-america",
    "-ufc-",
    "-bellator",
    "-mma-",
    "-boxing-",
    "-tennis-",
    "-atp-",
    "-wta-",
    "-golf-",
    "-pga-",
    "-liv-",
    "-cricket-",
    "-rugby-",
    "-hockey-",
    "-baseball-",
    "-total-",    # Over/under totals (sports betting)
]

# Slug prefixes for sports (matched at start of slug)
_SPORTS_SLUG_PREFIXES: list[str] = [
    "cbb-",       # college basketball
    "nba-",
    "nfl-",
    "nhl-",
    "mlb-",
    "mls-",
    "epl-",       # English Premier League
    "ucl-",       # UEFA Champions League
    "f1-",        # Formula 1
]

# Title keywords for sports
_SPORTS_TITLE_KW: list[str] = [
    "win the 20",    # "Will X win the 2025-26 ..."
    "win the nba",
    "win the nfl",
    "make the playoffs",
    "win the world series",
    "win the stanley cup",
    "win the super bowl",
    "red raiders",
    "wolf pack",
    "aztecs",
    "o/u ",
    "over/under",
    "point spread",
    "moneyline",
]

# Regex: team vs team with date (common Polymarket sports format)
_SPORTS_SLUG_RE = re.compile(
    r"^[a-z]+-[a-z]+-\d{4}-\d{2}-\d{2}"  # e.g. "cbb-txtech-arz-2026-02-14"
)

# Entertainment / social-media
_ENTERTAINMENT_SLUG_PARTS: list[str] = [
    "-tweets-",
    "-followers-",
    "-subscribers-",
    "-tiktok-",
    "-youtube-",
    "-of-tweets",
    "-number-of-posts",
]

_ENTERTAINMENT_TITLE_KW: list[str] = [
    "tweets from",
    "number of tweets",
    "followers",
    "subscribers",
]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MarketClassification:
    """Result of classifying a market."""
    category: str          # e.g. "crypto_price", "sports", "politics", "unknown"
    should_scan: bool      # True → eligible for insider detection
    reason: str            # human-readable explanation


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify_market(slug: str, title: str) -> MarketClassification:
    """
    Classify a Polymarket market by its slug and title.

    Returns a classification with:
      - category: one of crypto_price, sports, entertainment, event, unknown
      - should_scan: True if the market is an insider-trading candidate
      - reason: human-readable explanation
    """
    slug_lower = (slug or "").lower()
    title_lower = (title or "").lower()

    # --- Crypto price ---
    for pat in _CRYPTO_SLUG_PARTS:
        if pat in slug_lower:
            return MarketClassification("crypto_price", False, f"Crypto price market (slug: {pat})")
    for kw in _CRYPTO_TITLE_KW:
        if kw in title_lower:
            return MarketClassification("crypto_price", False, f"Crypto price market (title: {kw})")

    # --- Sports ---
    for prefix in _SPORTS_SLUG_PREFIXES:
        if slug_lower.startswith(prefix):
            return MarketClassification("sports", False, f"Sports market (prefix: {prefix})")
    for pat in _SPORTS_SLUG_PARTS:
        if pat in slug_lower:
            return MarketClassification("sports", False, f"Sports market (slug: {pat})")
    if _SPORTS_SLUG_RE.match(slug_lower):
        return MarketClassification("sports", False, "Sports market (team-vs-team pattern)")
    for kw in _SPORTS_TITLE_KW:
        if kw in title_lower:
            return MarketClassification("sports", False, f"Sports market (title: {kw})")

    # --- Entertainment / social ---
    for pat in _ENTERTAINMENT_SLUG_PARTS:
        if pat in slug_lower:
            return MarketClassification("entertainment", False, f"Entertainment market (slug: {pat})")
    for kw in _ENTERTAINMENT_TITLE_KW:
        if kw in title_lower:
            return MarketClassification("entertainment", False, f"Entertainment market (title: {kw})")

    # --- Default: scannable (conservative) ---
    return MarketClassification("event", True, "Event-based market")
