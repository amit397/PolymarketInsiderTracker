import asyncio
from app.core.database import get_db

async def check_wallet():
    wallet = "0xf244e9a19af1d19f6dd8b98e4b9bb3ace3a226fe"
    db = await get_db()
    try:
        cursor = await db.execute("SELECT count(*) FROM trades WHERE proxy_wallet = ?", (wallet,))
        row = await cursor.fetchone()
        print(f"Trades for {wallet}: {row[0]}")
        
        if row[0] > 0:
            cursor = await db.execute("SELECT * FROM trades WHERE proxy_wallet = ? LIMIT 1", (wallet,))
            trade = await cursor.fetchone()
            print("Sample trade:", trade)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(check_wallet())
