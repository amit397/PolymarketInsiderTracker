"""Tests for the redesigned scoring engine."""

import pytest

from app.services.scoring import (
    compute_win_rate_anomaly,
    compute_bet_concentration,
    compute_timing_signal,
    compute_entry_price_edge,
    compute_account_pattern,
    compute_suspicion_score,
    compute_market_timing,
    compute_wallet_freshness,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Win Rate Anomaly
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestWinRateAnomaly:
    def test_insufficient_sample(self):
        """Below MIN_RESOLVED_MARKETS → 0 regardless of win rate."""
        assert compute_win_rate_anomaly(100.0, 3) == 0.0
        assert compute_win_rate_anomaly(100.0, 4) == 0.0

    def test_50_percent(self):
        """50% win rate = random → 0.0."""
        assert compute_win_rate_anomaly(50.0, 10) == 0.0

    def test_below_50(self):
        """Below average → 0.0."""
        assert compute_win_rate_anomaly(30.0, 10) == 0.0

    def test_80_percent(self):
        """80% with sufficient markets → 0.6."""
        score = compute_win_rate_anomaly(80.0, 10)
        assert score == pytest.approx(0.6)

    def test_100_percent(self):
        """100% → 1.0."""
        assert compute_win_rate_anomaly(100.0, 5) == 1.0

    def test_exactly_5_markets(self):
        """Exactly MIN_RESOLVED_MARKETS should work."""
        score = compute_win_rate_anomaly(90.0, 5)
        assert score > 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bet Concentration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestBetConcentration:
    def test_all_in_one(self):
        assert compute_bet_concentration(5000.0, 5000.0) == 1.0

    def test_half(self):
        assert compute_bet_concentration(2500.0, 5000.0) == 0.5

    def test_low(self):
        assert compute_bet_concentration(500.0, 5000.0) == pytest.approx(0.1)

    def test_zero_total(self):
        assert compute_bet_concentration(100.0, 0.0) == 0.0

    def test_capped(self):
        assert compute_bet_concentration(6000.0, 5000.0) == 1.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Timing Signal (backward compat with market_timing alias)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestTimingSignal:
    def test_zero_hours(self):
        assert compute_timing_signal(0) == 1.0

    def test_negative(self):
        assert compute_timing_signal(-5) == 1.0

    def test_1h(self):
        score = compute_timing_signal(1)
        assert 0.85 <= score <= 0.95

    def test_24h(self):
        score = compute_timing_signal(24)
        assert 0.45 <= score <= 0.58

    def test_48h(self):
        score = compute_timing_signal(48)
        assert 0.35 <= score <= 0.47

    def test_168h(self):
        score = compute_timing_signal(168)
        assert 0.18 <= score <= 0.30

    def test_720h(self):
        assert compute_timing_signal(720) == 0.0

    def test_beyond_max(self):
        assert compute_timing_signal(1000) == 0.0

    def test_monotonic(self):
        hours = [1, 6, 24, 48, 72, 168, 500, 720]
        scores = [compute_timing_signal(h) for h in hours]
        for i in range(len(scores) - 1):
            assert scores[i] > scores[i + 1]

    def test_backward_compat_alias(self):
        """compute_market_timing should be an alias."""
        assert compute_market_timing(24) == compute_timing_signal(24)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entry Price Edge
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestEntryPriceEdge:
    def test_winner_at_5_cents(self):
        """Buying at $0.05 and winning → high edge."""
        score = compute_entry_price_edge(0.05, won=True)
        assert 0.85 <= score <= 0.95

    def test_winner_at_20_cents(self):
        """Buying at $0.20 and winning → moderate edge."""
        score = compute_entry_price_edge(0.20, won=True)
        assert 0.55 <= score <= 0.65

    def test_winner_at_50_cents(self):
        """Buying at $0.50 → no edge (fair price)."""
        assert compute_entry_price_edge(0.50, won=True) == 0.0

    def test_winner_at_90_cents(self):
        """Buying at $0.90 → no edge (overpriced)."""
        assert compute_entry_price_edge(0.90, won=True) == 0.0

    def test_loser(self):
        """Lost → no edge regardless of price."""
        assert compute_entry_price_edge(0.05, won=False) == 0.0
        assert compute_entry_price_edge(0.50, won=False) == 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Account Pattern
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAccountPattern:
    def test_perfect_insider_profile(self):
        """New, single-market, concentrated → high score."""
        score = compute_account_pattern(age_days=1, total_markets_traded=1, concentration=1.0)
        assert score > 0.9

    def test_old_diversified_whale(self):
        """Old, 15 markets, spread out → low score."""
        score = compute_account_pattern(age_days=500, total_markets_traded=15, concentration=0.1)
        assert score < 0.15

    def test_no_age_data(self):
        """Missing age yields score from market count + concentration only."""
        score = compute_account_pattern(age_days=None, total_markets_traded=1, concentration=1.0)
        assert score > 0.8

    def test_backward_compat_freshness(self):
        """compute_wallet_freshness still works."""
        assert compute_wallet_freshness(0) == 1.0
        assert compute_wallet_freshness(365) == 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Aggregate Scoring & Gate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestSuspicionScore:
    def test_all_zeros(self):
        result = compute_suspicion_score(0, 0, 0, 0, 0)
        assert result.score == 0.0
        assert not result.passes_gate

    def test_all_ones(self):
        result = compute_suspicion_score(1, 1, 1, 1, 1)
        assert result.score == 100.0
        assert result.passes_gate

    def test_cap_at_100(self):
        result = compute_suspicion_score(1.5, 1.5, 1.5, 1.5, 1.5)
        assert result.score == 100.0

    def test_typical_insider(self):
        """High win rate + concentrated + good timing + edge + new account."""
        result = compute_suspicion_score(
            win_rate_anomaly=0.8,
            bet_concentration=1.0,
            timing_signal=0.5,
            entry_price_edge=0.6,
            account_pattern=0.9,
        )
        assert result.score >= 60
        assert result.passes_gate
        assert len(result.elevated_factors) >= 3

    def test_single_factor_not_enough(self):
        """One high factor alone shouldn't pass gate."""
        result = compute_suspicion_score(1.0, 0.1, 0.1, 0.1, 0.1)
        assert not result.passes_gate

    def test_to_dict(self):
        result = compute_suspicion_score(0.5, 0.5, 0.5, 0.5, 0.5)
        d = result.to_dict()
        assert "score" in d
        assert "passes_gate" in d
        assert "elevated_factors" in d
        assert "win_rate_anomaly" in d
        assert "entry_price_edge" in d
