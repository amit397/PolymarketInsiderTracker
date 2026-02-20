"""
PnL and Win Rate Calculator.

Calculates realized profit/loss and win rates for a wallet by analyzing
its trade history against resolved market data.

Uses NET POSITION (sum of buys - sum of sells) per market to determine
the wallet's directional bet, not just the "last trade" heuristic.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class PnLCalculator:
    """Calculates Realized PnL, Win Rate, and Entry Price Stats."""

    def calculate_stats(
        self,
        trades: list[dict[str, Any]],
        resolved_markets: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Calculate PnL stats for a set of trades given resolved market data.

        Uses NET POSITION per market (sum of BUY sizes - sum of SELL sizes)
        to determine if the wallet was long or short at resolution time.

        Returns dict with win_rate, total_profit, total_pnl, avg_entry_prices, etc.
        """
        if not trades:
            return self._empty_stats()

        # ---- Build per-market position ledger ----
        # For each (conditionId, outcome), track:
        #   net_shares: BUY adds, SELL subtracts
        #   total_cost: money spent buying
        #   total_proceeds: money received selling
        market_positions: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "outcomes": defaultdict(lambda: {
                    "net_shares": 0.0,
                    "total_cost": 0.0,
                    "total_proceeds": 0.0,
                    "buy_count": 0,
                    "total_buy_size": 0.0,
                    "weighted_entry_sum": 0.0,  # size * price for avg entry
                }),
            }
        )

        for t in trades:
            cid = t.get("conditionId")
            if not cid:
                continue

            size = float(t.get("size", 0))
            price = float(t.get("price", 0))
            side = t.get("side", "BUY").upper()
            outcome = t.get("outcome", "Unknown")

            pos = market_positions[cid]["outcomes"][outcome]

            if side == "BUY":
                pos["net_shares"] += size
                pos["total_cost"] += size * price
                pos["buy_count"] += 1
                pos["total_buy_size"] += size
                pos["weighted_entry_sum"] += size * price
            else:
                pos["net_shares"] -= size
                pos["total_proceeds"] += size * price

        # ---- Evaluate against resolved markets ----
        total_wins = 0
        total_losses = 0
        total_resolved = 0
        total_pnl = 0.0
        avg_entry_prices: dict[str, float] = {}  # conditionId -> avg entry price

        for cid, position_data in market_positions.items():
            market = resolved_markets.get(cid)
            if not market or not market.get("closed"):
                continue

            winner_outcome = market.get("winner_outcome")
            if not winner_outcome:
                continue

            total_resolved += 1

            # Determine the wallet's NET directional bet
            # If they have positive net_shares on the winner → they were right
            # If they have positive net_shares on the loser → they were wrong
            outcomes = position_data["outcomes"]

            # Calculate net position value at resolution
            # Winners pay $1 per share, losers pay $0
            position_pnl = 0.0
            net_direction = None  # "correct" or "incorrect"

            for outcome_name, pos in outcomes.items():
                if pos["net_shares"] <= 0:
                    # They sold out completely or were net short
                    # PnL = proceeds - cost (already realized)
                    position_pnl += pos["total_proceeds"] - pos["total_cost"]
                    continue

                # They hold net_shares at resolution
                if outcome_name == winner_outcome:
                    # Winner: each share pays $1
                    resolution_payout = pos["net_shares"] * 1.0
                    position_pnl += resolution_payout + pos["total_proceeds"] - pos["total_cost"]
                    net_direction = "correct"
                else:
                    # Loser: each share pays $0
                    resolution_payout = 0.0
                    position_pnl += resolution_payout + pos["total_proceeds"] - pos["total_cost"]
                    if net_direction != "correct":
                        net_direction = "incorrect"

                # Track avg entry price for this market
                if pos["total_buy_size"] > 0:
                    avg_entry = pos["weighted_entry_sum"] / pos["total_buy_size"]
                    avg_entry_prices[cid] = avg_entry

            total_pnl += position_pnl

            if net_direction == "correct":
                total_wins += 1
            elif net_direction == "incorrect":
                total_losses += 1

        win_rate = (total_wins / total_resolved * 100) if total_resolved > 0 else 0.0
        total_profit = max(0.0, total_pnl)  # Profit is the positive portion

        return {
            "win_rate": round(win_rate, 2),
            "resolved_markets_count": total_resolved,
            "wins": total_wins,
            "losses": total_losses,
            "total_pnl": round(total_pnl, 2),
            "total_profit": round(total_profit, 2),
            "avg_entry_prices": avg_entry_prices,
        }

    def _empty_stats(self) -> dict[str, Any]:
        return {
            "win_rate": 0.0,
            "resolved_markets_count": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "total_profit": 0.0,
            "avg_entry_prices": {},
        }
