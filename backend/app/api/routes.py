"""FastAPI route definitions."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Query, BackgroundTasks

from app.api.schemas import (
    AlertResponse,
    DashboardStats,
    ExpiringMarketResponse,
    FactorBreakdown,
    ImportSnapshotRequest,
    ImportSnapshotResponse,
    ScanRequest,
    ScanResponse,
    SuspiciousMarket,
    TradeRecord,
    WalletTradesPage,
    WalletProfile,
)
from app.core.database import get_db
from app.services.gamma_client import GammaClient
from app.services.intelligence import (
    followability_score,
    score_label,
    top_factor_names,
    why_flagged,
)
from app.services.scanner import Scanner
from app.core.monitor import monitor # Import Monitor
from app.services.scan_loop import scan_loop # Import ScanLoop
from app.services.snapshots import SQLiteSnapshotRepository

router = APIRouter(prefix="/api")
WALLET_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _validate_wallet_address(address: str) -> str:
    if not WALLET_ADDRESS_RE.match(address):
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Invalid wallet address format")
    return address.lower()


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
            position_size_signal=data.get("position_size_signal", 0),
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


def _parse_json_blob(payload: str | None) -> dict:
    if not payload:
        return {}
    try:
        parsed = json.loads(payload)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _row_to_wallet_profile(row, alerts: list[AlertResponse] | None = None) -> WalletProfile:
    analysis = _parse_json_blob(row["analysis_json"])
    categories = _parse_json_blob(row["categories_json"])
    factors = analysis.get("factors", {}) if isinstance(analysis, dict) else {}
    win_rate = analysis.get("win_rate", 0.0) if isinstance(analysis, dict) else 0.0
    total_pnl = analysis.get("total_pnl", row["total_profit"] or 0.0) if isinstance(analysis, dict) else (row["total_profit"] or 0.0)
    resolved_markets_count = analysis.get("resolved_markets_count", 0) if isinstance(analysis, dict) else 0
    account_age_days = analysis.get("account_age_days") if isinstance(analysis, dict) else None
    risk_score_value = row["risk_score"] if row["risk_score"] is not None else float(analysis.get("score", 0.0) if isinstance(analysis, dict) else 0.0)
    return WalletProfile(
        address=row["address"],
        username=row["username"],
        first_seen=row["first_seen"],
        total_trades=row["total_trades"],
        total_volume=row["total_volume"] or 0.0,
        total_profit=row["total_profit"] if row["total_profit"] is not None else 0.0,
        total_pnl=total_pnl if total_pnl is not None else 0.0,
        risk_score=risk_score_value,
        analysis=analysis,
        categories=categories,
        win_rate=win_rate or 0.0,
        resolved_markets_count=resolved_markets_count or 0,
        account_age_days=account_age_days,
        score_label=score_label(risk_score_value),
        why_flagged=why_flagged(factors, account_age_days),
        top_factors=top_factor_names(factors),
        followability_score=followability_score(
            win_rate=float(win_rate or 0.0),
            total_profit=float(row["total_profit"] or 0.0),
            total_volume=float(row["total_volume"] or 0.0),
            risk_score_value=float(risk_score_value or 0.0),
            resolved_markets_count=int(resolved_markets_count or 0),
        ),
        alerts=alerts or [],
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
    address = _validate_wallet_address(address)
    db = await get_db()
    try:
        # Wallet info
        cursor = await db.execute(
            "SELECT * FROM wallets WHERE lower(address) = ?", (address,)
        )
        wallet_row = await cursor.fetchone()

        # Alerts for this wallet
        cursor = await db.execute(
            "SELECT * FROM alerts WHERE lower(wallet_address) = ? ORDER BY suspicion_score DESC",
            (address,),
        )
        alert_rows = await cursor.fetchall()

        if wallet_row:
            return _row_to_wallet_profile(
                wallet_row,
                alerts=[_row_to_alert(r) for r in alert_rows],
            )
        return WalletProfile(address=address, alerts=[])
    finally:
        await db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/wallet/{address}/trades
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/wallet/{address}/trades", response_model=WalletTradesPage)
async def get_wallet_trades(
    address: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Paginated trade history for a wallet."""
    address = _validate_wallet_address(address)
    db = await get_db()
    try:
        count_cursor = await db.execute(
            "SELECT COUNT(*) AS total FROM trades WHERE lower(proxy_wallet) = ?",
            (address,),
        )
        total = (await count_cursor.fetchone())["total"]

        cursor = await db.execute(
            "SELECT * FROM trades WHERE lower(proxy_wallet) = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (address, limit, offset),
        )
        rows = await cursor.fetchall()
        items = [TradeRecord(**dict(row)) for row in rows]
        return WalletTradesPage(
            items=items,
            limit=limit,
            offset=offset,
            total=total,
            has_more=(offset + limit) < total,
        )
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
    min_score: float = Query(default=15, ge=0, le=100),
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
        
        return [_row_to_wallet_profile(row) for row in rows]
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
              AND risk_score < 40
              AND analysis_json IS NOT NULL
            ORDER BY total_profit DESC, total_volume DESC
            LIMIT ?
            """,
            (min_volume, limit),
        )
        rows = await cursor.fetchall()

        return [_row_to_wallet_profile(row) for row in rows]
    finally:
        await db.close()


@router.get("/intelligence/export")
async def export_intelligence_snapshot():
    """Export a JSON snapshot of the local intelligence store."""
    repository = SQLiteSnapshotRepository()
    return await repository.export_snapshot()


@router.post("/intelligence/import", response_model=ImportSnapshotResponse)
async def import_intelligence_snapshot(request: ImportSnapshotRequest):
    """Import a JSON snapshot into the local intelligence store."""
    from fastapi import HTTPException

    repository = SQLiteSnapshotRepository()
    try:
        counts = await repository.import_snapshot(request.snapshot, mode=request.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ImportSnapshotResponse(
        message="Snapshot imported successfully",
        counts=counts,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/scan
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _run_scan_task(lookback_hours: int):
    # Background worker explicitly cleans up resources
    scanner = Scanner()
    from app.services.account_analyzer import AccountAnalyzer
    analyzer = AccountAnalyzer(data=scanner.data, gamma=scanner.gamma, polygonscan=scanner.polygonscan)
    try:
        await scanner.run_scan(lookback_hours=lookback_hours)
        await analyzer.analyze_all_wallets()
    finally:
        await scanner.close()
        await analyzer.close()

@router.post("/scan", response_model=ScanResponse)
async def trigger_scan(background_tasks: BackgroundTasks, body: ScanRequest | None = None):
    """Trigger a manual scan (ingest + analyze in background)."""
    lookback = body.lookback_hours if body else 24
    background_tasks.add_task(_run_scan_task, lookback)
    
    return ScanResponse(
        alerts_generated=0,
        message="Scan task queued and running in the background.",
    )

async def _run_historical_task(pages: int, min_size: float):
    scanner = Scanner()
    from app.services.account_analyzer import AccountAnalyzer
    analyzer = AccountAnalyzer(data=scanner.data, gamma=scanner.gamma, polygonscan=scanner.polygonscan)
    try:
        count = await scanner.scan_history(lookback_pages=pages, min_size=min_size)
        if count > 0:
            await analyzer.analyze_all_wallets()
    finally:
        await scanner.close()
        await analyzer.close()


@router.post("/scan/history", response_model=ScanResponse)
async def trigger_historical_scan(
    background_tasks: BackgroundTasks,
    pages: int = Query(default=100, ge=1, le=5000),
    min_size: float = Query(default=10000.0, ge=1000.0),
):
    """
    Trigger a deep historical scan to find whales in the background.
    """
    background_tasks.add_task(_run_historical_task, pages, min_size)
        
    return ScanResponse(
        trades_processed=0,
        message=f"Historical scan queued. Iterating through {pages} pages in the background.",
    )


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/backtest/{address}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/backtest/{address}")
async def backtest_wallet(address: str):
    """
    Run the full detection pipeline on any wallet without saving results.
    
    Use to validate detection against known insiders:
    GET /api/backtest/0xdde15ebd95330ce69136dc0ccd810d22382e02c5
    """
    from app.services.backtest import run_backtest
    return await run_backtest(address)
