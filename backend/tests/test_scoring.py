"""Tests for the scoring engine."""

import math

import pytest

from app.services.scoring import (
    compute_market_timing,
    compute_rapid_profit,
    compute_suspicion_score,
    compute_topic_concentration,
    compute_volume_anomaly,
    compute_wallet_freshness,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# N_V: Volume Anomaly
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestVolumeAnomaly:
    def test_normal_trade(self):
        """A trade at the mean should score 0."""
        score = compute_volume_anomaly(100, 100, 30, 20)
        assert score == 0.0

    def test_large_outlier(self):
        """A trade 3σ above the mean should score 1.0."""
        score = compute_volume_anomaly(190, 100, 30, 20)
        assert score == 1.0

    def test_moderate_outlier(self):
        """A trade 1.5σ above the mean should score ~0.5."""
        score = compute_volume_anomaly(145, 100, 30, 20)
        assert 0.4 <= score <= 0.6

    def test_below_mean(self):
        """A trade below the mean should score 0."""
        score = compute_volume_anomaly(50, 100, 30, 20)
        assert score == 0.0

    def test_sigma_floor(self):
        """σ = 0 should not raise an error — uses σ floor."""
        score = compute_volume_anomaly(100, 50, 0, 15)
        assert score > 0  # 100 > 50, so z > 0

    def test_low_trade_count_fallback(self):
        """Below min trades, should fall back to global stats."""
        # Only 3 market trades, but global stats provided
        score = compute_volume_anomaly(200, 50, 10, 3, global_mean=100, global_std=30)
        # Should use global stats: z = (200 - 100) / 90 ≈ 1.11
        assert score > 0.0

    def test_low_trade_count_no_global(self):
        """Below min trades and no global stats → 0."""
        score = compute_volume_anomaly(1000, 50, 10, 3)
        assert score == 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# N_C: Topic Concentration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestTopicConcentration:
    def test_single_category(self):
        """All bets in one category → 1.0."""
        assert compute_topic_concentration({"politics": 100.0}) == 1.0

    def test_two_equal_categories(self):
        """Two equal categories → 0.5."""
        assert compute_topic_concentration({"a": 50, "b": 50}) == 0.5

    def test_diversified(self):
        """Many categories → low score."""
        cats = {f"cat_{i}": 10.0 for i in range(10)}
        assert compute_topic_concentration(cats) < 0.2

    def test_empty(self):
        assert compute_topic_concentration({}) == 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# N_M: Market Timing (logarithmic decay)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestMarketTiming:
    def test_zero_hours(self):
        """Trade at resolution → 1.0."""
        assert compute_market_timing(0) == 1.0

    def test_negative_hours(self):
        """After resolution → 1.0."""
        assert compute_market_timing(-5) == 1.0

    def test_one_hour(self):
        """1 hour → ~0.89."""
        score = compute_market_timing(1)
        assert 0.85 <= score <= 0.95

    def test_24_hours(self):
        """24 hours → ~0.52."""
        score = compute_market_timing(24)
        assert 0.45 <= score <= 0.58

    def test_48_hours(self):
        """48 hours → ~0.41 (the key fix)."""
        score = compute_market_timing(48)
        assert 0.35 <= score <= 0.47

    def test_168_hours(self):
        """7 days → ~0.24."""
        score = compute_market_timing(168)
        assert 0.18 <= score <= 0.30

    def test_720_hours(self):
        """30 days → 0.0."""
        assert compute_market_timing(720) == 0.0

    def test_beyond_max(self):
        """Beyond 30 days → 0.0."""
        assert compute_market_timing(1000) == 0.0

    def test_monotonic_decrease(self):
        """Score should decrease as hours increase."""
        hours = [1, 6, 24, 48, 72, 168, 500, 720]
        scores = [compute_market_timing(h) for h in hours]
        for i in range(len(scores) - 1):
            assert scores[i] > scores[i + 1], f"Not monotonic at {hours[i]}h vs {hours[i+1]}h"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# N_F: Wallet Freshness
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestWalletFreshness:
    def test_brand_new(self):
        assert compute_wallet_freshness(0) == 1.0

    def test_one_year(self):
        assert compute_wallet_freshness(365) == 0.0

    def test_half_year(self):
        score = compute_wallet_freshness(182.5)
        assert 0.49 <= score <= 0.51

    def test_very_old(self):
        """Older than a year → 0."""
        assert compute_wallet_freshness(1000) == 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# N_R: Rapid Profit
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRapidProfit:
    def test_buy_price_increase(self):
        """Buy at 0.30, price goes to 0.60 → move = 0.30 → 0.30/0.20 = 1.0 (capped)."""
        assert compute_rapid_profit(0.30, 0.60, "BUY") == 1.0

    def test_buy_price_decrease(self):
        """Buy at 0.30, price drops to 0.20 → move = -0.10 → 0."""
        assert compute_rapid_profit(0.30, 0.20, "BUY") == 0.0

    def test_sell_price_decrease(self):
        """Sell at 0.70, price drops to 0.40 → move = 0.30 → 1.0 (capped)."""
        assert compute_rapid_profit(0.70, 0.40, "SELL") == 1.0

    def test_moderate_move(self):
        """10% move → ~0.5."""
        assert compute_rapid_profit(0.50, 0.60, "BUY") == pytest.approx(0.5)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Aggregate scoring & alert gate
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
        """Score should never exceed 100."""
        result = compute_suspicion_score(1.5, 1.5, 1.5, 1.5, 1.5)
        assert result.score == 100.0

    def test_gate_requires_min_factors(self):
        """High score from one factor alone shouldn't pass gate."""
        # Only volume is high
        result = compute_suspicion_score(1.0, 0.1, 0.1, 0.1, 0.1)
        # Score ≈ 30 + 2.5 + 2 + 1.5 + 1 = 37 — below 50
        assert not result.passes_gate

    def test_typical_insider(self):
        """Classic insider profile should pass the gate."""
        result = compute_suspicion_score(
            volume_anomaly=0.8,
            topic_concentration=1.0,
            market_timing=0.5,  # ~24h before resolution
            wallet_freshness=0.9,
            rapid_profit=0.6,
        )
        # Score ≈ 24 + 25 + 10 + 13.5 + 6 = 78.5
        assert result.score >= 70
        assert result.passes_gate
        assert len(result.elevated_factors) >= 4

    def test_to_dict(self):
        result = compute_suspicion_score(0.5, 0.5, 0.5, 0.5, 0.5)
        d = result.to_dict()
        assert "score" in d
        assert "passes_gate" in d
        assert "elevated_factors" in d
