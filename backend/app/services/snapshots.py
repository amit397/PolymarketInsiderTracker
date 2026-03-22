"""Snapshot export/import utilities for local persistence and future remote adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from app.core.database import get_db

SNAPSHOT_VERSION = 1
SNAPSHOT_TABLES: dict[str, list[str]] = {
    "markets": [
        "id", "question", "slug", "category", "end_date", "volume",
        "clob_token_ids", "condition_id", "image", "last_updated",
    ],
    "trades": [
        "id", "condition_id", "market_slug", "proxy_wallet", "side", "size",
        "usdc_size", "price", "outcome", "timestamp", "tx_hash", "market_question",
    ],
    "wallets": [
        "address", "username", "first_seen", "total_trades", "total_volume",
        "total_profit", "categories_json", "last_scanned", "risk_score", "analysis_json",
    ],
    "alerts": [
        "id", "wallet_address", "market_id", "condition_id", "suspicion_score",
        "factors_json", "market_question", "market_slug", "market_end_date",
        "trade_size", "trade_side", "tx_hash", "created_at",
    ],
}
DELETE_ORDER = ["alerts", "trades", "wallets", "markets"]
INSERT_ORDER = ["markets", "trades", "wallets", "alerts"]


class SnapshotRepository(Protocol):
    async def export_snapshot(self) -> dict[str, Any]: ...
    async def import_snapshot(self, snapshot: dict[str, Any], *, mode: str = "merge") -> dict[str, int]: ...


@dataclass
class SQLiteSnapshotRepository:
    """SQLite-backed snapshot repository.

    This class is intentionally adapter-shaped so a Supabase implementation can
    conform to the same interface later.
    """

    async def export_snapshot(self) -> dict[str, Any]:
        db = await get_db()
        try:
            payload: dict[str, Any] = {
                "version": SNAPSHOT_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "tables": {},
            }
            for table in INSERT_ORDER:
                rows = await (await db.execute(f"SELECT * FROM {table}")).fetchall()
                payload["tables"][table] = [dict(row) for row in rows]
            payload["counts"] = {
                table: len(payload["tables"][table])
                for table in INSERT_ORDER
            }
            return payload
        finally:
            await db.close()

    async def import_snapshot(self, snapshot: dict[str, Any], *, mode: str = "merge") -> dict[str, int]:
        tables = snapshot.get("tables")
        if not isinstance(tables, dict):
            raise ValueError("Snapshot payload is missing a valid 'tables' object")

        validated: dict[str, list[dict[str, Any]]] = {}
        for table, columns in SNAPSHOT_TABLES.items():
            rows = tables.get(table, [])
            if rows is None:
                rows = []
            if not isinstance(rows, list):
                raise ValueError(f"Snapshot table '{table}' must be a list")
            cleaned_rows: list[dict[str, Any]] = []
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"Snapshot table '{table}' must contain only objects")
                cleaned_rows.append({column: row.get(column) for column in columns})
            validated[table] = cleaned_rows

        db = await get_db()
        inserted_counts = {table: 0 for table in INSERT_ORDER}
        try:
            if mode == "replace":
                for table in DELETE_ORDER:
                    await db.execute(f"DELETE FROM {table}")

            for table in INSERT_ORDER:
                rows = validated[table]
                if not rows:
                    continue
                columns = SNAPSHOT_TABLES[table]
                placeholders = ", ".join(["?" for _ in columns])
                quoted_columns = ", ".join(columns)
                query = f"INSERT OR REPLACE INTO {table} ({quoted_columns}) VALUES ({placeholders})"
                await db.executemany(
                    query,
                    [tuple(row.get(column) for column in columns) for row in rows],
                )
                inserted_counts[table] = len(rows)

            await db.commit()
            return inserted_counts
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()
