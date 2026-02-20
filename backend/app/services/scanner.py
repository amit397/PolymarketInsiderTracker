"""
Scanner orchestrator – fetches recent trades, filters, deduplicates,
and saves them to the database.

Scoring and analysis are handled by AccountAnalyzer in a separate pass.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from app.core.config import (
    MIN_TRADE_SIZE,
    SCAN_LOOKBACK_HOURS,
)
from app.core.database import get_db
from app.core.monitor import monitor
from app.services.data_client import DataClient
from app.services.gamma_client import GammaClient
from app.services.market_classifier import classify_market
from app.services.polygonscan import PolygonscanClient

logger = logging.getLogger(__name__)


class Scanner:
    """Main scanning orchestrator — ingests trades only."""

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
    # Historical Scan (Whale Watching)
    # ------------------------------------------------------------------

    async def scan_history(
        self,
        lookback_pages: int = 1000,
        min_size: float = MIN_TRADE_SIZE,
    ) -> int:
        """
        Backfill trades by scanning backwards in the global feed.
        Filters for large trades only ($10K+) to populate the database.
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
            try:
                trades = await self.data.fetch_trades(
                    limit=batch_size,
                    offset=page * batch_size
                )
            except Exception as e:
                logger.error("Failed to fetch historical page %d: %s", page, e)
                continue

            if not trades:
                logger.info("Historical scan ended early at page %d (no data)", page)
                break

            # Filter: sanitize, enforce min size, dedup
            valid_trades = []
            for t in trades:
                try:
                    size = float(t.get("size", 0))
                    t["size"] = size
                except (ValueError, TypeError):
                    t["size"] = 0.0

                if t["size"] >= min_size:
                    tx = t.get("transactionHash")
                    if tx and tx not in seen_hashes:
                        valid_trades.append(t)
                        seen_hashes.add(tx)

            if valid_trades:
                await self._save_processed_trades(valid_trades)
                total_saved += len(valid_trades)

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
        Scan recent trades, filter, deduplicate, and persist.

        Filters applied:
          1. Market type — skip crypto-price, sports, entertainment
          2. Trade size — skip trades under MIN_TRADE_SIZE ($10,000)
          3. Deduplication — skip already-seen tx hashes

        Returns empty list (scoring is handled by AccountAnalyzer).
        """
        since_ts = int(time.time()) - (lookback_hours * 3600)
        logger.info("Starting scan – trades since %s", since_ts)
        monitor.update("Fetching Recent Trades", stats={"lookback_hours": lookback_hours})

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

        # 2. Dedup: skip trades already processed (by tx_hash)
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

        # 3. Filter: market type (skip crypto/sports/entertainment)
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

        # 4. Filter: minimum trade size ($10,000)
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

        # 5. Save all filtered trades
        await self._save_processed_trades(filtered_trades)
        logger.info("Ingestion complete – %d trades saved", len(filtered_trades))

        return []

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
