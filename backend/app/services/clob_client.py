"""CLOB API client – real-time prices and order book data."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import CLOB_API_BASE, HTTP_TIMEOUT


class ClobClient:
    """
    Async client for the Polymarket CLOB API.

    .. note::

        The CLOB API **requires authentication** (API key / L2 auth).
        Endpoints return HTTP 401 without valid credentials.

        For v1, the Rapid Profit factor (N_R) falls back to using
        the Data API's trade-price sequence instead of CLOB prices.
        This client is provided for future use once auth is set up.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=CLOB_API_BASE,
            timeout=HTTP_TIMEOUT,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_price(self, token_id: str) -> dict[str, Any] | None:
        """
        Fetch the current mid-price for a conditional token.

        Returns ``None`` if the endpoint is not accessible (e.g. 401).
        """
        try:
            resp = await self._client.get(
                "/price",
                params={"token_id": token_id},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError:
            return None

    async def fetch_orderbook(self, token_id: str) -> dict[str, Any] | None:
        """
        Fetch the bid/ask order book for a conditional token.

        Returns ``None`` if the endpoint is not accessible.
        """
        try:
            resp = await self._client.get(
                "/book",
                params={"token_id": token_id},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError:
            return None
