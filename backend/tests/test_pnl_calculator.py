"""Tests for the redesigned PnL calculator."""

import pytest

from app.services.pnl_calculator import PnLCalculator


@pytest.fixture
def pnl():
    return PnLCalculator()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Empty / basic cases
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_empty_trades(pnl):
    stats = pnl.calculate_stats([], {})
    assert stats["win_rate"] == 0.0
    assert stats["resolved_markets_count"] == 0
    assert stats["total_pnl"] == 0.0
    assert stats["total_profit"] == 0.0
    assert stats["avg_entry_prices"] == {}


def test_no_resolved_markets(pnl):
    """Trades exist but no markets are resolved → no PnL."""
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.5}
    ]
    stats = pnl.calculate_stats(trades, {})
    assert stats["win_rate"] == 0.0
    assert stats["resolved_markets_count"] == 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Net position win/loss detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_buy_winner_is_win(pnl):
    """Bought YES, market resolves YES → WIN."""
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.3}
    ]
    markets = {"1": {"closed": True, "winner_outcome": "Yes"}}
    stats = pnl.calculate_stats(trades, markets)
    assert stats["win_rate"] == 100.0
    assert stats["wins"] == 1
    assert stats["total_pnl"] > 0  # Paid 30, gets 100 back


def test_buy_loser_is_loss(pnl):
    """Bought YES, market resolves No → LOSS."""
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.7}
    ]
    markets = {"1": {"closed": True, "winner_outcome": "No"}}
    stats = pnl.calculate_stats(trades, markets)
    assert stats["win_rate"] == 0.0
    assert stats["losses"] == 1
    assert stats["total_pnl"] < 0  # Paid 70, gets 0 back


def test_net_position_buy_sell(pnl):
    """Buy 100, sell 80 → net 20 shares held. If winner, still a win."""
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.4},
        {"conditionId": "1", "side": "SELL", "outcome": "Yes", "size": 80, "price": 0.6},
    ]
    markets = {"1": {"closed": True, "winner_outcome": "Yes"}}
    stats = pnl.calculate_stats(trades, markets)
    assert stats["win_rate"] == 100.0
    assert stats["wins"] == 1
    # PnL: 20 shares * $1 (resolution) + 80 * $0.6 (sell proceeds) - 100 * $0.4 (cost) = 20 + 48 - 40 = 28
    assert stats["total_pnl"] == pytest.approx(28.0)


def test_sold_out_before_resolution(pnl):
    """Buy 100, sell 100 → net 0 shares. No directional bet."""
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.3},
        {"conditionId": "1", "side": "SELL", "outcome": "Yes", "size": 100, "price": 0.5},
    ]
    markets = {"1": {"closed": True, "winner_outcome": "Yes"}}
    stats = pnl.calculate_stats(trades, markets)
    # They sold out, so PnL = proceeds - cost = 50 - 30 = 20
    assert stats["total_pnl"] == pytest.approx(20.0)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Mixed markets
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_mixed_results(pnl):
    """Market 1: WIN, Market 2: LOSS, Market 3: unresolved."""
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.5},
        {"conditionId": "2", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.5},
        {"conditionId": "3", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.5},
    ]
    markets = {
        "1": {"closed": True, "winner_outcome": "Yes"},
        "2": {"closed": True, "winner_outcome": "No"},
        "3": {"closed": False},
    }
    stats = pnl.calculate_stats(trades, markets)
    assert stats["win_rate"] == 50.0
    assert stats["resolved_markets_count"] == 2
    assert stats["wins"] == 1
    assert stats["losses"] == 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Avg entry price tracking
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_avg_entry_price(pnl):
    """Average entry price should be weighted by size."""
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.2},
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 200, "price": 0.4},
    ]
    markets = {"1": {"closed": True, "winner_outcome": "Yes"}}
    stats = pnl.calculate_stats(trades, markets)
    # Weighted: (100*0.2 + 200*0.4) / 300 = (20+80)/300 = 100/300 ≈ 0.333
    avg = stats["avg_entry_prices"].get("1", {}).get("Yes")
    assert avg is not None
    assert avg == pytest.approx(0.333, abs=0.01)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PnL calculation accuracy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_pnl_correct_for_winner(pnl):
    """Buy 100 shares at $0.10, winner → PnL = 100*1 - 100*0.10 = 90."""
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.10}
    ]
    markets = {"1": {"closed": True, "winner_outcome": "Yes"}}
    stats = pnl.calculate_stats(trades, markets)
    assert stats["total_pnl"] == pytest.approx(90.0)
    assert stats["total_profit"] == pytest.approx(90.0)


def test_pnl_correct_for_loser(pnl):
    """Buy 100 shares at $0.70, loser → PnL = 0 - 100*0.70 = -70."""
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 100, "price": 0.70}
    ]
    markets = {"1": {"closed": True, "winner_outcome": "No"}}
    stats = pnl.calculate_stats(trades, markets)
    assert stats["total_pnl"] == pytest.approx(-70.0)
    assert stats["total_profit"] == 0.0  # profit = max(0, pnl)
