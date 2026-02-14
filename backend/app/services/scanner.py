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

from app.core.config import SCAN_LOOKBACK_HOURS
from app.core.database import get_db
from app.services.data_client import DataClient
from app.services.gamma_client import GammaClient
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

        Returns a list of alert dicts for the trades processed.
        """
        since_ts = int(time.time()) - (lookback_hours * 3600)
        logger.info("Starting scan – trades since %s", since_ts)

        # 1. Fetch recent trades
        trades = await self.data.fetch_recent_trades(since_ts)
        logger.info("Fetched %d recent trades", len(trades))

        if not trades:
            return []

        # 2. Group by wallet
        wallet_trades: dict[str, list[dict]] = defaultdict(list)
        for trade in trades:
            wallet = trade.get("proxyWallet", "")
            if wallet:
                wallet_trades[wallet].append(trade)

        # 3. Compute global trade stats (fallback for low-trade markets)
        all_sizes = [t.get("size", 0) for t in trades if t.get("size", 0) > 0]
        global_mean = statistics.mean(all_sizes) if all_sizes else 0.0
        global_std = statistics.stdev(all_sizes) if len(all_sizes) > 1 else 1.0

        # 4. Group trades by market (conditionId) for per-market stats
        market_trades: dict[str, list[float]] = defaultdict(list)
        for trade in trades:
            cid = trade.get("conditionId", "")
            size = trade.get("size", 0)
            if cid and size > 0:
                market_trades[cid].append(size)

        # 5. Score each wallet
        alerts: list[dict[str, Any]] = []

        for wallet, w_trades in wallet_trades.items():
            for trade in w_trades:
                result = await self._score_trade(
                    wallet=wallet,
                    trade=trade,
                    all_wallet_trades=w_trades,
                    market_trades=market_trades,
                    global_mean=global_mean,
                    global_std=global_std,
                )

                if result.passes_gate:
                    alert = await self._persist_alert(
                        wallet=wallet,
                        trade=trade,
                        result=result,
                    )
                    alerts.append(alert)

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
        market_trades: dict[str, list[float]],
        global_mean: float,
        global_std: float,
    ) -> ScoringResult:
        """Score a single trade for a wallet."""

        trade_size = trade.get("size", 0)
        condition_id = trade.get("conditionId", "")
        trade_ts = trade.get("timestamp", 0)
        trade_price = trade.get("price", 0)
        trade_side = trade.get("side", "BUY")

        # --- N_V: Volume Anomaly ---
        m_sizes = market_trades.get(condition_id, [])
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

        # --- N_C: Topic Concentration ---
        category_counts: dict[str, float] = defaultdict(float)
        for t in all_wallet_trades:
            slug = t.get("eventSlug", t.get("slug", "unknown"))
            category_counts[slug] += t.get("size", 0)
        nc = compute_topic_concentration(dict(category_counts))

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
            t.get("price", 0)
            for t in market_trades.get(condition_id, [])
            if t.get("timestamp", 0) > trade_ts
            and isinstance(t, dict)
        ]
        if subsequent_prices:
            # Use the latest price as the "after" price
            price_after = subsequent_prices[-1] if isinstance(subsequent_prices[-1], (int, float)) else 0
            nr = compute_rapid_profit(trade_price, price_after, trade_side)

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
            markets = await self.gamma.fetch_markets(limit=1)
            # Search for matching slug in recent markets
            for m in markets:
                if m.get("slug") == slug:
                    self._market_cache[slug] = m
                    return m
            self._market_cache[slug] = None
            return None
        except Exception:
            self._market_cache[slug] = None
            return None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

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
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO alerts
                    (wallet_address, market_id, condition_id, suspicion_score,
                     factors_json, market_question, market_slug, market_end_date,
                     trade_size, trade_side, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    alert["created_at"],
                ),
            )
            await db.commit()

            # Also upsert the wallet record
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
            await db.commit()
        finally:
            await db.close()

        return alert
