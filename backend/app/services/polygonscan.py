"""Polygonscan client – wallet age lookup via first-transaction timestamp."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.config import (
    HTTP_TIMEOUT,
    POLYGONSCAN_API_BASE,
    POLYGONSCAN_API_KEY,
)

logger = logging.getLogger(__name__)


class PolygonscanClient:
    """Async client for the Polygonscan API (Polygon PoS)."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=POLYGONSCAN_API_BASE,
            timeout=HTTP_TIMEOUT,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_wallet_age_days(self, address: str) -> float | None:
        """
        Return the age of *address* in days based on its first
        transaction on Polygon.

        Returns ``None`` if the lookup fails or the wallet has no
        transactions.
        """
        if not POLYGONSCAN_API_KEY:
            logger.warning("POLYGONSCAN_API_KEY not set – wallet age unavailable")
            return None

        try:
            resp = await self._client.get(
                "",
                params={
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "page": 1,
                    "offset": 1,
                    "sort": "asc",
                    "apikey": POLYGONSCAN_API_KEY,
                },
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

            if data.get("status") != "1" or not data.get("result"):
                return None

            first_tx = data["result"][0]
            first_ts = int(first_tx.get("timeStamp", 0))
            if first_ts == 0:
                return None

            age_seconds = time.time() - first_ts
            return max(0.0, age_seconds / 86400.0)

        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            logger.warning("Polygonscan lookup failed for %s: %s", address, exc)
            return None
