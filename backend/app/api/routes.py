"""FastAPI route definitions."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.api.schemas import (
    AlertResponse,
    DashboardStats,
    ExpiringMarketResponse,
    FactorBreakdown,
    ScanRequest,
    ScanResponse,
    SuspiciousMarket,
    WalletProfile,
)
from app.core.database import get_db
from app.services.gamma_client import GammaClient
from app.services.scanner import Scanner
from app.core.monitor import monitor # Import Monitor
from app.services.scan_loop import scan_loop # Import ScanLoop

router = APIRouter(prefix="/api")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_factors(factors_json: str) -> FactorBreakdown:
    """Parse the stored factors JSON into a FactorBreakdown."""
    try:
        data = json.loads(factors_json)
        return FactorBreakdown(
            win_rate_anomaly=data.get("win_rate_anomaly", 0),
            bet_concentration=data.get("bet_concentration", 0),
            timing_signal=data.get("timing_signal", 0),
            entry_price_edge=data.get("entry_price_edge", 0),
            account_pattern=data.get("account_pattern", 0),
            elevated_factors=data.get("elevated_factors", []),
        )
    except (json.JSONDecodeError, TypeError):
        return FactorBreakdown()


def _row_to_alert(row) -> AlertResponse:
    """Convert a DB row to an AlertResponse."""
    return AlertResponse(
        id=row["id"],
        wallet_address=row["wallet_address"],
        market_question=row["market_question"],
        market_slug=row["market_slug"],
        market_end_date=row["market_end_date"],
        condition_id=row["condition_id"],
        suspicion_score=row["suspicion_score"],
        factors=_parse_factors(row["factors_json"]),
        trade_size=row["trade_size"],
        trade_side=row["trade_side"],
        tx_hash=row["tx_hash"],
        created_at=row["created_at"],
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/alerts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/alerts", response_model=list[AlertResponse])
async def get_alerts(
    min_score: float = Query(default=0, ge=0, le=100),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Fetch recent alerts, optionally filtered by min score and category."""
    db = await get_db()
    try:
        query = "SELECT * FROM alerts WHERE suspicion_score >= ?"
        params: list = [min_score]

        if category:
            query += " AND market_slug LIKE ?"
            params.append(f"%{category}%")

        query += " ORDER BY suspicion_score DESC, created_at DESC LIMIT ?"
        params.append(limit)

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [_row_to_alert(row) for row in rows]
    finally:
        await db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/wallet/{address}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/wallet/{address}", response_model=WalletProfile)
