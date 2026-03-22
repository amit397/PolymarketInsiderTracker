"""
Suspicion-score calculator — Redesigned v2.

Six-factor formula focused on detecting insider trading patterns:
  1. Win Rate Anomaly       (15%) — deviation from 50% baseline, confidence-weighted
  2. Bet Concentration      (15%) — single-market concentration ratio
  3. Timing Signal          (10%) — logarithmic decay proximity to resolution
  4. Entry Price Edge       (15%) — buying at extreme undervalued odds and winning
  5. Account Pattern        (20%) — fresh + single-purpose + low diversification
  6. Position Size Signal   (25%) — NEW: large USDC on low-odds outcomes

The account_pattern and position_size_signal factors together account for 45% of
the score, heavily penalising the classic insider pattern: brand-new account
dumps thousands of dollars on a low-probability geopolitical event.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.core.config import (
    ALERT_FACTOR_THRESHOLD,
    ALERT_MIN_FACTORS_ABOVE,
    ALERT_MIN_SCORE,
    FRESH_ACCOUNT_FULL_SIGNAL_DAYS,
    FRESH_ACCOUNT_MAX_DAYS,
    LOW_ODDS_PRICE_THRESHOLD,
    MARKET_TIMING_MAX_HOURS,
    MIN_RESOLVED_MARKETS,
    POSITION_SIZE_HIGH_THRESHOLD,
    POSITION_SIZE_SUSPICIOUS_THRESHOLD,
    SCORING_WEIGHTS,
    WIN_RATE_SIGNIFICANCE,
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

    Now uses CONFIDENCE WEIGHTING for small sample sizes:
      - 1 resolved market: 20% confidence
      - 3 resolved markets: 60% confidence
      - 5+ resolved markets: 100% confidence

    This means a 100% win rate on 1 market returns 0.20, not 0.0.
    """
    if resolved_markets < 1:
        return 0.0

    # Confidence discount for small sample sizes
    confidence = min(1.0, resolved_markets / 5.0)

    win_rate = win_rate_pct / 100.0
    if win_rate <= 0.5:
        return 0.0

    raw = min(1.0, (win_rate - 0.5) / 0.5)
    return raw * confidence


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

    BOOSTED freshness scoring for very new accounts:
      - < 7 days → 1.0 (maximum suspicion)
      - 7-30 days → 0.5-1.0 (high suspicion)
      - 30-365 days → linear decay to 0.0

    Components:
      - Freshness: weighted 50% of this factor (up from 33%)
      - Single-purpose: trading ≤ 2 markets → 1.0, ≥ 10 markets → 0.0
      - Concentration: passed through directly (already 0-1)
    """
    signals = []
    weights = []

    # Freshness score — boosted weight (50% of this factor)
    if age_days is not None:
        if age_days <= FRESH_ACCOUNT_FULL_SIGNAL_DAYS:
            freshness = 1.0  # Brand-new account = maximum signal
        elif age_days <= FRESH_ACCOUNT_MAX_DAYS:
            # Linear decay from 1.0 to 0.5 over 7-30 day range
            freshness = 1.0 - 0.5 * (
                (age_days - FRESH_ACCOUNT_FULL_SIGNAL_DAYS)
                / (FRESH_ACCOUNT_MAX_DAYS - FRESH_ACCOUNT_FULL_SIGNAL_DAYS)
            )
        else:
            freshness = max(0.0, 1.0 - min(age_days, 365.0) / 365.0)
        signals.append(freshness)
        weights.append(2.0)  # Double weight for freshness
    
    # Single-purpose score (few markets traded)
    if total_markets_traded <= 2:
        signals.append(1.0)
    elif total_markets_traded >= 10:
        signals.append(0.0)
    else:
        signals.append(1.0 - (total_markets_traded - 2) / 8.0)
    weights.append(1.0)

    # Concentration (already 0-1 from compute_bet_concentration)
    signals.append(concentration)
    weights.append(1.0)

    if not signals:
        return 0.0

    return sum(s * w for s, w in zip(signals, weights)) / sum(weights)


def compute_position_size_signal(
    total_usdc_invested: float,
    avg_entry_price: float,
) -> float:
    """
    NEW: Large USD investment at very low prices is a strong insider signal.

    This captures the classic pattern: brand-new account dumps $5K-$50K
    on a 15¢-25¢ outcome that most people think won't happen.

    Combines two sub-signals:
      - Size component: how much USDC (log-scaled)
        $500 → 0.15, $1K → 0.30, $5K → 0.65, $10K → 0.80, $50K → 1.0
      - Low-odds component: how cheap the entry price was
        5¢ → 1.0, 15¢ → 0.57, 25¢ → 0.29, 35¢ → 0.0

    Both must be present: $50K on a 60¢ outcome = 0 (just a big bet).
    $100 on a 5¢ outcome = low (too small to matter).
    $10K on a 15¢ outcome = HIGH (classic insider).
    """
    if total_usdc_invested < POSITION_SIZE_SUSPICIOUS_THRESHOLD:
        return 0.0

    # Size component: log-scaled with clean monotonic increase
    # $500 → ~0.15, $1K → ~0.25, $5K → ~0.55, $10K → ~0.70, $50K → ~0.90, $100K → 1.0
    ratio = total_usdc_invested / POSITION_SIZE_SUSPICIOUS_THRESHOLD  # 1.0 at threshold
    # log2 scaling: ratio=1 → 0.0, ratio=10 → 0.48, ratio=100 → 0.96, ratio=200 → 1.0
    size_score = min(1.0, math.log2(ratio + 1) / math.log2(201))

    # Low-odds component: buying below the threshold price
    if avg_entry_price >= LOW_ODDS_PRICE_THRESHOLD:
        return 0.0  # Not a low-odds bet — doesn't trigger this signal

    price_score = min(
        1.0,
        (LOW_ODDS_PRICE_THRESHOLD - avg_entry_price) / LOW_ODDS_PRICE_THRESHOLD,
    )

    # Combined: both size AND low odds required
    return size_score * 0.6 + price_score * 0.4


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
    position_size_signal: float = 0.0

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
            "position_size_signal": round(self.position_size_signal, 4),
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
    position_size_signal: float = 0.0,
    weights: dict[str, float] | None = None,
) -> ScoringResult:
    """
    Compute the weighted suspicion score and check the alert gate.

    Returns a :class:`ScoringResult` with the full breakdown.
    """
    w = weights or SCORING_WEIGHTS

    raw = (
        w.get("win_rate_anomaly", 0.15) * win_rate_anomaly
        + w.get("bet_concentration", 0.15) * bet_concentration
        + w.get("timing_signal", 0.10) * timing_signal
        + w.get("entry_price_edge", 0.15) * entry_price_edge
        + w.get("account_pattern", 0.20) * account_pattern
        + w.get("position_size_signal", 0.25) * position_size_signal
    )
    score = min(100.0, max(0.0, raw * 100.0))

    factors = {
        "win_rate_anomaly": win_rate_anomaly,
        "bet_concentration": bet_concentration,
        "timing_signal": timing_signal,
        "entry_price_edge": entry_price_edge,
        "account_pattern": account_pattern,
        "position_size_signal": position_size_signal,
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
        position_size_signal=position_size_signal,
        score=score,
        passes_gate=passes,
        elevated_factors=elevated,
    )


def apply_conservative_wallet_age_filter(
    result: ScoringResult,
    age_days: float | None,
) -> tuple[ScoringResult, bool]:
    """Reduce or suppress insider confidence for well-established wallets.

    The goal is conservative false-positive reduction:
    - very old wallets should not be flagged unless the score is already compelling,
    - moderately old wallets are slightly penalized,
    - very fresh wallets are untouched because freshness is already modeled elsewhere.
    """
    if age_days is None or age_days < 90:
        return result, False

    if age_days >= 365 and result.score < 75:
        result.score = round(result.score * 0.7, 2)
        result.passes_gate = False
        return result, True

    if age_days >= 180 and result.score < 60:
        result.score = round(result.score * 0.8, 2)
        result.passes_gate = False
        return result, True

    return result, False


# ---------------------------------------------------------------------------
# Legacy compatibility aliases
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
