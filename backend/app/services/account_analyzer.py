"""
Account Analyzer Service.
Iterates through known wallets and analyzes their trading history to identify insiders.
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import time
from datetime import datetime, timezone

from app.core.database import get_db
from app.services.data_client import DataClient
from app.services.gamma_client import GammaClient
from app.services.pnl_calculator import PnLCalculator
from app.services.polygonscan import PolygonscanClient
from app.services.scoring import compute_suspicion_score
from app.core.monitor import monitor # Import Monitor

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

    async def close(self) -> None:
        if self._owns_clients:
            await self.data.close()
            await self.gamma.close()
            await self.polygonscan.close()

    async def analyze_all_wallets(self) -> None:
        """
        Iterate through all unique wallets in the 'trades' table and analyze them.
        updates the 'wallets' table with risk scores and stats.
        """
        logger.info("Starting systematic account analysis...")
        monitor.update("Starting Account Analysis Cycle")
        
        # 1. Get all unique wallets from trades table
        db = await get_db()
        try:
            # Get candidates
            cursor = await db.execute("SELECT DISTINCT proxy_wallet FROM trades WHERE proxy_wallet IS NOT NULL AND proxy_wallet != ''")
            rows = await cursor.fetchall()
            candidates = {row[0] for row in rows}

            # Get already scanned (set of addresses)
            cursor = await db.execute("SELECT address FROM wallets")
            rows = await cursor.fetchall()
            scanned = {row[0] for row in rows}
            
            # 1. New Wallets: Candidates that are NOT in 'scanned'
            new_wallets = list(candidates - scanned)

            # 2. Stale Whales: Already scanned, but match "Whale" criteria and haven't been checked in 24h
            # Criteria: PnL > $10k OR Risk Score > 50
            cursor = await db.execute("""
                SELECT address FROM wallets 
                WHERE (total_profit >= 10000 OR risk_score >= 50)
                AND last_scanned < datetime('now', '-1 day')
            """)
            rows = await cursor.fetchall()
            stale_whales = [row[0] for row in rows]

            # Combine
            wallets = list(set(new_wallets + stale_whales))
            
        finally:
            await db.close()

        if not wallets:
            logger.info("No new wallets or stale whales to analyze.")
            monitor.update("Idle - No targets found", stats={"last_cycle_wallets": 0})
            return

        logger.info("Found %d wallets to analyze (%d new, %d stale whales)", len(wallets), len(new_wallets), len(stale_whales))
        monitor.update(f"Queue: {len(new_wallets)} New, {len(stale_whales)} Whales", stats={"total_wallets": len(wallets)})

        for i, wallet in enumerate(wallets):
            try:
                is_whale_rescan = wallet in stale_whales
                status_msg = f"Re-verifying Whale ({i+1}/{len(wallets)})" if is_whale_rescan else f"Analyzing New Target ({i+1}/{len(wallets)})"
                
                monitor.update(status_msg, wallet=wallet, stats={"processed": i+1, "total": len(wallets)})
                await self.analyze_wallet(wallet)
                # Sleep briefly to avoid rate limits
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error("Failed to analyze wallet %s: %s", wallet, e)

        logger.info("Account analysis complete.")
        monitor.update("Idle", wallet=None, stats={"last_cycle_wallets": len(wallets)})

    async def analyze_wallet(self, wallet: str) -> None:
        """Perform deep analysis on a single wallet."""
        # 1. Fetch entire history from LOCAL DB (API is not reliable for history)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM trades WHERE proxy_wallet = ? ORDER BY timestamp DESC", 
                (wallet,)
            )
            rows = await cursor.fetchall()
            trades = []
            for row in rows:
                # Convert row to dict and map to expected format
                t = dict(row)
                # Map snake_case DB columns to camelCase API format used by logic
                t["conditionId"] = t["condition_id"]
                t["transactionHash"] = t["tx_hash"]
                # Ensure numeric types
                t["size"] = float(t["size"])
                t["price"] = float(t["price"])
                trades.append(t)
        finally:
            await db.close()

        if not trades:
            logger.info("No trades found for %s in local DB", wallet)
            return

        # 2. Match with Market Info for PnL/WinRate
        market_ids = {t.get("conditionId") for t in trades if t.get("conditionId")}
        resolved_markets = {}
        
        # Optimize: Fetch markets in batches or individually if needed
        # For now, fetch individually but we should probably cache this in a real high-throughput system
        # We'll use the GammaClient to fetch market details
        for mid in market_ids:
            if not mid: continue
            try:
                 # Check if we can get resolution data
                 # We need to know if the market is resolved and who won
                 m = await self.gamma.fetch_market_by_id(mid)
                 if m:
                     resolved_markets[mid] = m
            except Exception:
                pass

        # 3. Calculate Stats
        pnl_stats = self.pnl_calculator.calculate_stats(trades, resolved_markets)
        win_rate = pnl_stats.get("win_rate", 0.0)
        total_profit = pnl_stats.get("total_profit", 0.0)
        total_pnl = pnl_stats.get("total_pnl", 0.0)

        # 4. Compute Risk Score (Simplified for aggregated view)
        # We can re-use the scoring logic or define a new "Account Level" score
        # For this refactor, let's use the average suspicion score of their trades
        # PLUS their win rate as a major factor.
        
        scores = []
        total_vol = sum(t["size"] for t in trades)
        
        # Group by market for scoring context
        market_map = {}
        for t in trades:
            cid = t.get("conditionId")
            if cid not in market_map: market_map[cid] = []
            market_map[cid].append(t)

        for t in trades:
            cid = t.get("conditionId")
            market_vol = sum(x["size"] for x in market_map.get(cid, []))
            
            # Compute score for this trade
            # We lack global context here so N_V might be weak, but N_C, N_M, N_F, N_R work
            age_days = await self.polygonscan.fetch_wallet_age_days(wallet)
            
            # Market Timing
            nm = 0.0
            if cid in resolved_markets:
                m = resolved_markets[cid]
                if m.get("endDate"):
                    try:
                        end_dt = datetime.fromisoformat(m["endDate"].replace("Z", "+00:00"))
                        trade_dt = datetime.fromtimestamp(t.get("timestamp", 0), tz=timezone.utc)
                        hours = max(0, (end_dt - trade_dt).total_seconds() / 3600)
                        from app.services.scoring import compute_market_timing
                        nm = compute_market_timing(hours)
                    except: pass
            
            # Freshness
            nf = 0.0
            from app.services.scoring import compute_wallet_freshness
            if age_days is not None:
                nf = compute_wallet_freshness(age_days)
            
            # Simple concentration
            from app.services.scoring import compute_topic_concentration
            nc = compute_topic_concentration(market_vol, total_vol)
            
            # Rapid Profit (if applicable)
            # Hard to compute without full order book history, assume 0 for batch unless we have it
            nr = 0.0

            res = compute_suspicion_score(
                volume_anomaly=0.0, # specific to real-time stream usually
                topic_concentration=nc,
                market_timing=nm,
                wallet_freshness=nf,
                rapid_profit=nr,
                historical_win_rate=win_rate # NEW: Add win rate to score
            )
            scores.append(res.score)

        avg_score = statistics.mean(scores) if scores else 0.0
        
        # 5. Update Database
        # ONLY if PnL > 10,000 (User Requirement)
        # We still save "checked" status to avoid re-scanning low-value wallets forever
        
        MIN_PNL_THRESHOLD = 10000.0

        if total_profit < MIN_PNL_THRESHOLD:
             # Mark as scanned but don't save full details/score/alerts
             # We just insert a basic record so it's in the 'scanned' set
             db = await get_db()
             try:
                 await db.execute(
                     """
                     INSERT INTO wallets (address, total_trades, total_volume, risk_score, last_scanned)
                     VALUES (?, ?, ?, 0, ?)
                     ON CONFLICT(address) DO UPDATE SET last_scanned = excluded.last_scanned
                     """,
                     (wallet, len(trades), total_vol, datetime.now(timezone.utc).isoformat())
                 )
                 await db.commit()
                 # logger.info("Skipped %s (PnL $%.0f < $10k)", wallet, total_profit)
             finally:
                 await db.close()
             return

        # Boost score if Win Rate is high (> 70%) and significant volume
        if win_rate > 0.7 and len(trades) > 5:
            avg_score = max(avg_score, 85.0) # High win rate = probable insider

        # User request: "Possible whale found, analyzing trades"
        monitor.update(f"🐳 Possible Whale Found! (${total_profit:,.0f} Profit)", wallet=wallet)
        # Specific delay to let the user see the "Whale Found" message
        await asyncio.sleep(2)

        analysis_data = {
            "win_rate": win_rate,
            "total_profit": total_profit,
            "total_pnl": total_pnl,
            "trade_count": len(trades),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "avg_score": avg_score
        }
        
        db = await get_db()
        try:
            # Upsert wallet
            await db.execute(
                """
                INSERT INTO wallets (address, total_trades, total_volume, risk_score, analysis_json, last_scanned)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    total_trades = excluded.total_trades,
                    total_volume = excluded.total_volume,
                    risk_score = excluded.risk_score,
                    analysis_json = excluded.analysis_json,
                    last_scanned = excluded.last_scanned
                """,
                (
                    wallet, 
                    len(trades), 
                    total_vol, 
                    avg_score, 
                    json.dumps(analysis_data),
                    datetime.now(timezone.utc).isoformat()
                )
            )
            await db.commit()
            logger.info("Analyzed %s: WinRate=%.2f, Score=%.2f, PnL=$%.0f", wallet, win_rate, avg_score, total_profit)
        finally:
            await db.close()

        # 6. Generate Alerts if Suspicious
        # Lower threshold to 15 temporarily to catch the standard 20.0 score wallets
        ALERT_THRESHOLD = 15.0 
        
        if avg_score >= ALERT_THRESHOLD and trades:
            # Alert on the MOST RECENT trade to populate "Live Feed"
            latest_trade = trades[0] # trades are ordered by timestamp DESC
            
            # Create a ScoringResult object for the alert
            from app.services.scoring import ScoringResult
            
            # We use the breakdown from the latest trade or a summary
            result = ScoringResult(
                score=avg_score,
                historical_win_rate=win_rate,
                rapid_profit=0.0, # Placeholder
                volume_anomaly=0.0,
                topic_concentration=0.0,
                market_timing=0.0,
                wallet_freshness=0.0
            )
            
            await self._persist_alert(wallet, latest_trade, result)


    async def _persist_alert(
        self,
        wallet: str,
        trade: dict,
        result: Any, # ScoringResult
    ) -> None:
        """Store an alert in the database."""
        # Check if alert already exists for this trade/wallet combo to avoid spam
        # But for 'Live Feed' we might want updates. 
        # For now, let's allow latest-trade updates.
        
        alert_data = {
            "wallet_address": wallet,
            "market_id": trade.get("conditionId", ""),
            "condition_id": trade.get("conditionId", ""),
            "suspicion_score": result.score,
            "factors_json": json.dumps(result.to_dict()),
            "market_question": trade.get("title", "") or trade.get("marketQuestion", ""),
            "market_slug": trade.get("slug", ""),
            "market_end_date": None, # Could fetch if needed
            "trade_size": trade.get("size", 0),
            "trade_side": trade.get("side", ""),
            "tx_hash": trade.get("transactionHash", ""),
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
            # logger.info("Generated alert for %s (Score: %.1f)", wallet, result.score)
        except Exception as e:
            logger.error("Failed to persist alert: %s", e)
        finally:
            await db.close()
