import asyncio
import aiosqlite
from app.core.config import DB_PATH

async def migrate():
    print(f"Migrating database at {DB_PATH}...")
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Add tx_hash to alerts
        try:
            await db.execute("ALTER TABLE alerts ADD COLUMN tx_hash TEXT")
            print("Added tx_hash column to alerts.")
        except Exception as e:
            print(f"Skipped alerts.tx_hash: {e}")

        # 2. Add risk_score to wallets
        try:
            await db.execute("ALTER TABLE wallets ADD COLUMN risk_score REAL DEFAULT 0")
            print("Added risk_score column to wallets.")
        except Exception as e:
            print(f"Skipped wallets.risk_score: {e}")

        # 3. Add analysis_json to wallets
        try:
            await db.execute("ALTER TABLE wallets ADD COLUMN analysis_json TEXT DEFAULT '{}'")
            print("Added analysis_json column to wallets.")
        except Exception as e:
            print(f"Skipped wallets.analysis_json: {e}")

        await db.commit()
    print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
