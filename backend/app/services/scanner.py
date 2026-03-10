"""
Scanner orchestrator — Market-first discovery.

Two scanning modes:
  1. Market-first scan (NEW, primary):
     - Fetches interesting markets from Gamma API (geopolitical, political)
     - For each market, fetches ALL trades via server-side `market=` filter
     - Aggregates per-wallet USDC volume
     - Saves trades + identifies wallets for deep analysis

  2. Legacy global-feed scan (kept for backward compat):
     - Fetches recent trades from the global feed
     - Filters by market type and size
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.core.config import (
    MIN_TRADE_SIZE,
    SCAN_LOOKBACK_HOURS,
    SCAN_MARKET_HOURS_AHEAD,
    SCAN_MARKET_MIN_VOLUME,
    SCAN_MARKET_MAX_PAGES,
    MIN_POSITION_SIZE,
)
from app.core.database import get_db
from app.core.monitor import monitor
from app.services.data_client import DataClient
from app.services.gamma_client import GammaClient
from app.services.market_classifier import classify_market
from app.services.polygonscan import PolygonscanClient

logger = logging.getLogger(__name__)


class Scanner:
    """Main scanning orchestrator — market-first discovery."""

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
    # PRIMARY: Market-first scan
    # ------------------------------------------------------------------

    async def run_scan(
        self,
        lookback_hours: int = SCAN_LOOKBACK_HOURS,
    ) -> dict[str, int]:
        """
        Market-first scan:
        1. Fetch active markets of interest (geopolitical, political, etc.)
        2. For each market, fetch all trades via server-side market= filter
        3. Save trades and identify wallet candidates for deep analysis
        """
        logger.info("═══ Starting market-first scan ═══")
        monitor.update("Fetching Interesting Markets")

        # 1. Fetch interesting markets from Gamma API
        try:
            markets = await self.gamma.fetch_expiring_markets(
                hours_ahead=SCAN_MARKET_HOURS_AHEAD,
                min_volume=SCAN_MARKET_MIN_VOLUME,
            )
        except Exception as e:
            logger.error("Failed to fetch markets: %s", e)
            markets = []

        if not markets:
            logger.info("No interesting markets found")
            return {"trades_processed": 0, "wallet_candidates": 0}

        # 2. Filter to scannable markets (skip crypto/sports/entertainment)
        scannable = []
        for m in markets:
            slug = m.get("slug", "")
            question = m.get("question", "")
            cls = classify_market(slug, question)
            if cls.should_scan:
                scannable.append(m)

        logger.info(
            "Found %d scannable markets out of %d total",
            len(scannable), len(markets),
        )

        if not scannable:
            logger.info("No scannable markets after filtering")
            return {"trades_processed": 0, "wallet_candidates": 0}

        # 3. For each market, fetch trades and save them
        cutoff_ts = int(datetime.now(timezone.utc).timestamp() - (lookback_hours * 3600))
        seen_hashes = await self._get_seen_tx_hashes()
        total_saved = 0
        wallet_candidates: set[str] = set()
        
        # Sort markets by volume descending instead of resolving soonest
        # so we always prioritize the biggest markets
        scannable.sort(key=lambda m: m.get("volumeNum", 0), reverse=True)

        for i, market in enumerate(scannable[:50]):  # Cap at 50 highest volume markets per cycle
            condition_id = market.get("conditionId", "")
            question = market.get("question", "")
            slug = market.get("slug", "")

            if not condition_id:
                continue

            monitor.update(
                f"Scanning Market ({i+1}/{min(len(scannable), 50)})",
                stats={"market": question[:60]},
            )

            try:
                trades = await self.data.fetch_market_trades(
                    condition_id, max_pages=SCAN_MARKET_MAX_PAGES,
                )
            except Exception as e:
                logger.error("Failed to scan market %s: %s", condition_id[:16], e)
                continue

            if not trades:
                continue

            # Sanitize + dedup + aggregate
            new_trades = []
            wallet_volumes: dict[str, float] = defaultdict(float)

            for t in trades:
                # Sanitize types
                try:
                    t["size"] = float(t.get("size", 0))
                    t["price"] = float(t.get("price", 0))
                    trade_ts = int(t.get("timestamp", 0))
                except (ValueError, TypeError):
                    t["size"] = 0.0
                    t["price"] = 0.0
                    trade_ts = 0

                if trade_ts and trade_ts < cutoff_ts:
                    continue

                # Calculate USDC value (size * price)
                usdc_val = t["size"] * t["price"]

                # Track per-wallet USDC volume
                wallet = t.get("proxyWallet", "")
                if wallet:
                    wallet = wallet.lower()
                    wallet_volumes[wallet] += usdc_val

                # Dedup
                tx = t.get("transactionHash")
                if tx and tx not in seen_hashes:
                    t["_usdc_size"] = usdc_val
                    t["_slug"] = slug
                    t["_question"] = question
                    new_trades.append(t)
                    seen_hashes.add(tx)

            # Save new trades
            if new_trades:
                await self._save_processed_trades(new_trades)
                total_saved += len(new_trades)

            # Identify wallet candidates (those with notable USDC positions)
            for wallet, vol in wallet_volumes.items():
                if vol >= MIN_POSITION_SIZE:
                    wallet_candidates.add(wallet)

            logger.info(
                "Market '%s': %d trades, %d new, %d notable wallets",
                question[:40], len(trades), len(new_trades),
                sum(1 for v in wallet_volumes.values() if v >= MIN_POSITION_SIZE),
            )

            # Rate limit between markets
            await asyncio.sleep(0.3)

        logger.info(
            "Market-first scan complete: %d trades saved, %d wallet candidates",
            total_saved, len(wallet_candidates),
        )
        return {
            "trades_processed": total_saved,
            "wallet_candidates": len(wallet_candidates),
        }

    # ------------------------------------------------------------------
    # Historical Scan (Whale Watching) — kept for backward compat
    # ------------------------------------------------------------------

    async def scan_history(
        self,
        lookback_pages: int = 1000,
        min_size: float = MIN_TRADE_SIZE,
    ) -> int:
        """Backfill trades by scanning the global feed."""
        monitor.update("Running Historical Scan", stats={"pages": lookback_pages})
        logger.info("Starting historical scan (pages=%d)", lookback_pages)

        seen_hashes = await self._get_seen_tx_hashes()
        total_saved = 0
        batch_size = 100

        for page in range(lookback_pages):
            try:
                trades = await self.data.fetch_trades(
                    limit=batch_size,
                    offset=page * batch_size,
                )
            except Exception as e:
                logger.error("Historical page %d failed: %s", page, e)
                continue

            if not trades:
                break

            valid_trades = []
            for t in trades:
                try:
                    t["size"] = float(t.get("size", 0))
                    t["price"] = float(t.get("price", 0))
                except (ValueError, TypeError):
                    t["size"] = 0.0
                    t["price"] = 0.0

                usdc_val = t["size"] * t["price"]
                if usdc_val >= min_size:
                    tx = t.get("transactionHash")
                    if tx and tx not in seen_hashes:
                        t["_usdc_size"] = usdc_val
                        valid_trades.append(t)
                        seen_hashes.add(tx)

            if valid_trades:
                await self._save_processed_trades(valid_trades)
                total_saved += len(valid_trades)

            if page % 10 == 0:
                monitor.update("Historical Scan", stats={"page": page, "saved": total_saved})
                await asyncio.sleep(0.1)

        logger.info("Historical scan complete: %d trades saved", total_saved)
        return total_saved

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_seen_tx_hashes(self) -> set[str]:
        db = await get_db()
        try:
            cursor = await db.execute("SELECT tx_hash FROM trades WHERE tx_hash IS NOT NULL")
            rows = await cursor.fetchall()
            return {row[0] for row in rows}
        finally:
            await db.close()

    async def _save_processed_trades(self, trades: list[dict[str, Any]]) -> None:
        if not trades:
            return
        db = await get_db()
        try:
            await db.executemany(
                """
                INSERT OR IGNORE INTO trades
                    (condition_id, market_slug, proxy_wallet, side, size,
                     usdc_size, price, outcome, timestamp, tx_hash, market_question)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        t.get("conditionId", ""),
                        t.get("_slug", t.get("slug", "")),
                        (t.get("proxyWallet", "") or "").lower(),
                        t.get("side", ""),
                        t.get("size", 0),
                        t.get("_usdc_size", t.get("size", 0) * t.get("price", 0)),
                        t.get("price", 0),
                        t.get("outcome", ""),
                        t.get("timestamp", 0),
                        t.get("transactionHash", ""),
                        t.get("_question", t.get("title", "")),
                    )
                    for t in trades
                    if t.get("transactionHash")
                ],
            )
            await db.commit()
        finally:
            await db.close()
