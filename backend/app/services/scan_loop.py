"""
Background scan loop — runs the scanner continuously in a background
asyncio task, sleeping between cycles.

Each cycle:
  1. Fetches trades (Scanner)
  2. Analyzes accounts (AccountAnalyzer)
  3. Sleeps SCAN_INTERVAL_SECONDS before repeating

The loop is started inside the FastAPI lifespan so it runs as long as
the server is up.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import SCAN_INTERVAL_SECONDS
from app.services.scanner import Scanner
from app.services.account_analyzer import AccountAnalyzer

logger = logging.getLogger(__name__)


class ScanLoop:
    """Manages the continuous background scanning task."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._scanner: Scanner | None = None
        self._analyzer: AccountAnalyzer | None = None
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
        print("DEBUG: ScanLoop task created") # Direct print to stdout
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
        
        # Close resources
        if self._scanner:
            await self._scanner.close()
            self._scanner = None
        if self._analyzer:
            await self._analyzer.close()
            self._analyzer = None
            
        logger.info("Background scan loop stopped")

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        """Run scan cycles forever until stopped."""
        cycle = 0
        from app.core.monitor import monitor # Import here to avoid circular imports if any
        
        while self._running:
            cycle += 1
            monitor.update("Idle", stats={"loop_cycle": cycle, "scan_interval": SCAN_INTERVAL_SECONDS})
            try:
                if self._scanner is None:
                    self._scanner = Scanner()
                if self._analyzer is None:
                    # Provide shared clients to analyzer if needed, or let it create its own.
                    # Here we pass the scanner's clients to reuse connections.
                    self._analyzer = AccountAnalyzer(
                        data=self._scanner.data, 
                        gamma=self._scanner.gamma,
                        polygonscan=self._scanner.polygonscan
                    )

                logger.info("═══ Scan cycle %d starting ═══", cycle)
                
                # 1. Ingest new trades
                await self._scanner.run_scan()
                
                # 2. Analyze all accounts
                await self._analyzer.analyze_all_wallets()

                logger.info("═══ Scan cycle %d done ═══", cycle)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scan cycle %d failed — will retry", cycle)

            # Sleep between cycles
            try:
                # User request: "looking for new accounts" not "sleeping"
                monitor.update("Searching for new targets...", stats={"next_scan_in": SCAN_INTERVAL_SECONDS})
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break


# Module-level singleton for easy access
scan_loop = ScanLoop()
