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
# ---------------------------------------------------------------------------
WEIGHT_WIN_RATE_ANOMALY: float = 0.30
WEIGHT_BET_CONCENTRATION: float = 0.20
WEIGHT_TIMING_SIGNAL: float = 0.20
WEIGHT_ENTRY_PRICE_EDGE: float = 0.15
WEIGHT_ACCOUNT_PATTERN: float = 0.15

SCORING_WEIGHTS: dict[str, float] = {
    "win_rate_anomaly": WEIGHT_WIN_RATE_ANOMALY,
    "bet_concentration": WEIGHT_BET_CONCENTRATION,
    "timing_signal": WEIGHT_TIMING_SIGNAL,
    "entry_price_edge": WEIGHT_ENTRY_PRICE_EDGE,
    "account_pattern": WEIGHT_ACCOUNT_PATTERN,
}

# ---------------------------------------------------------------------------
# Alert thresholds
# ---------------------------------------------------------------------------
ALERT_MIN_SCORE: float = 30.0
ALERT_MIN_FACTORS_ABOVE: int = 2
ALERT_FACTOR_THRESHOLD: float = 0.3

# ---------------------------------------------------------------------------
# Insider detection thresholds
# ---------------------------------------------------------------------------
MIN_RESOLVED_MARKETS: int = 5         # Need ≥5 resolved markets for win rate signal
WIN_RATE_SIGNIFICANCE: float = 0.80   # 80%+ win rate needed to be notable
MIN_POSITION_SIZE: float = 10000.0    # Minimum total position in a single market

# ---------------------------------------------------------------------------
# Market Timing – logarithmic decay
# ---------------------------------------------------------------------------
MARKET_TIMING_MAX_HOURS: float = 720.0  # 30 days – beyond this, N_M = 0

# ---------------------------------------------------------------------------
# Short-dated contract feature
# ---------------------------------------------------------------------------
SHORT_DATED_HOURS_DEFAULT: int = 168       # 7 days
SHORT_DATED_HOURS_OPTIONS: list[int] = [24, 48, 72, 168]
SHORT_DATED_MIN_VOLUME: float = 100.0      # lowered from 1000 per critique

# ---------------------------------------------------------------------------
# HTTP client defaults
# ---------------------------------------------------------------------------
HTTP_TIMEOUT: float = 30.0
HTTP_MAX_RETRIES: int = 3
DATA_API_PAGE_SIZE: int = 100

# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------
SCAN_LOOKBACK_HOURS: int = 24  # default: scan trades from last 24 h
SCAN_INTERVAL_SECONDS: int = 60  # pause between background scan cycles
SCAN_MAX_PAGES: int = 30  # pages per cycle (100 trades/page → 3000 trades)
MIN_TRADE_SIZE: float = 10000.0  # skip trades under $10,000
WALLET_CONCENTRATION_THRESHOLD: float = 0.85  # 85% of volume in one market
