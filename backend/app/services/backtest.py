"""
Backtest Service — Analyze any wallet without persisting results.

Fetches a wallet's full history from Polymarket APIs, runs the
six-factor scoring pipeline, and returns a detailed result. Used to
validate that the detection system would correctly flag known insiders.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import (
    DATA_API_BASE,
    GAMMA_API_BASE,
    MIN_POSITION_SIZE,
)
from app.services.pnl_calculator import PnLCalculator
from app.services.scoring import (
    compute_win_rate_anomaly,
    compute_bet_concentration,
    compute_timing_signal,
    compute_entry_price_edge,
    compute_account_pattern,
    compute_position_size_signal,
    compute_suspicion_score,
)

logger = logging.getLogger(__name__)


async def run_backtest(address: str) -> dict[str, Any]:
    """
    Run the full detection pipeline on a wallet without writing to the DB.

    Returns a detailed result dict with scores, factor breakdown, trade
    summary, per-market analysis, and insider verdict.
    """
    address = address.strip().lower()
    if not address.startswith("0x"):
        address = f"0x{address}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # ── 1. Fetch profile ──
        profile = await _fetch_profile(client, address)
        username = profile.get("name") or profile.get("pseudonym") or "Unknown"

        account_age_days: float | None = None
        if profile.get("createdAt"):
            try:
                created = datetime.fromisoformat(
                    profile["createdAt"].replace("Z", "+00:00")
                )
                account_age_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
            except Exception:
                pass

        # ── 2. Fetch activity (includes usdcSize + redemptions) ──
        activity = await _fetch_activity(client, address)

        # ── 3. Fetch trade history ──
        trades = await _fetch_trades(client, address)

        if not trades and not activity:
            return {
                "address": address,
                "username": username,
                "error": "No trades found for this wallet",
                "score": 0,
            }

        # ── 4. Aggregate per-market stats ──
        market_usdc: dict[str, float] = defaultdict(float)
        market_shares: dict[str, float] = defaultdict(float)
        market_prices: dict[str, list[tuple[float, float]]] = defaultdict(list)  # [(size, price)]
        market_titles: dict[str, str] = {}
        market_outcomes: dict[str, str] = {}
        trade_count = 0

        for t in trades:
            cid = t.get("conditionId", "")
            if not cid:
                continue

            try:
                size = float(t.get("size", 0))
                price = float(t.get("price", 0))
            except (ValueError, TypeError):
                continue

            usdc = size * price
            side = t.get("side", "").upper()

            if side == "BUY":
                market_usdc[cid] += usdc
                market_shares[cid] += size
                market_prices[cid].append((size, price))
                trade_count += 1

            market_titles[cid] = t.get("title", "")
            market_outcomes[cid] = t.get("outcome", "")

        # Also use activity data for usdcSize if available
        total_redeemed = 0.0
        for a in activity:
            if a.get("type") == "REDEEM":
                total_redeemed += float(a.get("usdcSize", 0) or 0)

        total_usdc = sum(market_usdc.values())
        total_shares = sum(market_shares.values())

        if total_usdc == 0:
            return {
                "address": address,
                "username": username,
                "error": "No buy trades found",
                "score": 0,
            }

        # ── 5. Fetch market resolution data ──
        market_ids = list(market_usdc.keys())
        resolved: dict[str, dict] = {}
        for mid in market_ids[:20]:
            mdata = await _fetch_market(client, mid)
            if mdata:
                resolved[mid] = mdata

        # ── 6. Compute PnL ──
        pnl_calc = PnLCalculator()
        pnl_trades = [
            {
                "conditionId": t.get("conditionId"),
                "side": t.get("side"),
                "outcome": t.get("outcome"),
                "size": float(t.get("size", 0)),
                "price": float(t.get("price", 0)),
            }
            for t in trades
        ]
        pnl_markets = {}
        for mid, m in resolved.items():
            if m.get("closed"):
                pnl_markets[mid] = {
                    "closed": True,
                    "winner_outcome": m.get("winner_outcome", ""),
                }

        pnl_stats = pnl_calc.calculate_stats(pnl_trades, pnl_markets)
        win_rate = pnl_stats.get("win_rate", 0.0)
        resolved_count = pnl_stats.get("resolved_markets_count", 0)
        avg_entry_prices = pnl_stats.get("avg_entry_prices", {})

        # ── 7. Score each factor ──
        # Primary market = highest USDC
        primary_cid = max(market_usdc, key=market_usdc.get)
        primary_usdc = market_usdc[primary_cid]

        # Win rate anomaly
        f_win_rate = compute_win_rate_anomaly(win_rate, resolved_count)

        # Bet concentration
        f_concentration = compute_bet_concentration(primary_usdc, total_usdc)

        # Timing signal
        timing_scores = []
        for cid, vol in market_usdc.items():
            m = resolved.get(cid)
            if m and m.get("endDate"):
                try:
                    end_dt = datetime.fromisoformat(m["endDate"].replace("Z", "+00:00"))
                    cid_trades = [t for t in trades if t.get("conditionId") == cid]
                    if cid_trades:
                        earliest = min(t.get("timestamp", 0) for t in cid_trades)
                        trade_dt = datetime.fromtimestamp(earliest, tz=timezone.utc)
                        hours = max(0, (end_dt - trade_dt).total_seconds() / 3600)
                        timing_scores.append(compute_timing_signal(hours))
                except Exception:
                    pass
        f_timing = (sum(timing_scores) / len(timing_scores)) if timing_scores else 0.0

        # Entry price edge
        edge_scores = []
        for cid, avg_p in avg_entry_prices.items():
            m = resolved.get(cid)
            if m and m.get("closed") and m.get("winner_outcome"):
                winner = m["winner_outcome"]
                cid_trades = [t for t in trades if t.get("conditionId") == cid]
                buys = sum(float(t.get("size", 0)) for t in cid_trades if t.get("side", "").upper() == "BUY" and t.get("outcome") == winner)
                sells = sum(float(t.get("size", 0)) for t in cid_trades if t.get("side", "").upper() == "SELL" and t.get("outcome") == winner)
                won = buys - sells > 0
                edge_scores.append(compute_entry_price_edge(avg_p, won))
        f_edge = (sum(edge_scores) / len(edge_scores)) if edge_scores else 0.0

        # Account pattern (boosted fresh-account signal)
        f_pattern = compute_account_pattern(account_age_days, len(market_usdc), f_concentration)

        # Position size signal (large USDC on low-odds)
        primary_price_entries = market_prices.get(primary_cid, [])
        if primary_price_entries:
            primary_avg_price = (
                sum(s * p for s, p in primary_price_entries)
                / sum(s for s, p in primary_price_entries)
            )
        else:
            primary_avg_price = 0.5
        f_position = compute_position_size_signal(primary_usdc, primary_avg_price)

        # ── 8. Final score ──
        result = compute_suspicion_score(
            win_rate_anomaly=f_win_rate,
            bet_concentration=f_concentration,
            timing_signal=f_timing,
            entry_price_edge=f_edge,
            account_pattern=f_pattern,
            position_size_signal=f_position,
        )

        # ── 9. Per-market breakdown ──
        per_market = []
        for cid in sorted(market_usdc, key=market_usdc.get, reverse=True):
            title = market_titles.get(cid, cid[:16])
            prices_list = market_prices.get(cid, [])
            avg_p = (
                sum(s * p for s, p in prices_list) / sum(s for s, p in prices_list)
                if prices_list else 0.0
            )
            m = resolved.get(cid)
            per_market.append({
                "conditionId": cid,
                "title": title,
                "usdc_invested": round(market_usdc[cid], 2),
                "shares": round(market_shares.get(cid, 0), 2),
                "avg_entry_price": round(avg_p, 4),
                "resolved": bool(m and m.get("closed")),
                "won": bool(m and m.get("winner_outcome") == market_outcomes.get(cid)),
            })

        # ── 10. Build result ──
        verdict = (
            "** HIGHLY SUSPICIOUS **" if result.score >= 60 else
            "* SUSPICIOUS *" if result.score >= 40 else
            "WORTH WATCHING" if result.score >= 25 else
            "LIKELY NORMAL"
        )

        return {
            "address": address,
            "username": username,
            "verdict": verdict,
            "score": round(result.score, 2),
            "passes_alert_gate": result.passes_gate,
            "elevated_factors": result.elevated_factors,
            "factors": {
                "win_rate_anomaly": {
                    "value": round(f_win_rate, 4),
                    "detail": f"{win_rate:.1f}% win rate, {resolved_count} resolved markets",
                },
                "bet_concentration": {
                    "value": round(f_concentration, 4),
                    "detail": f"{f_concentration*100:.0f}% in primary market",
                },
                "timing_signal": {
                    "value": round(f_timing, 4),
                    "detail": f"avg timing score across {len(timing_scores)} markets",
                },
                "entry_price_edge": {
                    "value": round(f_edge, 4),
                    "detail": f"avg edge across {len(edge_scores)} resolved markets",
                },
                "account_pattern": {
                    "value": round(f_pattern, 4),
                    "detail": (
                        f"age={account_age_days:.0f}d" if account_age_days else "unknown age"
                    ) + f", {len(market_usdc)} markets, conc={f_concentration:.0%}",
                },
                "position_size_signal": {
                    "value": round(f_position, 4),
                    "detail": f"${primary_usdc:,.0f} USDC at avg {primary_avg_price:.2f}c",
                },
            },
            "summary": {
                "account_age_days": round(account_age_days, 1) if account_age_days else None,
                "markets_traded": len(market_usdc),
                "total_usdc_invested": round(total_usdc, 2),
                "total_redeemed": round(total_redeemed, 2),
                "total_shares": round(total_shares, 2),
                "win_rate": round(win_rate, 2),
                "resolved_markets": resolved_count,
                "trade_count": trade_count,
            },
            "markets": per_market,
        }


# ---------------------------------------------------------------------------
# Internal API helpers
# ---------------------------------------------------------------------------

async def _fetch_profile(client: httpx.AsyncClient, address: str) -> dict:
    try:
        resp = await client.get(
            f"{GAMMA_API_BASE}/public-profile",
            params={"address": address},
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


async def _fetch_activity(client: httpx.AsyncClient, address: str) -> list:
    try:
        resp = await client.get(
            f"{DATA_API_BASE}/activity",
            params={"user": address, "limit": 200},
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


async def _fetch_trades(client: httpx.AsyncClient, address: str) -> list:
    all_trades = []
    for page in range(50):
        try:
            params: dict = {"user": address, "limit": 100}
            if page > 0:
                params["offset"] = page * 100
            resp = await client.get(f"{DATA_API_BASE}/trades", params=params)
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            all_trades.extend(batch)
            if len(batch) < 100:
                break
        except Exception:
            break
    return all_trades


async def _fetch_market(client: httpx.AsyncClient, condition_id: str) -> dict | None:
    try:
        resp = await client.get(
            f"{GAMMA_API_BASE}/markets",
            params={"condition_id": condition_id},
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                m = data[0]
                return {
                    "closed": m.get("closed", False),
                    "winner_outcome": m.get("winner", ""),
                    "endDate": m.get("endDate") or m.get("end_date_iso"),
                }
    except Exception:
        pass
    return None
