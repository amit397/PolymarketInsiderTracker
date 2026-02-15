import pytest
from app.services.pnl_calculator import PnLCalculator

@pytest.fixture
def pnl():
    return PnLCalculator()

def test_empty_trades(pnl):
    stats = pnl.calculate_stats([], {})
    assert stats["win_rate"] == 0.0
    assert stats["resolved_markets_count"] == 0

def test_single_win(pnl):
    # User bought YES on ID 1, Market 1 resolved YES
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 10, "price": 0.5, "timestamp": 100}
    ]
    markets = {
        "1": {"closed": True, "winner_outcome": "Yes"}
    }
    stats = pnl.calculate_stats(trades, markets)
    assert stats["win_rate"] == 100.0
    assert stats["resolved_markets_count"] == 1
    assert stats["wins"] == 1

def test_single_loss(pnl):
    # User bought NO on ID 1, Market 1 resolved YES
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "No", "size": 10, "price": 0.5, "timestamp": 100}
    ]
    markets = {
        "1": {"closed": True, "winner_outcome": "Yes"}
    }
    stats = pnl.calculate_stats(trades, markets)
    assert stats["win_rate"] == 0.0
    assert stats["resolved_markets_count"] == 1
    assert stats["wins"] == 0

def test_mixed_results(pnl):
    # Market 1: WIN (Bought YES, Winner YES)
    # Market 2: LOSS (Bought YES, Winner NO)
    # Market 3: UNRESOLVED
    trades = [
        {"conditionId": "1", "side": "BUY", "outcome": "Yes", "size": 10, "timestamp": 100},
        {"conditionId": "2", "side": "BUY", "outcome": "Yes", "size": 10, "timestamp": 100},
        {"conditionId": "3", "side": "BUY", "outcome": "Yes", "size": 10, "timestamp": 100},
    ]
    markets = {
        "1": {"closed": True, "winner_outcome": "Yes"},
        "2": {"closed": True, "winner_outcome": "No"},
        "3": {"closed": False, "winner_outcome": "TBD"},
    }
    stats = pnl.calculate_stats(trades, markets)
    assert stats["win_rate"] == 50.0 # 1 win out of 2 resolved
    assert stats["resolved_markets_count"] == 2
    assert stats["wins"] == 1
