"""
Scanner orchestrator – fetches recent trades, scores wallets,
and generates alerts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.core.config import (
    MIN_TRADE_SIZE,
    SCAN_LOOKBACK_HOURS,
    WALLET_CONCENTRATION_THRESHOLD,
)
from app.core.database import get_db
from app.services.data_client import DataClient
from app.services.gamma_client import GammaClient
from app.services.market_classifier import classify_market
from app.services.polygonscan import PolygonscanClient
from app.services.scoring import (
    ScoringResult,
    compute_market_timing,
    compute_rapid_profit,
    compute_suspicion_score,
    compute_topic_concentration,
    compute_volume_anomaly,
    compute_wallet_freshness,
)
from app.services.pnl_calculator import PnLCalculator

logger = logging.getLogger(__name__)


from app.core.monitor import monitor

class Scanner:
    """Main scanning orchestrator."""

    def __init__(
        self,
        gamma: GammaClient | None = None,
        data: DataClient | None = None,
        polygonscan: PolygonscanClient | None = None,
    ) -> None:
        self.gamma = gamma or GammaClient()
        self.data = data or DataClient()
        self.polygonscan = polygonscan or PolygonscanClient()
        self.pnl_calculator = PnLCalculator()
        self._owns_clients = gamma is None

    async def close(self) -> None:
        if self._owns_clients:
            await self.gamma.close()
            await self.data.close()
            await self.polygonscan.close()

    # ------------------------------------------------------------------
    # Historical Scan (Whale Watching)
    # ------------------------------------------------------------------

    async def scan_history(
        self,
        lookback_pages: int = 1000,
        min_size: float = 10000.0,
    ) -> int:
        """
        Backfill trades by scanning backwards in the global feed.
        Filters for large trades only to populate the database with "whales".
        Returns number of trades saved.
        """
        monitor.update("Running Historical Scan", stats={"pages": lookback_pages})
        logger.info(
            "Starting historical whale scan (pages=%d, min_size=%.0f)",
            lookback_pages, min_size
        )
        
        seen_hashes = await self._get_seen_tx_hashes()
        total_saved = 0
        batch_size = 100
        
        for page in range(lookback_pages):
            # Fetch batch
            try:
                trades = await self.data.fetch_trades(
                    limit=batch_size, 
                    offset=page * batch_size
                )
            except Exception as e:
                logger.error("Failed to fetch historical page %d: %s", page, e)
                # Don't abort, just skip
                continue
            
            if not trades:
                logger.info("Historical scan ended early at page %d (no data)", page)
                break
                
            # Filter
            valid_trades = []
            for t in trades:
                # Sanitize
                try:
                    size = float(t.get("size", 0))
                    t["size"] = size
                except (ValueError, TypeError):
                    t["size"] = 0.0
                    
                # Check size and dedup
                if t["size"] >= min_size:
                     tx = t.get("transactionHash")
                     if tx and tx not in seen_hashes:
                         valid_trades.append(t)
                         seen_hashes.add(tx) # update local set
            
            # Save
            if valid_trades:
                await self._save_processed_trades(valid_trades)
                total_saved += len(valid_trades)
                
            # Progress log every 10 pages
            if page % 10 == 0:
                monitor.update("Historical Scan", stats={"page": page, "total_saved": total_saved})
                logger.info("Historical scan: Page %d/%d, Saved %d so far", page, lookback_pages, total_saved)
                await asyncio.sleep(0.1)
                
        logger.info("Historical scan complete. Total NEW trades saved: %d", total_saved)
        return total_saved

    # ------------------------------------------------------------------
    # Main scan entry point
    # ------------------------------------------------------------------

    async def run_scan(
        self,
        lookback_hours: int = SCAN_LOOKBACK_HOURS,
    ) -> list[dict[str, Any]]:
        """
        Scan recent trades, score each unique wallet, and persist
        alerts for wallets that pass the alert gate.

        Filters applied:
          1. Market type — skip crypto-price, sports, entertainment
          2. Trade size — skip trades under MIN_TRADE_SIZE ($1,000)
          3. Wallet concentration — only flag wallets with ≥85%
             volume in the scored market

        Returns a list of alert dicts for the trades processed.
        """
        since_ts = int(time.time()) - (lookback_hours * 3600)
        logger.info("Starting scan – trades since %s", since_ts)
        monitor.update("Fetching Recent Trades", stats={"lookback_hours": lookback_hours})

        # 1. Fetch recent trades
        # 1. Fetch recent trades
        trades = await self.data.fetch_recent_trades(since_ts)
        logger.info("Fetched %d raw trades", len(trades))

        # Sanitize types (API sometimes returns strings)
        for t in trades:
            try:
                t["size"] = float(t.get("size", 0))
                t["price"] = float(t.get("price", 0))
            except (ValueError, TypeError):
                t["size"] = 0.0
                t["price"] = 0.0

        if not trades:
            return []

        # 1b. Dedup: skip trades already processed (by tx_hash)
        seen_hashes = await self._get_seen_tx_hashes()
        before_dedup = len(trades)
        trades = [
            t for t in trades
            if t.get("transactionHash") and t["transactionHash"] not in seen_hashes
        ]
        logger.info(
            "After dedup: %d / %d trades are new",
            len(trades), before_dedup,
        )
        if not trades:
            logger.info("No new trades – scan cycle complete")
            return []

        # 2. Filter: market type (skip crypto/sports/entertainment)
        filtered_trades: list[dict] = []
        skipped_counts: dict[str, int] = defaultdict(int)
        for trade in trades:
            slug = trade.get("slug", "")
            title = trade.get("title", "")
            cls = classify_market(slug, title)
            if cls.should_scan:
                filtered_trades.append(trade)
            else:
                skipped_counts[cls.category] += 1

        for cat, cnt in skipped_counts.items():
            logger.info("Skipped %d trades (market type: %s)", cnt, cat)
        logger.info(
            "After market-type filter: %d / %d trades remain",
            len(filtered_trades), len(trades),
        )

        # 3. Filter: minimum trade size
        size_before = len(filtered_trades)
        filtered_trades = [
            t for t in filtered_trades
            if t.get("size", 0) >= MIN_TRADE_SIZE
        ]
        logger.info(
            "After min-size filter ($%.0f): %d / %d trades remain",
            MIN_TRADE_SIZE, len(filtered_trades), size_before,
        )

        if not filtered_trades:
            logger.info("No trades passed filters – scan complete")
            return []

        # 4. Group by wallet
        wallet_trades: dict[str, list[dict]] = defaultdict(list)
        for trade in filtered_trades:
            wallet = trade.get("proxyWallet", "")
            if wallet:
                wallet_trades[wallet].append(trade)

        # 5. Compute global trade stats (fallback for low-trade markets)
        all_sizes = [t.get("size", 0) for t in filtered_trades if t.get("size", 0) > 0]
        global_mean = statistics.mean(all_sizes) if all_sizes else 0.0
        global_std = statistics.stdev(all_sizes) if len(all_sizes) > 1 else 1.0

        # 6. Group full trade dicts by market (conditionId)
        market_trades: dict[str, list[dict]] = defaultdict(list)
        for trade in filtered_trades:
            cid = trade.get("conditionId", "")
            if cid:
                market_trades[cid].append(trade)

        # 7. (Removed) Scoring is now handled by AccountAnalyzer
        # We only save the trades here.

        # 8. Save all processed trade hashes
        await self._save_processed_trades(filtered_trades)

        logger.info("Ingestion complete – %d trades saved", len(filtered_trades))
        # Return empty list as we don't generate alerts here anymore
        return []

    # ------------------------------------------------------------------
    # Per-trade scoring (Deprecated/Removed)
    # ------------------------------------------------------------------
    # The logic has been moved to AccountAnalyzer. 
    # This method is kept as a placeholder or can be removed.
    # For now, we remove it to avoid confusion.

    # ------------------------------------------------------------------
    # Market info cache
    # ------------------------------------------------------------------

    _market_cache: dict[str, dict[str, Any] | None] = {}

    async def _get_market_info(self, slug: str) -> dict[str, Any] | None:
        """Fetch and cache market metadata by slug."""
        if not slug:
            return None
        if slug in self._market_cache:
            return self._market_cache[slug]

        try:
            # Query Gamma API filtering by slug
            markets = await self.gamma.fetch_markets(limit=1, slug=slug)
            if markets:
                self._market_cache[slug] = markets[0]
                return markets[0]
            self._market_cache[slug] = None
            return None
        except Exception as e:
            logger.debug("Failed to fetch market info for slug=%s: %s", slug, e)
            self._market_cache[slug] = None
            return None

    # ------------------------------------------------------------------
    # Trade deduplication
    # ------------------------------------------------------------------

    async def _get_seen_tx_hashes(self) -> set[str]:
        """Return the set of tx_hashes already stored in the trades table."""
        db = await get_db()
        try:
            cursor = await db.execute("SELECT tx_hash FROM trades WHERE tx_hash IS NOT NULL")
            rows = await cursor.fetchall()
            return {row[0] for row in rows}
        finally:
            await db.close()

    async def _save_processed_trades(self, trades: list[dict[str, Any]]) -> None:
        """Persist processed trades so they are skipped in future cycles."""
        if not trades:
            return
        db = await get_db()
        try:
            await db.executemany(
                """
                INSERT OR IGNORE INTO trades
                    (condition_id, market_slug, proxy_wallet, side, size,
                     price, outcome, timestamp, tx_hash, market_question)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        t.get("conditionId", ""),
                        t.get("slug", ""),
                        t.get("proxyWallet", ""),
                        t.get("side", ""),
                        t.get("size", 0),
                        t.get("price", 0),
                        t.get("outcome", ""),
                        t.get("timestamp", 0),
                        t.get("transactionHash", ""),
                        t.get("title", ""),
                    )
                    for t in trades
                    if t.get("transactionHash")
                ],
            )
            await db.commit()
            logger.info("Saved %d processed trades to DB", len(trades))
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _deep_analyze_wallet(self, wallet: str) -> None:
        """
        Fetch history, score each trade, and update wallet risk profile.
        Used for deeper analysis after an alert is triggered.
        """
        try:
            # Fetch last ~200 trades (max_pages=2) for context
            history = await self.data.fetch_wallet_trades(wallet, max_pages=2)
            if not history:
                return

            # Sanitize types (same as run_scan)
            for t in history:
                try:
                    t["size"] = float(t.get("size", 0))
                    t["price"] = float(t.get("price", 0))
                except (ValueError, TypeError):
                    t["size"] = 0.0
                    t["price"] = 0.0

            # Group for context
            market_trades = defaultdict(list)
            for t in history:
                market_trades[t.get("conditionId", "")].append(t)
            
            total_vol = sum(t["size"] for t in history)
            scores = []

            for t in history:
                cid = t.get("conditionId", "")
                market_vol = sum(x["size"] for x in history if x.get("conditionId") == cid)
                
                # Reuse scoring logic
                # Lacking full market context, we pass simplified global/market stats.
                # N_V will be conservative (1.0) for sparse history.
                # N_C and N_M will be accurate.
                res = await self._score_trade(
                    wallet=wallet,
                    trade=t,
                    all_wallet_trades=history,
                    market_trades=market_trades,
                    global_mean=0,
                    global_std=1,
                    market_volume=market_vol,
                    total_wallet_volume=total_vol,
                )
                scores.append(res.score)

            if not scores:
                return

            # --- Win Rate Analysis ---
            # Fetch market info for the markets traded to see if they are resolved
            market_ids = list(market_trades.keys())
            resolved_markets = {}
            for mid in market_ids:
                 # existing cache check is inside _get_market_info but it takes slug
                 # we have conditionId (mid) here.
                 # Gamma client has fetch_market_by_id. 
                 # Let's add a helper or just use gamma directly if we have access.
                 # self.gamma.fetch_market_by_id is available.
                 try:
                     m = await self.gamma.fetch_market_by_id(mid)
                     if m:
                         resolved_markets[mid] = m
                 except Exception:
                     pass
            
            pnl_stats = self.pnl_calculator.calculate_stats(history, resolved_markets)
            win_rate = pnl_stats.get("win_rate", 0.0)
            total_wins = pnl_stats.get("wins", 0)

            avg_score = statistics.mean(scores)
            max_score = max(scores)
            suspicious_count = sum(1 for s in scores if s > 50)
            
            analysis = {
                "trades_analyzed": len(history),
                "avg_score": round(avg_score, 2),
                "max_score": round(max_score, 2),
                "suspicious_trade_count": suspicious_count,
                "win_rate": win_rate,
                "total_wins": total_wins,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Update DB
            db = await get_db()
            try:
                await db.execute(
                    """
                    UPDATE wallets 
                    SET risk_score = ?, analysis_json = ? 
                    WHERE address = ?
                    """,
                    (avg_score, json.dumps(analysis), wallet),
                )
                await db.commit()
                logger.info("Deep analysis for %s: risk_score=%.1f", wallet, avg_score)
            finally:
                await db.close()

        except Exception as e:
            logger.error("Deep analysis failed for %s: %s", wallet, e)

    async def _persist_alert(
        self,
        wallet: str,
        trade: dict[str, Any],
        result: ScoringResult,
    ) -> dict[str, Any]:
        """Store an alert in the database and return it as a dict."""
        alert = {
            "wallet_address": wallet,
            "market_id": trade.get("conditionId", ""),
            "condition_id": trade.get("conditionId", ""),
            "suspicion_score": result.score,
            "factors_json": json.dumps(result.to_dict()),
            "market_question": trade.get("title", ""),
            "market_slug": trade.get("slug", ""),
            "market_end_date": None,
            "trade_size": trade.get("size", 0),
            "trade_side": trade.get("side", ""),
            "tx_hash": trade.get("transactionHash", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        db = await get_db()
        try:
            # Upsert wallet FIRST (alerts has FK to wallets.address)
            await db.execute(
                """
                INSERT INTO wallets (address, total_trades, total_volume, last_scanned)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    total_trades = total_trades + 1,
                    total_volume = total_volume + excluded.total_volume,
                    last_scanned = excluded.last_scanned
                """,
                (wallet, trade.get("size", 0), alert["created_at"]),
            )

            # Now insert the alert
            await db.execute(
                """
                INSERT INTO alerts
                    (wallet_address, market_id, condition_id, suspicion_score,
                     factors_json, market_question, market_slug, market_end_date,
                     trade_size, trade_side, tx_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert["wallet_address"],
                    alert["market_id"],
                    alert["condition_id"],
                    alert["suspicion_score"],
                    alert["factors_json"],
                    alert["market_question"],
                    alert["market_slug"],
                    alert["market_end_date"],
                    alert["trade_size"],
                    alert["trade_side"],
                    alert["tx_hash"],
                    alert["created_at"],
                ),
            )
            await db.commit()
        finally:
            await db.close()

        # Trigger deep dive analysis
        # (This adds latency but ensures profile is updated immediately)
        await self._deep_analyze_wallet(wallet)

        return alert
