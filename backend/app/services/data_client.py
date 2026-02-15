"""Data API client – historical trade data from Polymarket."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import (
    DATA_API_BASE,
    DATA_API_PAGE_SIZE,
    HTTP_TIMEOUT,
    SCAN_MAX_PAGES,
)

logger = logging.getLogger(__name__)


class DataClient:
    """Async client for the Polymarket Data API (``data-api.polymarket.com``)."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=DATA_API_BASE,
            timeout=HTTP_TIMEOUT,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Core trade fetching
    # ------------------------------------------------------------------

    async def fetch_trades(
        self,
        *,
        limit: int = DATA_API_PAGE_SIZE,
        offset: int = 0,
        before: int | None = None,
        after: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch the global trade feed.

        The Data API's filter parameters (``market``, ``asset_id``,
        ``conditionId``) were found to be **non-functional** during
        live testing – they return the global feed regardless of the
        filter value.  Per-market and per-wallet filtering must be
        done client-side.
        """
        params: dict[str, Any] = {"limit": limit}
        if offset:
            params["offset"] = offset
        if before is not None:
            params["before"] = before
        if after is not None:
            params["after"] = after

        resp = await self._client.get("/trades", params=params)
        if resp.status_code == 400:
            logger.warning("Data API returned 400 (offset=%s) – stopping pagination", offset)
            return []
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Per-market trades  (client-side filter)
    # ------------------------------------------------------------------

    async def fetch_market_trades(
        self,
        condition_id: str,
        *,
        max_pages: int = 20,
        after: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch trades for a specific market identified by *condition_id*.

        Because the Data API ignores server-side filter params, we
        paginate the global feed and filter client-side by matching
        the ``conditionId`` field in each trade record.

        To bound the work, we stop after *max_pages* pages or when
        the stream runs out.
        """
        matched: list[dict[str, Any]] = []

        for page in range(max_pages):
            batch = await self.fetch_trades(
                limit=DATA_API_PAGE_SIZE,
                offset=page * DATA_API_PAGE_SIZE,
                after=after,
            )
            if not batch:
                break

            for trade in batch:
                if trade.get("conditionId") == condition_id:
                    matched.append(trade)

            if len(batch) < DATA_API_PAGE_SIZE:
                break

        return matched

    # ------------------------------------------------------------------
    # Per-wallet trades  (client-side filter)
    # ------------------------------------------------------------------

    async def fetch_wallet_trades(
        self,
        proxy_wallet: str,
        *,
        max_pages: int = 20,
        after: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch all trades for a specific *proxy_wallet* address.

        Same client-side filtering approach as :meth:`fetch_market_trades`.
        """
        wallet_lower = proxy_wallet.lower()
        matched: list[dict[str, Any]] = []

        for page in range(max_pages):
            batch = await self.fetch_trades(
                limit=DATA_API_PAGE_SIZE,
                offset=page * DATA_API_PAGE_SIZE,
                after=after,
            )
            if not batch:
                break

            for trade in batch:
                if trade.get("proxyWallet", "").lower() == wallet_lower:
                    matched.append(trade)

            if len(batch) < DATA_API_PAGE_SIZE:
                break

        return matched

    # ------------------------------------------------------------------
    # Recent trades (global feed, for scanning)
    # ------------------------------------------------------------------

    async def fetch_recent_trades(
        self,
        since_timestamp: int,
        *,
        max_pages: int = SCAN_MAX_PAGES,
    ) -> list[dict[str, Any]]:
        """
        Fetch all trades since *since_timestamp* (unix epoch).

        Paginates forward through the global feed until trades older
        than the cutoff are encountered or pages are exhausted.
        """
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

            # If some trades are older than cutoff, we've gone far enough
            if len(recent) < len(batch):
                break

            if len(batch) < DATA_API_PAGE_SIZE:
                break

        return all_trades
