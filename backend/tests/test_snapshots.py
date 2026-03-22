"""Tests for snapshot persistence and conservative wallet-age filtering."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from app.core import database
from app.services.scoring import ScoringResult, apply_conservative_wallet_age_filter
from app.services.snapshots import SQLiteSnapshotRepository


def test_conservative_wallet_age_filter_suppresses_old_middling_scores():
    result = ScoringResult(score=58.0, passes_gate=True)
    filtered, applied = apply_conservative_wallet_age_filter(result, age_days=240)
    assert applied is True
    assert filtered.score == 46.4
    assert filtered.passes_gate is False


def test_conservative_wallet_age_filter_preserves_strong_cases():
    result = ScoringResult(score=82.0, passes_gate=True)
    filtered, applied = apply_conservative_wallet_age_filter(result, age_days=600)
    assert applied is False
    assert filtered.score == 82.0
    assert filtered.passes_gate is True


def test_snapshot_export_and_import_round_trip(monkeypatch):
    async def scenario() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "snapshot.db"
            monkeypatch.setattr(database, "DB_PATH", temp_db)
            await database.init_db()
            db = await database.get_db()
            try:
                await db.execute(
                    "INSERT INTO wallets (address, username, total_trades, total_volume, total_profit, risk_score, analysis_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "0xabc",
                        "tester",
                        4,
                        1200.0,
                        250.0,
                        62.0,
                        '{"win_rate": 75, "resolved_markets_count": 3, "factors": {"account_pattern": 0.8}}',
                    ),
                )
                await db.execute(
                    "INSERT INTO alerts (wallet_address, market_id, condition_id, suspicion_score, factors_json, market_question, market_slug, trade_size, trade_side, tx_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                    (
                        "0xabc",
                        "market-1",
                        "condition-1",
                        62.0,
                        '{"account_pattern": 0.8}',
                        "Will this test pass?",
                        "test-pass",
                        500.0,
                        "BUY",
                        "0xtx",
                    ),
                )
                await db.commit()
            finally:
                await db.close()

            repository = SQLiteSnapshotRepository()
            snapshot = await repository.export_snapshot()
            assert snapshot["counts"]["wallets"] == 1
            assert snapshot["counts"]["alerts"] == 1

            db = await database.get_db()
            try:
                await db.execute("DELETE FROM alerts")
                await db.execute("DELETE FROM wallets")
                await db.commit()
            finally:
                await db.close()

            counts = await repository.import_snapshot(snapshot, mode="replace")
            assert counts["wallets"] == 1
            assert counts["alerts"] == 1

            db = await database.get_db()
            try:
                wallet_row = await (await db.execute("SELECT * FROM wallets WHERE address = ?", ("0xabc",))).fetchone()
                assert wallet_row["username"] == "tester"
            finally:
                await db.close()

    asyncio.run(scenario())
