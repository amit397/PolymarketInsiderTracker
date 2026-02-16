import asyncio
from app.core.database import get_db

async def check_status():
    db = await get_db()
    try:
        # 1. Trades count
        row = await (await db.execute("SELECT count(*) FROM trades")).fetchone()
        trades_count = row[0]
        print(f"Total Trades: {trades_count}")

        # 2. Wallets count
        row = await (await db.execute("SELECT count(*) FROM wallets")).fetchone()
        wallets_count = row[0]
        print(f"Total Wallets: {wallets_count}")

        # 3. Alerts count
        row = await (await db.execute("SELECT count(*) FROM alerts")).fetchone()
        alerts_count = row[0]
        print(f"Total Alerts: {alerts_count}")

        # 4. Risk Score Stats
        if wallets_count > 0:
            row = await (await db.execute("SELECT MIN(risk_score), AVG(risk_score), MAX(risk_score) FROM wallets")).fetchone()
            print(f"Risk Scores - Min: {row[0]}, Avg: {row[1]}, Max: {row[2]}")
            
            # Show top 5 wallets by risk score
            cursor = await db.execute("SELECT address, risk_score FROM wallets ORDER BY risk_score DESC LIMIT 5")
            top_wallets = await cursor.fetchall()
            print("\nTop 5 Wallets by Risk Score:")
            for w in top_wallets:
                print(f"  {w[0]}: {w[1]}")
        else:
            print("No wallets found.")

    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(check_status())
