"""Gamma API client – market metadata, profiles, expiring markets."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import (
    GAMMA_API_BASE,
    HTTP_TIMEOUT,
    SHORT_DATED_MIN_VOLUME,
)


class GammaClient:
    """Async client for the Polymarket Gamma API."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=GAMMA_API_BASE,
            timeout=HTTP_TIMEOUT,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Markets
    # ------------------------------------------------------------------

    async def fetch_markets(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        closed: bool = False,
        tag_id: str | None = None,
        slug: str | None = None,
        end_date_min: str | None = None,
        end_date_max: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch paginated market metadata."""
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "closed": str(closed).lower(),
        }
        if tag_id:
            params["tag_id"] = tag_id
        if slug:
            params["slug"] = slug
        if end_date_min:
            params["end_date_min"] = end_date_min
        if end_date_max:
            params["end_date_max"] = end_date_max

        resp = await self._client.get("/markets", params=params)
        resp.raise_for_status()
        return resp.json()

    async def fetch_market_by_id(self, market_id: str) -> dict[str, Any] | None:
        """Fetch a single market by its Gamma ID or condition_id."""
        if market_id.startswith("0x"):
            # It's a conditionId, must use the query parameter
            resp = await self._client.get("/markets", params={"condition_id": market_id})
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return data[0]
            return None
            
        # It's an internal integer ID
        resp = await self._client.get(f"/markets/{market_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Expiring markets  (short-dated contracts feature)
    # ------------------------------------------------------------------

    async def fetch_expiring_markets(
        self,
        hours_ahead: int = 168,
        min_volume: float = SHORT_DATED_MIN_VOLUME,
    ) -> list[dict[str, Any]]:
        """
        Fetch active markets resolving within *hours_ahead* hours.

        Uses the Gamma API ``end_date_min`` / ``end_date_max`` query
        parameters (confirmed working via live testing).  Low‑volume
        markets are filtered client‑side.

        Returns markets sorted by ``endDateIso`` ascending (soonest first).
        """
        now = datetime.now(timezone.utc)
        end_min = now.strftime("%Y-%m-%d")
        end_max = (now + timedelta(hours=hours_ahead)).strftime("%Y-%m-%d")

        all_markets: list[dict[str, Any]] = []
        offset = 0

        while True:
            batch = await self.fetch_markets(
                limit=100,
                offset=offset,
                closed=False,
                end_date_min=end_min,
                end_date_max=end_max,
            )
            if not batch:
                break
            all_markets.extend(batch)
            if len(batch) < 100:
                break
            offset += 100

        # Client-side volume filter
        filtered = [
            m for m in all_markets
            if (m.get("volumeNum") or 0) >= min_volume
        ]

        # Sort by end date ascending (soonest first)
        filtered.sort(key=lambda m: m.get("endDateIso", "9999-12-31"))
        return filtered

    # ------------------------------------------------------------------
    # Tags / categories
    # ------------------------------------------------------------------

    async def fetch_tags(self) -> list[dict[str, Any]]:
        """Fetch available market tags/categories."""
        resp = await self._client.get("/tags")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Public profiles
    # ------------------------------------------------------------------

    async def fetch_public_profile(self, address: str) -> dict[str, Any] | None:
        """Fetch public profile info for a wallet address."""
        resp = await self._client.get(
            "/public-profile",
            params={"address": address},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        # The endpoint may return a list or a single dict
        if isinstance(data, list):
            return data[0] if data else None
        return data
