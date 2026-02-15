"""SQLite database setup and schema management."""

from __future__ import annotations

import aiosqlite

from app.core.config import DB_PATH

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
    id               TEXT PRIMARY KEY,
    question         TEXT NOT NULL,
    slug             TEXT,
    category         TEXT,
    end_date         TEXT,
    volume           REAL DEFAULT 0,
    clob_token_ids   TEXT,
    condition_id     TEXT,
    image            TEXT,
    last_updated     TEXT
);

CREATE TABLE IF NOT EXISTS trades (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id     TEXT NOT NULL,
    market_slug      TEXT,
    proxy_wallet     TEXT NOT NULL,
    side             TEXT NOT NULL,
    size             REAL NOT NULL,
    price            REAL NOT NULL,
    outcome          TEXT,
    timestamp        INTEGER NOT NULL,
    tx_hash          TEXT UNIQUE,
    market_question  TEXT
);

CREATE TABLE IF NOT EXISTS wallets (
    address          TEXT PRIMARY KEY,
    username         TEXT,
    first_seen       INTEGER,
    total_trades     INTEGER DEFAULT 0,
    total_volume     REAL DEFAULT 0,
    categories_json  TEXT DEFAULT '{}',
    last_scanned     TEXT,
    risk_score       REAL DEFAULT 0,
    analysis_json    TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS alerts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address   TEXT NOT NULL,
    market_id        TEXT,
    condition_id     TEXT,
    suspicion_score  REAL NOT NULL,
    factors_json     TEXT NOT NULL,
    market_question  TEXT,
    market_slug      TEXT,
    market_end_date  TEXT,
    trade_size       REAL,
    trade_side       TEXT,
    tx_hash          TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (wallet_address) REFERENCES wallets(address)
);

CREATE INDEX IF NOT EXISTS idx_trades_proxy_wallet ON trades(proxy_wallet);
CREATE INDEX IF NOT EXISTS idx_trades_condition_id ON trades(condition_id);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp    ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_score        ON alerts(suspicion_score DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_wallet       ON alerts(wallet_address);
CREATE INDEX IF NOT EXISTS idx_alerts_created      ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_markets_end_date    ON markets(end_date);
"""


async def get_db() -> aiosqlite.Connection:
    """Return a new database connection."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    """Create all tables and indices if they don't exist."""
    db = await get_db()
    try:
        await db.executescript(_SCHEMA)
        await db.commit()
    finally:
        await db.close()
