"""Tests for the redesigned scoring engine (v2 — six-factor system)."""

import pytest

from app.services.scoring import (
    compute_win_rate_anomaly,
    compute_bet_concentration,
    compute_timing_signal,
    compute_entry_price_edge,
    compute_account_pattern,
    compute_position_size_signal,
    compute_suspicion_score,
    compute_market_timing,
    compute_wallet_freshness,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Win Rate Anomaly (now confidence-weighted)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestWinRateAnomaly:
    def test_zero_resolved(self):
        """0 resolved markets → 0."""
        assert compute_win_rate_anomaly(100.0, 0) == 0.0

    def test_one_resolved_100pct(self):
        """100% with 1 market → 0.2 (1.0 * 1/5 confidence)."""
        score = compute_win_rate_anomaly(100.0, 1)
        assert score == pytest.approx(0.2)

    def test_two_resolved_100pct(self):
        """100% with 2 markets → 0.4 (1.0 * 2/5 confidence)."""
        score = compute_win_rate_anomaly(100.0, 2)
        assert score == pytest.approx(0.4)

    def test_five_resolved_100pct(self):
        """100% with 5 markets → 1.0 (full confidence)."""
        assert compute_win_rate_anomaly(100.0, 5) == 1.0

    def test_50_percent(self):
        """50% win rate = random → 0.0."""
        assert compute_win_rate_anomaly(50.0, 10) == 0.0

    def test_below_50(self):
        """Below average → 0.0."""
        assert compute_win_rate_anomaly(30.0, 10) == 0.0

    def test_80_percent_10_markets(self):
        """80% with 10 markets (full confidence) → 0.6."""
        score = compute_win_rate_anomaly(80.0, 10)
        assert score == pytest.approx(0.6)

    def test_exactly_5_markets(self):
        """Exactly 5 markets = full confidence."""
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
# Timing Signal
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
        assert compute_market_timing(24) == compute_timing_signal(24)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entry Price Edge
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestEntryPriceEdge:
    def test_winner_at_5_cents(self):
        score = compute_entry_price_edge(0.05, won=True)
        assert 0.85 <= score <= 0.95

    def test_winner_at_20_cents(self):
        score = compute_entry_price_edge(0.20, won=True)
        assert 0.55 <= score <= 0.65

    def test_winner_at_50_cents(self):
        assert compute_entry_price_edge(0.50, won=True) == 0.0

    def test_winner_at_90_cents(self):
        assert compute_entry_price_edge(0.90, won=True) == 0.0

    def test_loser(self):
        assert compute_entry_price_edge(0.05, won=False) == 0.0
        assert compute_entry_price_edge(0.50, won=False) == 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Account Pattern (boosted freshness)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAccountPattern:
    def test_perfect_insider_profile(self):
        """Brand-new (1 day), single market, 100% concentrated → very high."""
        score = compute_account_pattern(age_days=1, total_markets_traded=1, concentration=1.0)
        assert score > 0.9

    def test_week_old_account(self):
        """7-day old account, 2 markets, high concentration → still high."""
        score = compute_account_pattern(age_days=7, total_markets_traded=2, concentration=0.9)
        assert score > 0.7

    def test_old_diversified_whale(self):
        """Old, 15 markets, spread out → low score."""
        score = compute_account_pattern(age_days=500, total_markets_traded=15, concentration=0.1)
        assert score < 0.15

    def test_no_age_data(self):
        """Missing age yields score from market count + concentration."""
        score = compute_account_pattern(age_days=None, total_markets_traded=1, concentration=1.0)
        assert score > 0.8

    def test_backward_compat_freshness(self):
        assert compute_wallet_freshness(0) == 1.0
        assert compute_wallet_freshness(365) == 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Position Size Signal (NEW)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPositionSizeSignal:
    def test_below_threshold(self):
        """Below $500 → 0."""
        assert compute_position_size_signal(100.0, 0.15) == 0.0

    def test_high_price_no_signal(self):
        """$10K at 50¢ → 0 (not low-odds)."""
        assert compute_position_size_signal(10000.0, 0.50) == 0.0

    def test_classic_insider(self):
        """$12K at 20¢ → high signal."""
        score = compute_position_size_signal(12000.0, 0.20)
        assert score > 0.3

    def test_extreme_case(self):
        """$50K at 5¢ → very high."""
        score = compute_position_size_signal(50000.0, 0.05)
        assert score > 0.5

    def test_small_low_odds(self):
        """$600 at 10¢ → moderate signal."""
        score = compute_position_size_signal(600.0, 0.10)
        assert score > 0.1

    def test_monotonic_with_size(self):
        """Larger positions → higher scores at same price."""
        s1 = compute_position_size_signal(1000.0, 0.15)
        s2 = compute_position_size_signal(5000.0, 0.15)
        s3 = compute_position_size_signal(20000.0, 0.15)
        assert s1 < s2 < s3


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Aggregate Scoring & Gate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestSuspicionScore:
    def test_all_zeros(self):
        result = compute_suspicion_score(0, 0, 0, 0, 0, 0)
        assert result.score == 0.0
        assert not result.passes_gate

    def test_all_ones(self):
        result = compute_suspicion_score(1, 1, 1, 1, 1, 1)
        assert result.score == 100.0
        assert result.passes_gate

    def test_cap_at_100(self):
        result = compute_suspicion_score(1.5, 1.5, 1.5, 1.5, 1.5, 1.5)
        assert result.score == 100.0

    def test_dicedicedice_pattern(self):
        """
        Simulating Dicedicedice: 2-day old account, 100% win rate on 1 market,
        $12K USDC at $0.20, 100% concentrated, traded ~72h before resolution.
        """
        result = compute_suspicion_score(
            win_rate_anomaly=0.2,     # 100% but only 1 resolved market (confidence 0.2)
            bet_concentration=1.0,    # 100% in one market
            timing_signal=0.35,       # ~72h before resolution
            entry_price_edge=0.6,     # bought at $0.20, won
            account_pattern=0.95,     # 2-day old, 2 markets, 100% concentrated
            position_size_signal=0.5, # $12K on a 20¢ outcome
        )
        # With these factors, the score should be significant
        assert result.score >= 25
        # Should have multiple elevated factors
        assert len(result.elevated_factors) >= 3
        assert "bet_concentration" in result.elevated_factors
        assert "account_pattern" in result.elevated_factors
        assert "position_size_signal" in result.elevated_factors

    def test_normal_trader(self):
        """Normal diversified trader shouldn't trigger."""
        result = compute_suspicion_score(
            win_rate_anomaly=0.1,
            bet_concentration=0.15,
            timing_signal=0.2,
            entry_price_edge=0.0,
            account_pattern=0.1,
            position_size_signal=0.0,
        )
        assert not result.passes_gate
        assert result.score < 15

    def test_single_factor_not_enough(self):
        """One high factor alone shouldn't pass gate."""
        result = compute_suspicion_score(1.0, 0.1, 0.1, 0.1, 0.1, 0.1)
        assert not result.passes_gate

    def test_to_dict(self):
        result = compute_suspicion_score(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        d = result.to_dict()
        assert "score" in d
        assert "passes_gate" in d
        assert "elevated_factors" in d
        assert "win_rate_anomaly" in d
        assert "entry_price_edge" in d
        assert "position_size_signal" in d
