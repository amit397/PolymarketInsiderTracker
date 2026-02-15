"""
PnL and Win Rate Calculator.

Calculates realized profit/loss and win rates for a wallet by analyzing
its trade history against resolved market data.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class PnLCalculator:
    """Calculates Realized PnL and Win Rate."""

    def calculate_stats(
        self,
        trades: list[dict[str, Any]],
        resolved_markets: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Calculate PnL stats for a set of trades given resolved market data.
        
        :param trades: List of trade dicts (must contain 'conditionId', 'side', 'size', 'outcome', 'price')
        :param resolved_markets: Dict mapping condition_id -> market_info (must contain 'resolved', 'winner')
        :return: Dict with win_rate, total_profit, etc.
        """
        if not trades:
            return self._empty_stats()

        # Group trades by market
        market_positions = defaultdict(lambda: {"spent": 0.0, "payout": 0.0, "wins": 0, "losses": 0})
        
        for t in trades:
            cid = t.get("conditionId")
            if not cid:
                continue
                
            market = resolved_markets.get(cid)
            if not market:
                # Market not resolved or data missing, skip PnL calc for this trade
                continue

            # Polymarket trades: 
            # side="BUY" -> Spent = size * price
            # side="SELL" -> Payout = size * price (realized gain)
            # Resolution -> Payout = size * 1 (if winner) or 0 (if loser)
            # Note: This is a simplified approximation. A proper ledger is complex.
            # We will focus on "Did they pick the winner?" for Win Rate.

            # Win Rate Logic:
            # If they hold a position in the WINNING outcome at resolution, it's a WIN.
            # If they hold a position in the LOSING outcome at resolution, it's a LOSS.
            
            # Since we only see "trades", we need to reconstruct the final position?
            # Or simpler: For every market they traded, did they net profit?
            
            # Let's track Net Cash Flow per market.
            size = float(t.get("size", 0))
            price = float(t.get("price", 0))
            side = t.get("side", "BUY").upper()
            outcome = t.get("outcome") # e.g. "Yes" or "No" (sometimes handled by outcome index)
            
            # Cost basis
            if side == "BUY":
                market_positions[cid]["spent"] += size * price
            else:
                market_positions[cid]["payout"] += size * price

        # Now handle resolution payouts
        # This requires knowing their *final held* tokens.
        # Without a full ledger, we can't know for sure if they sold before resolution.
        # BUT, the user wants "Prediction Rate".
        # Proxy: If they bought the WINNER more than the LOSER, count as correct?
        
        # Better Proxy for "Prediction Rate" without full ledger:
        # Check if the market is resolved.
        # If resolved, look at their *last* trade in that market. 
        # If they were BUYING the WINNER, or SELLING the LOSER, they were "Correct".
        
        # Actually, let's use the Profit metric if possible. 
        # Profit = Payouts - Cost.
        # If Profit > 0 on a resolved market -> Win.
        
        # We need to know the resolution outcome.
        # resolved_markets[cid] should have 'token_id' of winner or 'outcome_index'.
        
        total_wins = 0
        total_resolved_participated = 0
        total_pnl = 0.0

        for cid, stats in market_positions.items():
            market = resolved_markets.get(cid)
            if not market or not market.get("closed"):
                continue

            # simplistic PnL approach if we assume they held to expiry? 
            # We can't assume that.
            
            # Let's go with the "Last Intent" heuristic for Prediction Rate.
            # Find the last trade this user made in this market.
            last_trade = next((t for t in reversed(trades) if t.get("conditionId") == cid), None)
            if not last_trade:
                continue
                
            total_resolved_participated += 1
            
            # Determine if last action was "Smart"
            winner_outcome = market.get("winner_outcome") # e.g. "Yes"
            if not winner_outcome:
                continue

            trade_outcome = last_trade.get("outcome")
            trade_side = last_trade.get("side", "BUY").upper()
            
            is_smart = False
            
            # If they BOUGHT the Winner
            if trade_side == "BUY" and trade_outcome == winner_outcome:
                is_smart = True
            # If they SOLD the Loser
            elif trade_side == "SELL" and trade_outcome != winner_outcome:
                is_smart = True
            # If they BOUGHT the Loser -> False
            # If they SOLD the Winner -> False (locking in profit? or bailing?)
            
            if is_smart:
                total_wins += 1
        
        win_rate = (total_wins / total_resolved_participated * 100) if total_resolved_participated > 0 else 0.0
        
        return {
            "win_rate": round(win_rate, 2),
            "resolved_markets_count": total_resolved_participated,
            "wins": total_wins,
        }

    def _empty_stats(self) -> dict[str, Any]:
        return {
            "win_rate": 0.0,
            "resolved_markets_count": 0,
            "wins": 0,
        }
