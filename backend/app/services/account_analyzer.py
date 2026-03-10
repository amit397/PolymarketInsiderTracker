"""
Account Analyzer Service — Redesigned v2.

Market-first approach: analyzes wallets discovered through targeted
market scanning. Uses server-side API filters for trade fetching and
the six-factor scoring system with boosted fresh-account + position-size signals.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.core.config import (
    ALERT_MIN_SCORE,
    MIN_POSITION_SIZE,
    MIN_RESOLVED_MARKETS,
)
from app.core.database import get_db
from app.core.monitor import monitor
from app.services.data_client import DataClient
from app.services.gamma_client import GammaClient
from app.services.pnl_calculator import PnLCalculator
from app.services.polygonscan import PolygonscanClient
from app.services.scoring import (
    ScoringResult,
    compute_bet_concentration,
    compute_entry_price_edge,
    compute_position_size_signal,
    compute_win_rate_anomaly,
    compute_timing_signal,
    compute_account_pattern,
    compute_suspicion_score,
)

logger = logging.getLogger(__name__)


class AccountAnalyzer:
    """Service to systematically analyze accounts for insider activity."""

    def __init__(
        self,
        data: DataClient | None = None,
        gamma: GammaClient | None = None,
        polygonscan: PolygonscanClient | None = None,
    ) -> None:
        self.data = data or DataClient()
        self.gamma = gamma or GammaClient()
        self.polygonscan = polygonscan or PolygonscanClient()
        self.pnl_calculator = PnLCalculator()
        self._owns_clients = data is None
        self._market_cache: dict[str, dict[str, Any]] = {}

    async def close(self) -> None:
        if self._owns_clients:
            await self.data.close()
            await self.gamma.close()
            await self.polygonscan.close()

    async def analyze_all_wallets(self) -> None:
        """
        Iterate through all unique wallets in the 'trades' table and analyze them.
        Uses USDC-based position sizes (usdc_size column) for thresholds.
        """
        logger.info("Starting systematic account analysis...")
        monitor.update("Starting Account Analysis Cycle")

        db = await get_db()
        try:
            # Get wallets with notable USDC positions in at least one market
            # Use usdc_size if available, else fall back to size * price
            cursor = await db.execute("""
                SELECT proxy_wallet, condition_id,
                       SUM(CASE WHEN usdc_size > 0 THEN usdc_size ELSE size * price END) as market_usdc
                FROM trades 
                WHERE proxy_wallet IS NOT NULL AND proxy_wallet != ''
                GROUP BY proxy_wallet, condition_id
                HAVING market_usdc >= ?
            """, (MIN_POSITION_SIZE,))
            rows = await cursor.fetchall()
            whale_wallets = {str(row[0]).lower() for row in rows}

            # Get already scanned
            cursor = await db.execute("SELECT address FROM wallets")
            rows = await cursor.fetchall()
            scanned = {str(row[0]).lower() for row in rows}

            # New wallets
            new_wallets = list(whale_wallets - scanned)

            # Stale whales: already scanned, notable score, not checked in 24h
            cursor = await db.execute("""
                SELECT address FROM wallets 
                WHERE risk_score >= 15
                AND last_scanned < datetime('now', '-1 day')
            """)
            rows = await cursor.fetchall()
            stale_whales = [str(row[0]).lower() for row in rows]

            wallets = list(set(new_wallets + stale_whales))

        finally:
            await db.close()

        if not wallets:
            logger.info("No new whale wallets or stale targets to analyze.")
            monitor.update("Idle - No targets found", stats={"last_cycle_wallets": 0})
            return

        logger.info(
            "Found %d wallets to analyze (%d new, %d stale)",
            len(wallets), len(new_wallets), len(stale_whales),
        )
        monitor.update(
            f"Queue: {len(new_wallets)} New, {len(stale_whales)} Stale",
            stats={"total_wallets": len(wallets)},
        )

        for i, wallet in enumerate(wallets):
            try:
                is_rescan = wallet in stale_whales
                status_msg = (
                    f"Re-verifying Target ({i+1}/{len(wallets)})"
                    if is_rescan
                    else f"Analyzing New Target ({i+1}/{len(wallets)})"
                )
                monitor.update(status_msg, wallet=wallet, stats={"processed": i + 1, "total": len(wallets)})
                await self.analyze_wallet(wallet)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error("Failed to analyze wallet %s: %s", wallet, e)

        logger.info("Account analysis complete.")
        monitor.update("Idle", wallet=None, stats={"last_cycle_wallets": len(wallets)})

    async def analyze_wallet(self, wallet: str) -> None:
        """Perform deep analysis on a single wallet using the six-factor scoring system."""
        wallet = wallet.lower()

        # ---- 1. Enrich: fetch wallet's full trade history via server-side filter ----
        await self._enrich_wallet_history(wallet)

        # ---- 2. Load all trades from local DB ----
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM trades WHERE proxy_wallet = ? ORDER BY timestamp DESC",
                (wallet,),
            )
            rows = await cursor.fetchall()
            trades = []
            for row in rows:
                t = dict(row)
                t["conditionId"] = t["condition_id"]
                t["transactionHash"] = t["tx_hash"]
                t["size"] = float(t["size"])
                t["price"] = float(t["price"])
                t["usdc_size"] = float(t.get("usdc_size", 0) or 0)
                t["title"] = t.get("market_question", "")
                trades.append(t)
        finally:
            await db.close()

        if not trades:
            logger.info("No trades found for %s in local DB", wallet)
            return

        # ---- 3. Compute USDC-based volumes per market ----
        market_usdc_volumes: dict[str, float] = defaultdict(float)
        market_share_volumes: dict[str, float] = defaultdict(float)
        market_prices: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for t in trades:
            cid = t.get("conditionId")
            if cid:
                usdc = t["usdc_size"] if t["usdc_size"] > 0 else t["size"] * t["price"]
                market_usdc_volumes[cid] += usdc
                market_share_volumes[cid] += t["size"]
                if t["price"] > 0 and t.get("side", "").upper() == "BUY":
                    outcome_str = t.get("outcome", "Unknown")
                    market_prices[cid][outcome_str].append(t["price"])

        total_usdc = sum(market_usdc_volumes.values())
        max_single_market_usdc = max(market_usdc_volumes.values()) if market_usdc_volumes else 0.0

        if max_single_market_usdc < MIN_POSITION_SIZE:
            await self._mark_scanned(wallet, len(trades), total_usdc)
            return

        # ---- 4. Fetch market resolution data ----
        market_ids = list(market_usdc_volumes.keys())
        resolved_markets: dict[str, dict[str, Any]] = {}
        for mid in market_ids:
            if not mid:
                continue
            
            # Use cached market if available
            if hasattr(self, "_market_cache") and mid in self._market_cache:
                resolved_markets[mid] = self._market_cache[mid]
                continue
                
            try:
                m = await self.gamma.fetch_market_by_id(mid)
                if m:
                    # Update cache
                    if hasattr(self, "_market_cache"):
                        self._market_cache[mid] = m
                    resolved_markets[mid] = m
                await asyncio.sleep(0.15)  # Rate Limit Avoidance
            except Exception:
                pass

        # ---- 5. Calculate PnL / Win Rate ----
        pnl_stats = self.pnl_calculator.calculate_stats(trades, resolved_markets)
        win_rate = pnl_stats.get("win_rate", 0.0)
        total_profit = pnl_stats.get("total_profit", 0.0)
        total_pnl = pnl_stats.get("total_pnl", 0.0)
        resolved_count = pnl_stats.get("resolved_markets_count", 0)
        avg_entry_prices = pnl_stats.get("avg_entry_prices", {})

        # ---- 6. Fetch wallet age + profile ----
        age_days = await self.polygonscan.fetch_wallet_age_days(wallet)
        profile = await self.gamma.fetch_public_profile(wallet)
        username = None
        if profile:
            username = profile.get("name") or profile.get("pseudonym")
            if age_days is None and profile.get("createdAt"):
                try:
                    created = datetime.fromisoformat(
                        profile["createdAt"].replace("Z", "+00:00")
                    )
                    age_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
                except Exception:
                    pass

        # ---- 7. Compute Six-Factor Score ----
        total_markets_traded = len(market_usdc_volumes)

        # Primary market = highest USDC volume
        primary_market_id = max(market_usdc_volumes, key=market_usdc_volumes.get)
        primary_market_usdc = market_usdc_volumes[primary_market_id]

        # Factor 1: Win Rate Anomaly (confidence-weighted)
        f_win_rate = compute_win_rate_anomaly(win_rate, resolved_count)

        # Factor 2: Bet Concentration (using USDC volumes)
        f_concentration = compute_bet_concentration(primary_market_usdc, total_usdc)

        # Factor 3: Timing Signal
        timing_scores = []
        for cid, vol in market_usdc_volumes.items():
            if cid in resolved_markets:
                m = resolved_markets[cid]
                if m.get("endDate"):
                    try:
                        end_dt = datetime.fromisoformat(m["endDate"].replace("Z", "+00:00"))
                        market_trades = [t for t in trades if t.get("conditionId") == cid]
                        if market_trades:
                            earliest = min(t.get("timestamp", 0) for t in market_trades)
                            trade_dt = datetime.fromtimestamp(earliest, tz=timezone.utc)
                            hours = max(0, (end_dt - trade_dt).total_seconds() / 3600)
                            timing_scores.append(compute_timing_signal(hours))
                    except Exception:
                        pass
        f_timing = (sum(timing_scores) / len(timing_scores)) if timing_scores else 0.0

        # Factor 4: Entry Price Edge
        edge_scores = []
        for cid, market_avg_entries in avg_entry_prices.items():
            market = resolved_markets.get(cid)
            if market and market.get("closed") and market.get("winner_outcome"):
                winner = market["winner_outcome"]
                if winner in market_avg_entries:
                    avg_entry = market_avg_entries[winner]
                    market_trades = [t for t in trades if t.get("conditionId") == cid]
                    winner_buys = sum(
                        t["size"] for t in market_trades
                        if t.get("side", "").upper() == "BUY" and t.get("outcome") == winner
                    )
                    winner_sells = sum(
                        t["size"] for t in market_trades
                        if t.get("side", "").upper() == "SELL" and t.get("outcome") == winner
                    )
                    won = (winner_buys - winner_sells) > 0
                    edge_scores.append(compute_entry_price_edge(avg_entry, won))
        f_edge = (sum(edge_scores) / len(edge_scores)) if edge_scores else 0.0

        # Factor 5: Account Pattern (boosted freshness)
        f_pattern = compute_account_pattern(age_days, total_markets_traded, f_concentration)

        # Factor 6: Position Size Signal (NEW — large USDC on low-odds outcomes)
        # Flatten all prices for the primary market across outcomes (rough proxy, ideally mapped to specific targeted outcome)
        primary_prices = []
        if primary_market_id in market_prices:
            for outcome_prices in market_prices[primary_market_id].values():
                primary_prices.extend(outcome_prices)
        primary_avg_price = (
            sum(primary_prices) / len(primary_prices) if primary_prices else 0.5
        )
        f_position = compute_position_size_signal(primary_market_usdc, primary_avg_price)

        # ---- 8. Compute final score ----
        result = compute_suspicion_score(
            win_rate_anomaly=f_win_rate,
            bet_concentration=f_concentration,
            timing_signal=f_timing,
            entry_price_edge=f_edge,
            account_pattern=f_pattern,
            position_size_signal=f_position,
        )

        # ---- 9. Log detection ----
        if result.passes_gate:
            monitor.update(
                f"🚨 SUSPICIOUS ACCOUNT (Score: {result.score:.0f})",
                wallet=wallet,
            )
            await asyncio.sleep(2)
        elif result.score >= 20:
            monitor.update(
                f"🐳 Analyzed (Score: {result.score:.0f}, ${total_profit:,.0f} Profit)",
                wallet=wallet,
            )

        # ---- 10. Persist to database ----
        analysis_data = {
            "win_rate": win_rate,
            "total_profit": total_profit,
            "total_pnl": total_pnl,
            "trade_count": len(trades),
            "resolved_markets_count": resolved_count,
            "markets_traded": total_markets_traded,
            "max_single_market_usdc": max_single_market_usdc,
            "total_usdc_invested": total_usdc,
            "account_age_days": age_days,
            "username": username,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "score": result.score,
            "passes_gate": result.passes_gate,
            "factors": result.to_dict(),
        }

        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO wallets (address, username, total_trades, total_volume, risk_score, 
                                    total_profit, analysis_json, last_scanned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    username = excluded.username,
                    total_trades = excluded.total_trades,
                    total_volume = excluded.total_volume,
                    risk_score = excluded.risk_score,
                    total_profit = excluded.total_profit,
                    analysis_json = excluded.analysis_json,
                    last_scanned = excluded.last_scanned
                """,
                (
                    wallet,
                    username,
                    len(trades),
                    total_usdc,
                    result.score,
                    total_profit,
                    json.dumps(analysis_data),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await db.commit()
            logger.info(
                "Analyzed %s (%s): Score=%.1f WinRate=%.1f%% USDC=$%.0f Age=%s",
                wallet, username or "anon", result.score, win_rate,
                total_usdc, f"{age_days:.0f}d" if age_days else "unknown",
            )
        finally:
            await db.close()

        # ---- 11. Generate alert if suspicious ----
        if result.passes_gate and trades:
            latest_trade = trades[0]
            await self._persist_alert(wallet, latest_trade, result)

    async def _mark_scanned(self, wallet: str, trade_count: int, total_usdc: float) -> None:
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO wallets (address, total_trades, total_volume, risk_score, last_scanned)
                VALUES (?, ?, ?, 0, ?)
                ON CONFLICT(address) DO UPDATE SET last_scanned = excluded.last_scanned
                """,
                (wallet, trade_count, total_usdc, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()
        finally:
            await db.close()

    async def _persist_alert(
        self,
        wallet: str,
        trade: dict,
        result: ScoringResult,
    ) -> None:
        alert_data = {
            "wallet_address": wallet,
            "market_id": trade.get("conditionId", ""),
            "condition_id": trade.get("conditionId", ""),
            "suspicion_score": result.score,
            "factors_json": json.dumps(result.to_dict()),
            "market_question": trade.get("title", "") or trade.get("market_question", ""),
            "market_slug": trade.get("slug", "") or trade.get("market_slug", ""),
            "market_end_date": None,
            "trade_size": trade.get("size", 0),
            "trade_side": trade.get("side", ""),
            "tx_hash": trade.get("transactionHash", "") or trade.get("tx_hash", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO alerts
                    (wallet_address, market_id, condition_id, suspicion_score,
                     factors_json, market_question, market_slug, market_end_date,
                     trade_size, trade_side, tx_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_data["wallet_address"],
                    alert_data["market_id"],
                    alert_data["condition_id"],
                    alert_data["suspicion_score"],
                    alert_data["factors_json"],
                    alert_data["market_question"],
                    alert_data["market_slug"],
                    alert_data["market_end_date"],
                    alert_data["trade_size"],
                    alert_data["trade_side"],
                    alert_data["tx_hash"],
                    alert_data["created_at"],
                ),
            )
            await db.commit()
            logger.info("Generated alert for %s (Score: %.1f)", wallet, result.score)
        except Exception as e:
            logger.error("Failed to persist alert: %s", e)
        finally:
            await db.close()

    async def _enrich_wallet_history(self, wallet: str) -> None:
        """
        Fetch the wallet's full trade history using server-side `user=` filter
        and save new trades to local DB.
        
        No longer has a 10-trade cap — always enriches to get complete history.
        """
        wallet = wallet.lower()
        logger.info("Enriching trade history for %s", wallet)

        try:
            api_trades = await self.data.fetch_wallet_trades(wallet, max_pages=50)
        except Exception as e:
            logger.warning("Failed to fetch history for %s: %s", wallet, e)
            return

        if not api_trades:
            return

        # Get existing tx hashes to avoid duplicates
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT tx_hash FROM trades WHERE proxy_wallet = ? AND tx_hash IS NOT NULL",
                (wallet,),
            )
            existing_hashes = {row[0] for row in await cursor.fetchall()}

            new_trades = []
            for t in api_trades:
                tx = t.get("transactionHash", "")
                if tx and tx not in existing_hashes:
                    try:
                        size = float(t.get("size", 0))
                        price = float(t.get("price", 0))
                    except (ValueError, TypeError):
                        continue

                    usdc_size = size * price  # Compute USDC value

                    new_trades.append((
                        t.get("conditionId", ""),
                        t.get("slug", ""),
                        (t.get("proxyWallet", wallet) or wallet).lower(),
                        t.get("side", ""),
                        size,
                        usdc_size,
                        price,
                        t.get("outcome", ""),
                        t.get("timestamp", 0),
                        tx,
                        t.get("title", ""),
                    ))

            if new_trades:
                await db.executemany(
                    """
                    INSERT OR IGNORE INTO trades
                        (condition_id, market_slug, proxy_wallet, side, size,
                         usdc_size, price, outcome, timestamp, tx_hash, market_question)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    new_trades,
                )
                await db.commit()
                logger.info("Enriched %s with %d new trades", wallet, len(new_trades))
        except Exception as e:
            logger.error("Error enriching wallet %s: %s", wallet, e)
        finally:
            await db.close()
