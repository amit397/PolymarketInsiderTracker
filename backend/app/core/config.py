"""Application settings and configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "insider_tracker.db"

# ---------------------------------------------------------------------------
# External API base URLs
# ---------------------------------------------------------------------------
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
POLYGONSCAN_API_BASE = "https://api.polygonscan.com/api"

# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------
POLYGONSCAN_API_KEY: str = os.getenv("POLYGONSCAN_API_KEY", "")

# ---------------------------------------------------------------------------
# Scoring weights  (must sum to 1.0)
#
# Reweighted to heavily emphasise the "new account + large low-odds bet"
# pattern that is the #1 insider signal.
# ---------------------------------------------------------------------------
WEIGHT_WIN_RATE_ANOMALY: float = 0.15       # reduced — small sample size for fresh insiders
WEIGHT_BET_CONCENTRATION: float = 0.15
WEIGHT_TIMING_SIGNAL: float = 0.10
WEIGHT_ENTRY_PRICE_EDGE: float = 0.15
WEIGHT_ACCOUNT_PATTERN: float = 0.20        # boosted — fresh accounts are key signal
WEIGHT_POSITION_SIZE_SIGNAL: float = 0.25   # NEW — large $ on low-odds outcomes

SCORING_WEIGHTS: dict[str, float] = {
    "win_rate_anomaly": WEIGHT_WIN_RATE_ANOMALY,
    "bet_concentration": WEIGHT_BET_CONCENTRATION,
    "timing_signal": WEIGHT_TIMING_SIGNAL,
    "entry_price_edge": WEIGHT_ENTRY_PRICE_EDGE,
    "account_pattern": WEIGHT_ACCOUNT_PATTERN,
    "position_size_signal": WEIGHT_POSITION_SIZE_SIGNAL,
}

# ---------------------------------------------------------------------------
# Alert thresholds
# ---------------------------------------------------------------------------
ALERT_MIN_SCORE: float = 25.0              # lowered from 30 — catch more candidates
ALERT_MIN_FACTORS_ABOVE: int = 2
ALERT_FACTOR_THRESHOLD: float = 0.3

# ---------------------------------------------------------------------------
# Insider detection thresholds
# ---------------------------------------------------------------------------
MIN_RESOLVED_MARKETS: int = 1              # was 5 — fresh insiders have ≤2
WIN_RATE_SIGNIFICANCE: float = 0.80
MIN_POSITION_SIZE: float = 500.0           # was 10K — USDC dollars now, not shares

# ---------------------------------------------------------------------------
# Market Timing – logarithmic decay
# ---------------------------------------------------------------------------
MARKET_TIMING_MAX_HOURS: float = 720.0

# ---------------------------------------------------------------------------
# Fresh account thresholds (boosted signal)
# ---------------------------------------------------------------------------
FRESH_ACCOUNT_MAX_DAYS: int = 30           # accounts < 30 days old get extra scrutiny
FRESH_ACCOUNT_FULL_SIGNAL_DAYS: int = 7    # accounts < 7 days old get maximum signal

# ---------------------------------------------------------------------------
# Position-size signal (NEW)
# ---------------------------------------------------------------------------
POSITION_SIZE_SUSPICIOUS_THRESHOLD: float = 500.0   # $500+ USDC in one market
POSITION_SIZE_HIGH_THRESHOLD: float = 5000.0         # $5K+ gets near-max score
LOW_ODDS_PRICE_THRESHOLD: float = 0.35               # buying below 35¢ = low odds

# ---------------------------------------------------------------------------
# Short-dated contract feature
# ---------------------------------------------------------------------------
SHORT_DATED_HOURS_DEFAULT: int = 168
SHORT_DATED_HOURS_OPTIONS: list[int] = [24, 48, 72, 168]
SHORT_DATED_MIN_VOLUME: float = 100.0

# ---------------------------------------------------------------------------
# HTTP client defaults
# ---------------------------------------------------------------------------
HTTP_TIMEOUT: float = 30.0
HTTP_MAX_RETRIES: int = 3
DATA_API_PAGE_SIZE: int = 100

# ---------------------------------------------------------------------------
# Scanner — Market-first scanning
# ---------------------------------------------------------------------------
SCAN_LOOKBACK_HOURS: int = 24
SCAN_INTERVAL_SECONDS: int = 60
SCAN_MAX_PAGES: int = 50                   # pages per market trade fetch
MIN_TRADE_SIZE: float = 50.0               # lowered from 10K (USDC, not shares)

# Market-first discovery settings
SCAN_MARKET_HOURS_AHEAD: int = 720         # scan markets resolving within 30 days
SCAN_MARKET_MIN_VOLUME: float = 1000.0     # skip tiny markets
SCAN_MARKET_MAX_PAGES: int = 50            # max pages per market

WALLET_CONCENTRATION_THRESHOLD: float = 0.85
