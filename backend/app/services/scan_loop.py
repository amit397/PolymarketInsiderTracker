"""
Background scan loop — runs the scanner continuously in a background
asyncio task, sleeping between cycles.

Each cycle:
  1. Fetches up to 3,000 trades from the Data API
  2. Deduplicates against already-processed tx_hashes in the DB
  3. Classifies, filters, scores, and persists alerts
  4. Sleeps SCAN_INTERVAL_SECONDS before repeating

The loop is started inside the FastAPI lifespan so it runs as long as
the server is up.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import SCAN_INTERVAL_SECONDS
from app.services.scanner import Scanner

logger = logging.getLogger(__name__)


class ScanLoop:
    """Manages the continuous background scanning task."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._scanner: Scanner | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background scan loop (call once at startup)."""
        if self._task is not None:
            logger.warning("Scan loop already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="scan-loop")
        logger.info(
            "Background scan loop started (interval=%ds)",
            SCAN_INTERVAL_SECONDS,
        )

    async def stop(self) -> None:
        """Gracefully stop the scan loop (call at shutdown)."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._scanner:
            await self._scanner.close()
            self._scanner = None
        logger.info("Background scan loop stopped")

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        """Run scan cycles forever until stopped."""
        cycle = 0
        while self._running:
            cycle += 1
            try:
                if self._scanner is None:
                    self._scanner = Scanner()

                logger.info("═══ Scan cycle %d starting ═══", cycle)
                alerts = await self._scanner.run_scan()
                logger.info(
                    "═══ Scan cycle %d done — %d new alerts ═══",
                    cycle, len(alerts),
                )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scan cycle %d failed — will retry", cycle)

            # Sleep between cycles
            try:
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break


# Module-level singleton for easy access
scan_loop = ScanLoop()