async def get_wallet(address: str):
    """Full wallet profile with alerts and score breakdown."""
    db = await get_db()
    try:
        # Wallet info
        cursor = await db.execute(
            "SELECT * FROM wallets WHERE address = ?", (address,)
        )
        wallet_row = await cursor.fetchone()

        # Alerts for this wallet
        cursor = await db.execute(
            "SELECT * FROM alerts WHERE wallet_address = ? ORDER BY suspicion_score DESC",
            (address,),
        )
        alert_rows = await cursor.fetchall()

        categories: dict[str, float] = {}
        if wallet_row and wallet_row["categories_json"]:
            try:
                categories = json.loads(wallet_row["categories_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        analysis: dict | None = None
        if wallet_row and wallet_row["analysis_json"]:
            try:
                analysis = json.loads(wallet_row["analysis_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        return WalletProfile(
            address=address,
            username=wallet_row["username"] if wallet_row else None,
            first_seen=wallet_row["first_seen"] if wallet_row else None,
            total_trades=wallet_row["total_trades"] if wallet_row else 0,
            total_volume=wallet_row["total_volume"] if wallet_row else 0.0,
            risk_score=wallet_row["risk_score"] if wallet_row else 0.0,
            analysis=analysis,
            categories=categories,
            win_rate=analysis.get("win_rate", 0.0) if analysis else 0.0,
            alerts=[_row_to_alert(r) for r in alert_rows],
        )
    finally:
        await db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/wallet/{address}/trades
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/wallet/{address}/trades")
async def get_wallet_trades(
    address: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Paginated trade history for a wallet."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM trades WHERE proxy_wallet = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (address, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/markets/suspicious
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/markets/suspicious", response_model=list[SuspiciousMarket])
async def get_suspicious_markets(
    limit: int = Query(default=20, ge=1, le=100),
):
    """Markets ranked by average suspicion score of their traders."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT
                condition_id AS market_id,
                market_question AS question,
                market_slug AS slug,
                AVG(suspicion_score) AS avg_suspicion_score,
                COUNT(*) AS alert_count
            FROM alerts
            GROUP BY condition_id
            ORDER BY avg_suspicion_score DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            SuspiciousMarket(
                market_id=row["market_id"] or "",
                question=row["question"] or "",
                slug=row["slug"],
                avg_suspicion_score=round(row["avg_suspicion_score"], 2),
                alert_count=row["alert_count"],
            )
            for row in rows
        ]
    finally:
        await db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/markets/expiring  (short-dated contracts feature)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/markets/expiring", response_model=list[ExpiringMarketResponse])
async def get_expiring_markets(
    hours: int = Query(default=168, ge=1, le=168),
    min_score: float = Query(default=50, ge=0, le=100),
    min_volume: float = Query(default=100, ge=0),
):
    """
    Markets resolving soon with their suspicious trade data.

    Queries Gamma API for markets within the time horizon, then
    joins with the alerts table to surface suspicious activity.
    """
    gamma = GammaClient()
    try:
        expiring = await gamma.fetch_expiring_markets(
            hours_ahead=hours,
            min_volume=min_volume,
        )
    finally:
        await gamma.close()

    if not expiring:
        return []

    now = datetime.now(timezone.utc)
    results: list[ExpiringMarketResponse] = []

    db = await get_db()
    try:
        for market in expiring:
            condition_id = market.get("conditionId", "")
            end_date_str = market.get("endDate", "")

            # Calculate hours remaining
            hours_remaining = 0.0
            if end_date_str:
                try:
                    end_dt = datetime.fromisoformat(
                        end_date_str.replace("Z", "+00:00")
                    )
                    hours_remaining = max(
                        0, (end_dt - now).total_seconds() / 3600
                    )
                except ValueError:
                    pass

            # Fetch alerts for this market
            cursor = await db.execute(
                """
                SELECT wallet_address, suspicion_score
                FROM alerts
                WHERE condition_id = ? AND suspicion_score >= ?
                ORDER BY suspicion_score DESC
                """,
                (condition_id, min_score),
            )
            alert_rows = await cursor.fetchall()

            flagged = list({row["wallet_address"] for row in alert_rows})
            top_score = max(
                (row["suspicion_score"] for row in alert_rows), default=0.0
            )

            results.append(
                ExpiringMarketResponse(
                    market_id=market.get("id", ""),
                    question=market.get("question", ""),
                    slug=market.get("slug"),
                    end_date=end_date_str,
                    hours_remaining=round(hours_remaining, 1),
                    volume=market.get("volumeNum", 0),
                    suspicious_trade_count=len(alert_rows),
                    top_suspicion_score=round(top_score, 2),
                    flagged_wallets=flagged[:10],
                    image=market.get("image"),
                    event_slug=market.get("eventSlug"),
                )
            )
    finally:
        await db.close()

    # Sort by hours remaining (most urgent first)
    results.sort(key=lambda r: r.hours_remaining)
    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/stats
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/stats", response_model=DashboardStats)
async def get_stats():
    """Global dashboard statistics."""
    db = await get_db()
    try:
        row = await (
            await db.execute(
                """
                SELECT
                    COUNT(*) AS total_alerts,
                    COALESCE(AVG(suspicion_score), 0) AS avg_score,
                    COALESCE(MAX(suspicion_score), 0) AS max_score
                FROM alerts
                """
            )
        ).fetchone()

        wallets_row = await (
            await db.execute("SELECT COUNT(*) AS cnt FROM wallets")
        ).fetchone()

        today_row = await (
            await db.execute(
                "SELECT COUNT(*) AS cnt FROM alerts WHERE created_at >= date('now')"
            )
        ).fetchone()

        return DashboardStats(
            total_alerts=row["total_alerts"],
            total_wallets_scanned=wallets_row["cnt"],
            avg_score=round(row["avg_score"], 2),
            max_score=round(row["max_score"], 2),
            alerts_today=today_row["cnt"],
        )
    finally:
        await db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/insiders
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/insiders", response_model=list[WalletProfile])
async def get_insiders(
    limit: int = Query(default=50, ge=1, le=100),
    min_score: float = Query(default=30, ge=0, le=100),
):
    """
    Get top insider accounts ranked by risk score.
    """
    db = await get_db()
    try:
        # Fetch wallets with high risk score
        cursor = await db.execute(
            """
            SELECT * FROM wallets 
            WHERE risk_score >= ? 
            ORDER BY risk_score DESC, total_profit DESC 
            LIMIT ?
            """,
            (min_score, limit)
        )
        rows = await cursor.fetchall()
        
        profiles = []
        for row in rows:
            analysis = {}
            if row["analysis_json"]:
                try:
                    analysis = json.loads(row["analysis_json"])
                except:
                    pass
            
            categories = {}
            if row["categories_json"]:
                try:
                    categories = json.loads(row["categories_json"])
                except:
                    pass

            # We don't fetch alerts for the list view to stay light
            profiles.append(
                WalletProfile(
                    address=row["address"],
                    username=row["username"],
                    first_seen=row["first_seen"],
                    total_trades=row["total_trades"],
                    total_volume=row["total_volume"],
                    risk_score=row["risk_score"],
                    analysis=analysis,
                    categories=categories,
                    win_rate=analysis.get("win_rate", 0.0),
                    alerts=[] 
                )
            )
        return profiles
    finally:
        await db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/whales  (High Win Rate profiles)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/whales", response_model=list[WalletProfile])
async def get_whales(
    limit: int = Query(default=50, ge=1, le=100),
    min_volume: float = Query(default=10000, ge=0),
):
    """
    Get wallets with high win rates and profit but low risk scores.
    These are skilled traders, not suspicious insiders.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT * FROM wallets
            WHERE total_volume >= ?
              AND total_trades >= 3
              AND analysis_json IS NOT NULL
            ORDER BY total_profit DESC, total_volume DESC
            LIMIT ?
            """,
            (min_volume, limit),
        )
        rows = await cursor.fetchall()

        profiles = []
        for row in rows:
            analysis = {}
            if row["analysis_json"]:
                try:
                    analysis = json.loads(row["analysis_json"])
                except:
                    pass

            win_rate = analysis.get("win_rate", 0.0)

            categories = {}
            if row["categories_json"]:
                try:
                    categories = json.loads(row["categories_json"])
                except:
                    pass

            profiles.append(
                WalletProfile(
                    address=row["address"],
                    username=row["username"],
                    first_seen=row["first_seen"],
                    total_trades=row["total_trades"],
                    total_volume=row["total_volume"],
                    risk_score=row["risk_score"],
                    analysis=analysis,
                    categories=categories,
                    win_rate=win_rate,
                    alerts=[],
                )
            )
        return profiles
    finally:
        await db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/scan
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/scan", response_model=ScanResponse)
async def trigger_scan(body: ScanRequest | None = None):
    """Trigger a manual scan (ingest + analyze)."""
    lookback = body.lookback_hours if body else 24
    scanner = Scanner()
    from app.services.account_analyzer import AccountAnalyzer
    analyzer = AccountAnalyzer(data=scanner.data, gamma=scanner.gamma, polygonscan=scanner.polygonscan)
    
    try:
        # 1. Ingest
        await scanner.run_scan(lookback_hours=lookback)
        
        # 2. Analyze
        await analyzer.analyze_all_wallets()
        
        return ScanResponse(
            alerts_generated=0, # Deprecated
            message="Scan and analysis triggered successfully",
        )
    finally:
        await scanner.close()
        await analyzer.close()


@router.post("/scan/history", response_model=ScanResponse)
async def trigger_historical_scan(
    pages: int = Query(default=100, ge=1, le=5000),
    min_size: float = Query(default=10000.0, ge=1000.0),
):
    """
    Trigger a deep historical scan to find whales.
    Iterates backward through global trades filtering by min_size.
    Then triggers analysis on found wallets.
    """
    scanner = Scanner()
    from app.services.account_analyzer import AccountAnalyzer
    analyzer = AccountAnalyzer(data=scanner.data, gamma=scanner.gamma, polygonscan=scanner.polygonscan)
    
    try:
        # 1. Deep Ingest
        count = await scanner.scan_history(lookback_pages=pages, min_size=min_size)
        
        # 2. Analyze
        if count > 0:
            await analyzer.analyze_all_wallets()
        
        return ScanResponse(
            trades_processed=count,
            message=f"Historical scan complete. {count} whale trades found. Analysis triggered.",
        )
    finally:
        await scanner.close()
        await analyzer.close()


@router.get("/monitor/status")
async def get_monitor_status():
    """Return the real-time status of the analysis loop."""
    return monitor.get_status()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Admin / Debug Routes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/admin/start-loop")
def start_scan_loop():
    """Manually start the background scan loop."""
    scan_loop.start()
    return {"message": "Scan loop start command issued"}

@router.post("/admin/stop-loop")
async def stop_scan_loop():
    """Manually stop the background scan loop."""
    await scan_loop.stop()
    return {"message": "Scan loop stopped"}
