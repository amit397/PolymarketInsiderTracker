"""Helpers for score explanations and wallet presentation metadata."""

from __future__ import annotations

from app.core.config import SCORING_WEIGHTS

FACTOR_LABELS: dict[str, str] = {
    "win_rate_anomaly": "Win-rate anomaly",
    "bet_concentration": "Bet concentration",
    "timing_signal": "Timing signal",
    "entry_price_edge": "Entry-price edge",
    "account_pattern": "Account pattern",
    "position_size_signal": "Position-size signal",
}

FACTOR_REASONS: dict[str, str] = {
    "win_rate_anomaly": "unusually strong outcomes on resolved markets",
    "bet_concentration": "capital clustered into a narrow set of markets",
    "timing_signal": "entries landed unusually close to resolution",
    "entry_price_edge": "entries captured unusually favorable odds",
    "account_pattern": "behavior resembles a fresh, single-purpose account",
    "position_size_signal": "large low-odds position size stands out",
}


def score_label(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 35:
        return "elevated"
    return "low"



def top_factor_names(factors: dict[str, float], limit: int = 3) -> list[str]:
    sortable = [
        (name, float(value or 0), SCORING_WEIGHTS.get(name, 0))
        for name, value in factors.items()
        if name in FACTOR_LABELS and name != "score" and name != "passes_gate"
    ]
    sortable.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return [FACTOR_LABELS[name] for name, value, _ in sortable[:limit] if value > 0]



def why_flagged(factors: dict[str, float], age_days: float | None = None) -> list[str]:
    sortable = [
        (name, float(value or 0), SCORING_WEIGHTS.get(name, 0))
        for name, value in factors.items()
        if name in FACTOR_LABELS
    ]
    sortable.sort(key=lambda item: (item[1], item[2]), reverse=True)

    reasons: list[str] = []
    for name, value, _ in sortable:
        if value < 0.3:
            continue
        reasons.append(FACTOR_REASONS[name])
        if len(reasons) >= 3:
            break

    if age_days is not None:
        if age_days <= 7:
            reasons.insert(0, "wallet is less than a week old")
        elif age_days <= 30:
            reasons.insert(0, "wallet is still relatively new")
        elif age_days >= 365 and reasons:
            reasons.append("old-wallet filter reduced insider confidence")

    # Preserve order while removing duplicates.
    deduped: list[str] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    return deduped[:4]



def followability_score(
    *,
    win_rate: float,
    total_profit: float,
    total_volume: float,
    risk_score_value: float,
    resolved_markets_count: int,
) -> float:
    """Composite score for ranking whales for a follow-trader experience."""
    win_component = min(100.0, max(0.0, win_rate)) * 0.35
    profit_component = min(100.0, max(0.0, total_profit) / 1000.0) * 0.25
    volume_component = min(100.0, max(0.0, total_volume) / 2000.0) * 0.2
    sample_component = min(100.0, max(0, resolved_markets_count) * 10.0) * 0.1
    risk_component = max(0.0, 100.0 - risk_score_value) * 0.1
    return round(win_component + profit_component + volume_component + sample_component + risk_component, 2)
