"""
Suspicion‑score calculator.

Five‑factor additive formula with logarithmic market‑timing decay,
volume‑anomaly guards, and an alert‑gate check.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.core.config import (
    ALERT_FACTOR_THRESHOLD,
    ALERT_MIN_FACTORS_ABOVE,
    ALERT_MIN_SCORE,
    MARKET_TIMING_MAX_HOURS,
    SCORING_WEIGHTS,
    VOLUME_ANOMALY_MIN_TRADES,
    VOLUME_ANOMALY_SIGMA_FLOOR,
)


# ---------------------------------------------------------------------------
# Individual factor computations
# ---------------------------------------------------------------------------

def compute_volume_anomaly(
    trade_size: float,
    market_mean: float,
    market_std: float,
    market_trade_count: int,
    global_mean: float | None = None,
    global_std: float | None = None,
) -> float:
    """
    N_V: How far *trade_size* is from the market average.

    Falls back to global stats when the market has fewer than
    ``VOLUME_ANOMALY_MIN_TRADES`` trades.  Uses a σ‑floor to
    prevent division‑by‑zero.
    """
    if market_trade_count < VOLUME_ANOMALY_MIN_TRADES:
        if global_mean is not None and global_std is not None:
            mean, std = global_mean, global_std
        else:
            return 0.0
    else:
        mean, std = market_mean, market_std

    std = max(std, VOLUME_ANOMALY_SIGMA_FLOOR)
    z = (trade_size - mean) / (3.0 * std)
    return min(1.0, max(0.0, z))


def compute_topic_concentration(category_shares: dict[str, float]) -> float:
    """
    N_C: Herfindahl–Hirschman Index over the wallet's category
    distribution.  1 category → 1.0, perfectly diversified → ~0.
    """
    if not category_shares:
        return 0.0
    total = sum(category_shares.values())
    if total == 0:
        return 0.0
    return sum((v / total) ** 2 for v in category_shares.values())


def compute_market_timing(hours_to_resolution: float) -> float:
    """
    N_M: Logarithmic decay that provides meaningful differentiation
    across the 0–720 h range.

    | Hours |  N_M |
    |------:|-----:|
    |     1 | 0.95 |
    |     6 | 0.73 |
    |    24 | 0.52 |
    |    48 | 0.41 |
    |    72 | 0.35 |
    |   168 | 0.24 |
    |   720 | 0.00 |
    """
    if hours_to_resolution <= 0:
        return 1.0
    if hours_to_resolution >= MARKET_TIMING_MAX_HOURS:
        return 0.0
    return max(
        0.0,
        1.0 - math.log(hours_to_resolution + 1) / math.log(MARKET_TIMING_MAX_HOURS + 1),
    )


def compute_wallet_freshness(age_days: float) -> float:
    """
    N_F: Fresh wallets score higher.
    0‑day‑old wallet → 1.0 ;  ≥365‑day‑old wallet → 0.0
    """
    return max(0.0, 1.0 - min(age_days, 365.0) / 365.0)


def compute_rapid_profit(
    price_at_entry: float,
    price_after: float,
    side: str,
) -> float:
    """
    N_R: Did the market price move ≥ 20% in the wallet's favor
    within 24 h?

    *side* is ``"BUY"`` or ``"SELL"``.
    """
    if side.upper() == "BUY":
        move = price_after - price_at_entry
    else:
        move = price_at_entry - price_after
    return min(1.0, max(0.0, move / 0.20))


# ---------------------------------------------------------------------------
# Aggregate scoring
# ---------------------------------------------------------------------------

@dataclass
class ScoringResult:
    """Container for the full breakdown of a suspicion score."""

    volume_anomaly: float = 0.0
    topic_concentration: float = 0.0
    market_timing: float = 0.0
    wallet_freshness: float = 0.0
    rapid_profit: float = 0.0

    score: float = 0.0
    passes_gate: bool = False
    elevated_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "volume_anomaly": round(self.volume_anomaly, 4),
            "topic_concentration": round(self.topic_concentration, 4),
            "market_timing": round(self.market_timing, 4),
            "wallet_freshness": round(self.wallet_freshness, 4),
            "rapid_profit": round(self.rapid_profit, 4),
            "score": round(self.score, 2),
            "passes_gate": self.passes_gate,
            "elevated_factors": self.elevated_factors,
        }


def compute_suspicion_score(
    volume_anomaly: float,
    topic_concentration: float,
    market_timing: float,
    wallet_freshness: float,
    rapid_profit: float,
    weights: dict[str, float] | None = None,
) -> ScoringResult:
    """
    Compute the weighted suspicion score and check the alert gate.

    Returns a :class:`ScoringResult` with the full breakdown.
    """
    w = weights or SCORING_WEIGHTS

    raw = (
        w["volume_anomaly"] * volume_anomaly
        + w["topic_concentration"] * topic_concentration
        + w["market_timing"] * market_timing
        + w["wallet_freshness"] * wallet_freshness
        + w["rapid_profit"] * rapid_profit
    )
    score = min(100.0, max(0.0, raw * 100.0))

    factors = {
        "volume_anomaly": volume_anomaly,
        "topic_concentration": topic_concentration,
        "market_timing": market_timing,
        "wallet_freshness": wallet_freshness,
        "rapid_profit": rapid_profit,
    }
    elevated = [
        name for name, val in factors.items() if val >= ALERT_FACTOR_THRESHOLD
    ]
    passes = score >= ALERT_MIN_SCORE and len(elevated) >= ALERT_MIN_FACTORS_ABOVE

    return ScoringResult(
        volume_anomaly=volume_anomaly,
        topic_concentration=topic_concentration,
        market_timing=market_timing,
        wallet_freshness=wallet_freshness,
        rapid_profit=rapid_profit,
        score=score,
        passes_gate=passes,
        elevated_factors=elevated,
    )
