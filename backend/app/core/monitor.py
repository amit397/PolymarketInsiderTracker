from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MonitorState:
    status: str = "Idle"
    current_wallet: str | None = None
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stats: dict[str, Any] = field(default_factory=dict)


class AnalysisMonitor:
    """Singleton to track real-time analysis status."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AnalysisMonitor, cls).__new__(cls)
            cls._instance._state = MonitorState()
        return cls._instance

    def update(self, status: str, wallet: str | None = None, stats: dict | None = None) -> None:
        """Update the current monitoring state."""
        self._state.status = status
        if wallet is not None:
            self._state.current_wallet = wallet
        if stats:
            self._state.stats.update(stats)
        self._state.last_updated = datetime.now(timezone.utc).isoformat()
        
        # logger.info("Monitor Update: %s (Wallet: %s)", status, wallet)

    def get_status(self) -> dict[str, Any]:
        """Return the current state as a dict."""
        return asdict(self._state)


# Global instance
monitor = AnalysisMonitor()
