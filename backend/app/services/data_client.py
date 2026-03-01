"""Data API client – historical trade data from Polymarket."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import (
    DATA_API_BASE,
    DATA_API_PAGE_SIZE,
    SCAN_MAX_PAGES,
)

logger = logging.getLogger(__name__)


class DataClient:
    """Async client for the Polymarket Data API (``data-api.polymarket.com``)."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=DATA_API_BASE,
            timeout=30.0,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Core trade fetching (global feed — kept for backward compat)
    # ------------------------------------------------------------------

    async def fetch_trades(
        self,
        *,
        limit: int = DATA_API_PAGE_SIZE,
        offset: int = 0,
        before: int | None = None,
        after: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch the global trade feed."""
        params: dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset
        if before is not None:
            params["before"] = before
        if after is not None:
            params["after"] = after

        resp = await self._client.get("/trades", params=params)
        if resp.status_code == 400:
            logger.warning("Data API returned 400 (offset=%s) – stopping", offset)
            return []
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Per-market trades — server-side filter via `market=` parameter
    # ------------------------------------------------------------------

    async def fetch_market_trades(
        self,
        condition_id: str,
        *,
        max_pages: int = SCAN_MAX_PAGES,
    ) -> list[dict[str, Any]]:
        """
        Fetch ALL trades for a specific market using server-side filtering.
        
        Uses the ``market`` query parameter which accepts a conditionId
        and returns only trades in that market (confirmed working via
        live API testing).
        """
        matched: list[dict[str, Any]] = []

        for page in range(max_pages):
            params: dict[str, Any] = {
                "limit": DATA_API_PAGE_SIZE,
                "market": condition_id,
            }
            if page > 0:
                params["offset"] = page * DATA_API_PAGE_SIZE

            try:
                resp = await self._client.get("/trades", params=params)
                if resp.status_code == 400:
                    break
                resp.raise_for_status()
                batch = resp.json()
            except Exception as e:
                logger.error("Failed to fetch market trades page %d: %s", page, e)
                break

            if not batch:
                break

            matched.extend(batch)

            if len(batch) < DATA_API_PAGE_SIZE:
                break

        logger.info(
            "Fetched %d trades for market %s (%d pages)",
            len(matched), condition_id[:16], page + 1,
        )
        return matched

    # ------------------------------------------------------------------
    # Per-wallet trades — server-side filter via `user=` parameter
    # ------------------------------------------------------------------

    async def fetch_wallet_trades(
        self,
        proxy_wallet: str,
        *,
        max_pages: int = 20,
        after: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch all trades for a specific wallet using server-side filtering.
        
        Uses the ``user`` query parameter (confirmed working via live
        API testing). This replaces the old client-side filtering approach
        that iterated the entire global feed.
        """
        matched: list[dict[str, Any]] = []

        for page in range(max_pages):
            params: dict[str, Any] = {
                "limit": DATA_API_PAGE_SIZE,
                "user": proxy_wallet,
            }
            if page > 0:
                params["offset"] = page * DATA_API_PAGE_SIZE
            if after is not None:
                params["after"] = after

            try:
                resp = await self._client.get("/trades", params=params)
                if resp.status_code == 400:
                    break
                resp.raise_for_status()
                batch = resp.json()
            except Exception as e:
                logger.error("Failed to fetch wallet trades page %d: %s", page, e)
                break

            if not batch:
                break

            matched.extend(batch)

            if len(batch) < DATA_API_PAGE_SIZE:
                break

        return matched

    # ------------------------------------------------------------------
    # Activity feed — includes usdcSize + redemptions
    # ------------------------------------------------------------------

    async def fetch_activity(
        self,
        proxy_wallet: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """
        Fetch activity (trades + redemptions) for a wallet.
        
        The activity endpoint provides ``usdcSize`` (actual USD value)
        alongside ``size`` (shares), plus REDEEM and REWARD events.
        """
        try:
            resp = await self._client.get(
                "/activity",
                params={"user": proxy_wallet, "limit": limit},
            )
            if resp.status_code != 200:
                return []
            return resp.json()
        except Exception as e:
            logger.warning("Failed to fetch activity for %s: %s", proxy_wallet, e)
            return []

    # ------------------------------------------------------------------
    # Recent trades (global feed, for scanning — kept for backward compat)
    # ------------------------------------------------------------------

    async def fetch_recent_trades(
        self,
        since_timestamp: int,
        *,
        max_pages: int = SCAN_MAX_PAGES,
    ) -> list[dict[str, Any]]:
        """Fetch all trades since *since_timestamp* (unix epoch)."""
        all_trades: list[dict[str, Any]] = []

        for page in range(max_pages):
            batch = await self.fetch_trades(
                limit=DATA_API_PAGE_SIZE,
                offset=page * DATA_API_PAGE_SIZE,
            )
            if not batch:
                break

            recent = [t for t in batch if t.get("timestamp", 0) >= since_timestamp]
            all_trades.extend(recent)

            if len(recent) < len(batch):
                break

            if len(batch) < DATA_API_PAGE_SIZE:
                break

        return all_trades
