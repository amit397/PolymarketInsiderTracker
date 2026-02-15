"""
Scanner orchestrator – fetches recent trades, scores wallets,
and generates alerts.
"""

from __future__ import annotations

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

logger = logging.getLogger(__name__)


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
        self._owns_clients = gamma is None

    async def close(self) -> None:
        if self._owns_clients:
            await self.gamma.close()
            await self.data.close()
            await self.polygonscan.close()

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

        # 7. Score each wallet + check concentration
        alerts: list[dict[str, Any]] = []
        concentration_skipped = 0

        for wallet, w_trades in wallet_trades.items():
            for trade in w_trades:
                # Compute wallet's concentration in this market
                condition_id = trade.get("conditionId", "")
                market_vol = sum(
                    t.get("size", 0) for t in w_trades
                    if t.get("conditionId", "") == condition_id
                )
                total_vol = sum(t.get("size", 0) for t in w_trades)
                concentration = market_vol / total_vol if total_vol > 0 else 0

                if concentration < WALLET_CONCENTRATION_THRESHOLD:
                    concentration_skipped += 1
                    continue

                result = await self._score_trade(
                    wallet=wallet,
                    trade=trade,
                    all_wallet_trades=w_trades,
                    market_trades=market_trades,
                    global_mean=global_mean,
                    global_std=global_std,
                    market_volume=market_vol,
                    total_wallet_volume=total_vol,
                )

                if result.passes_gate:
                    alert = await self._persist_alert(
                        wallet=wallet,
                        trade=trade,
                        result=result,
                    )
                    alerts.append(alert)

        if concentration_skipped:
            logger.info(
                "Skipped %d trades (wallet concentration < %.0f%%)",
                concentration_skipped, WALLET_CONCENTRATION_THRESHOLD * 100,
            )

        # 8. Save all processed trade hashes so we never re-score them
        await self._save_processed_trades(filtered_trades)

        logger.info("Scan complete – %d alerts generated", len(alerts))
        return alerts

    # ------------------------------------------------------------------
    # Per-trade scoring
    # ------------------------------------------------------------------

    async def _score_trade(
        self,
        wallet: str,
        trade: dict[str, Any],
        all_wallet_trades: list[dict[str, Any]],
        market_trades: dict[str, list[dict]],
        global_mean: float,
        global_std: float,
        market_volume: float = 0.0,
        total_wallet_volume: float = 0.0,
    ) -> ScoringResult:
        """Score a single trade for a wallet."""

        trade_size = trade.get("size", 0)
        condition_id = trade.get("conditionId", "")
        trade_ts = trade.get("timestamp", 0)
        trade_price = trade.get("price", 0)
        trade_side = trade.get("side", "BUY")

        # --- N_V: Volume Anomaly ---
        m_trade_list = market_trades.get(condition_id, [])
        m_sizes = [t.get("size", 0) for t in m_trade_list if t.get("size", 0) > 0]
        m_count = len(m_sizes)
        m_mean = statistics.mean(m_sizes) if m_sizes else 0.0
        m_std = statistics.stdev(m_sizes) if len(m_sizes) > 1 else 0.0

        nv = compute_volume_anomaly(
            trade_size=trade_size,
            market_mean=m_mean,
            market_std=m_std,
            market_trade_count=m_count,
            global_mean=global_mean,
            global_std=global_std,
        )

        # --- N_C: Single-market concentration ---
        nc = compute_topic_concentration(market_volume, total_wallet_volume)

        # --- N_M: Market Timing ---
        nm = 0.0
        market_info = await self._get_market_info(trade.get("slug", ""))
        if market_info and market_info.get("endDate"):
            try:
                end_dt = datetime.fromisoformat(
                    market_info["endDate"].replace("Z", "+00:00")
                )
                trade_dt = datetime.fromtimestamp(trade_ts, tz=timezone.utc)
                hours_to_res = max(0, (end_dt - trade_dt).total_seconds() / 3600)
                nm = compute_market_timing(hours_to_res)
            except (ValueError, TypeError):
                pass

        # --- N_F: Wallet Freshness ---
        nf = 0.0
        age_days = await self.polygonscan.fetch_wallet_age_days(wallet)
        if age_days is not None:
            nf = compute_wallet_freshness(age_days)

        # --- N_R: Rapid Profit ---
        # Use subsequent trades in the same market as price proxy
        nr = 0.0
        subsequent_prices = [
            float(t.get("price", 0))
            for t in m_trade_list
            if isinstance(t, dict)
            and t.get("timestamp", 0) > trade_ts
            and t.get("price", 0)
        ]
        if subsequent_prices and trade_price:
            price_after = subsequent_prices[-1]
            nr = compute_rapid_profit(float(trade_price), price_after, trade_side)

        # --- Compute final score ---
        return compute_suspicion_score(
            volume_anomaly=nv,
            topic_concentration=nc,
            market_timing=nm,
            wallet_freshness=nf,
            rapid_profit=nr,
        )

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

            avg_score = statistics.mean(scores)
            max_score = max(scores)
            suspicious_count = sum(1 for s in scores if s > 50)
            
            analysis = {
                "trades_analyzed": len(history),
                "avg_score": round(avg_score, 2),
                "max_score": round(max_score, 2),
                "suspicious_trade_count": suspicious_count,
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
