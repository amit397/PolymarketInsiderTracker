"""Pydantic response/request schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Factor breakdown
# ---------------------------------------------------------------------------

class FactorBreakdown(BaseModel):
    volume_anomaly: float = 0.0
    topic_concentration: float = 0.0
    market_timing: float = 0.0
    wallet_freshness: float = 0.0
    rapid_profit: float = 0.0
    elevated_factors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    id: int | None = None
    wallet_address: str
    market_question: str | None = None
    market_slug: str | None = None
    market_end_date: str | None = None
    condition_id: str | None = None
    suspicion_score: float
    factors: FactorBreakdown
    trade_size: float | None = None
    trade_side: str | None = None
    tx_hash: str | None = None
    wallet_risk_score: float = 0.0
    created_at: str


# ---------------------------------------------------------------------------
# Wallet profile
# ---------------------------------------------------------------------------

class WalletProfile(BaseModel):
    address: str
    username: str | None = None
    first_seen: int | None = None
    total_trades: int = 0
    total_volume: float = 0.0
    risk_score: float = 0.0
    analysis: dict | None = None
    categories: dict[str, float] = Field(default_factory=dict)
    win_rate: float = 0.0
    alerts: list[AlertResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Market
# ---------------------------------------------------------------------------

class SuspiciousMarket(BaseModel):
    market_id: str
    question: str
    slug: str | None = None
    category: str | None = None
    volume: float = 0.0
    avg_suspicion_score: float = 0.0
    alert_count: int = 0


class ExpiringMarketResponse(BaseModel):
    market_id: str
    question: str
    slug: str | None = None
    end_date: str | None = None
    hours_remaining: float = 0.0
    volume: float = 0.0
    suspicious_trade_count: int = 0
    top_suspicion_score: float = 0.0
    flagged_wallets: list[str] = Field(default_factory=list)
    image: str | None = None
    event_slug: str | None = None


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    total_alerts: int = 0
    total_wallets_scanned: int = 0
    avg_score: float = 0.0
    max_score: float = 0.0
    alerts_today: int = 0


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    lookback_hours: int = Field(default=24, ge=1, le=168)


class ScanResponse(BaseModel):
    alerts_generated: int = 0
    trades_processed: int = 0
    message: str = "Scan complete"
