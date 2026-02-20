"""
Suspicion-score calculator — Redesigned.

Five-factor formula focused on statistically meaningful insider signals:
  1. Win Rate Anomaly    (30%) — deviation from 50% baseline, requires sample size
  2. Bet Concentration   (20%) — single-market concentration ratio
  3. Timing Signal       (20%) — logarithmic decay proximity to resolution
  4. Entry Price Edge    (15%) — did they buy at extreme undervalued odds?
  5. Account Pattern     (15%) — fresh + single-purpose + low diversification
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.core.config import (
    ALERT_FACTOR_THRESHOLD,
    ALERT_MIN_FACTORS_ABOVE,
    ALERT_MIN_SCORE,
    MARKET_TIMING_MAX_HOURS,
    MIN_RESOLVED_MARKETS,
    WIN_RATE_SIGNIFICANCE,
    SCORING_WEIGHTS,
)


# ---------------------------------------------------------------------------
# Individual factor computations
# ---------------------------------------------------------------------------

def compute_win_rate_anomaly(
    win_rate_pct: float,
    resolved_markets: int,
) -> float:
    """
    How far above the 50% random baseline the wallet's win rate is.

    Returns 0.0 if fewer than MIN_RESOLVED_MARKETS are resolved (insufficient
    sample size to draw conclusions on binary markets).

    For win_rate_pct in [0, 100]:
      - 50% → 0.0
      - 80% → 0.6
      - 100% → 1.0
    """
    if resolved_markets < MIN_RESOLVED_MARKETS:
        return 0.0
    win_rate = win_rate_pct / 100.0  # Convert to 0-1 range
    if win_rate <= 0.5:
        return 0.0
    return min(1.0, (win_rate - 0.5) / 0.5)


def compute_bet_concentration(
    market_volume: float,
    total_wallet_volume: float,
) -> float:
    """
    Single-market concentration ratio.

    Measures what fraction of a wallet's total trading volume is
    concentrated in the market being scored.  An insider wallet is
    typically a single-purpose vehicle with near 100% of volume in
    one market.

    Returns 0.0–1.0  (1.0 = all volume in this market).
    """
    if total_wallet_volume <= 0:
        return 0.0
    return min(1.0, market_volume / total_wallet_volume)


def compute_timing_signal(hours_to_resolution: float) -> float:
    """
    Logarithmic decay that provides meaningful differentiation
    across the 0–720 h range.

    | Hours |  Score |
    |------:|-------:|
    |     1 |  0.95  |
    |     6 |  0.73  |
    |    24 |  0.52  |
    |    48 |  0.41  |
    |    72 |  0.35  |
    |   168 |  0.24  |
    |   720 |  0.00  |
    """
    if hours_to_resolution <= 0:
        return 1.0
    if hours_to_resolution >= MARKET_TIMING_MAX_HOURS:
        return 0.0
    return max(
        0.0,
        1.0 - math.log(hours_to_resolution + 1) / math.log(MARKET_TIMING_MAX_HOURS + 1),
    )


def compute_entry_price_edge(
    avg_entry_price: float,
    won: bool,
) -> float:
    """
    Did the wallet buy at extreme undervalued odds and win?

    An insider buys YES at $0.05 on a market that resolves YES — that's
    a 20x return and a huge edge. Normal traders don't consistently do this.

    For winners who bought below 50¢:
      entry=0.05 → 0.90 (massive edge)
      entry=0.20 → 0.60
      entry=0.40 → 0.20
      entry=0.50 → 0.00
      
    For losers or entries above 50¢: 0.0
    """
    if not won:
        return 0.0
    if avg_entry_price >= 0.50:
        return 0.0
    if avg_entry_price <= 0.0:
        return 1.0
    return min(1.0, (0.50 - avg_entry_price) / 0.50)


def compute_account_pattern(
    age_days: float | None,
    total_markets_traded: int,
    concentration: float,
) -> float:
    """
    Combined account pattern signal: fresh + single-purpose + low diversification.

    Components:
      - Freshness: 0-day wallet → 1.0, 365-day → 0.0
      - Single-purpose: trading ≤ 2 markets → 1.0, ≥ 10 markets → 0.0
      - Concentration: passed through directly (already 0-1)

    Returns average of available components.
    """
    signals = []

    # Freshness score
    if age_days is not None:
        freshness = max(0.0, 1.0 - min(age_days, 365.0) / 365.0)
        signals.append(freshness)

    # Single-purpose score (few markets traded)
    if total_markets_traded <= 2:
        signals.append(1.0)
    elif total_markets_traded >= 10:
        signals.append(0.0)
    else:
        signals.append(1.0 - (total_markets_traded - 2) / 8.0)

    # Concentration (already 0-1 from compute_bet_concentration)
    signals.append(concentration)

    if not signals:
        return 0.0
    return sum(signals) / len(signals)


# ---------------------------------------------------------------------------
# Aggregate scoring
# ---------------------------------------------------------------------------

@dataclass
class ScoringResult:
    """Container for the full breakdown of a suspicion score."""

    win_rate_anomaly: float = 0.0
    bet_concentration: float = 0.0
    timing_signal: float = 0.0
    entry_price_edge: float = 0.0
    account_pattern: float = 0.0

    score: float = 0.0
    passes_gate: bool = False
    elevated_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "win_rate_anomaly": round(self.win_rate_anomaly, 4),
            "bet_concentration": round(self.bet_concentration, 4),
            "timing_signal": round(self.timing_signal, 4),
            "entry_price_edge": round(self.entry_price_edge, 4),
            "account_pattern": round(self.account_pattern, 4),
            "score": round(self.score, 2),
            "passes_gate": self.passes_gate,
            "elevated_factors": self.elevated_factors,
        }


def compute_suspicion_score(
    win_rate_anomaly: float,
    bet_concentration: float,
    timing_signal: float,
    entry_price_edge: float,
    account_pattern: float,
    weights: dict[str, float] | None = None,
) -> ScoringResult:
    """
    Compute the weighted suspicion score and check the alert gate.

    Returns a :class:`ScoringResult` with the full breakdown.
    """
    w = weights or SCORING_WEIGHTS

    raw = (
        w["win_rate_anomaly"] * win_rate_anomaly
        + w["bet_concentration"] * bet_concentration
        + w["timing_signal"] * timing_signal
        + w["entry_price_edge"] * entry_price_edge
        + w["account_pattern"] * account_pattern
    )
    score = min(100.0, max(0.0, raw * 100.0))

    factors = {
        "win_rate_anomaly": win_rate_anomaly,
        "bet_concentration": bet_concentration,
        "timing_signal": timing_signal,
        "entry_price_edge": entry_price_edge,
        "account_pattern": account_pattern,
    }
    elevated = [
        name for name, val in factors.items() if val >= ALERT_FACTOR_THRESHOLD
    ]
    passes = score >= ALERT_MIN_SCORE and len(elevated) >= ALERT_MIN_FACTORS_ABOVE

    return ScoringResult(
        win_rate_anomaly=win_rate_anomaly,
        bet_concentration=bet_concentration,
        timing_signal=timing_signal,
        entry_price_edge=entry_price_edge,
        account_pattern=account_pattern,
        score=score,
        passes_gate=passes,
        elevated_factors=elevated,
    )


# ---------------------------------------------------------------------------
# Legacy compatibility aliases (for any code that still imports old names)
# ---------------------------------------------------------------------------

def compute_market_timing(hours_to_resolution: float) -> float:
    """Alias for compute_timing_signal (backward compat)."""
    return compute_timing_signal(hours_to_resolution)


def compute_topic_concentration(market_volume: float, total_wallet_volume: float) -> float:
    """Alias for compute_bet_concentration (backward compat)."""
    return compute_bet_concentration(market_volume, total_wallet_volume)


def compute_wallet_freshness(age_days: float) -> float:
    """Legacy wallet freshness (subsumed into account_pattern)."""
    return max(0.0, 1.0 - min(age_days, 365.0) / 365.0)
