import asyncio
import logging
from app.core.database import get_db
from app.services.account_analyzer import AccountAnalyzer

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)

async def verify_filters():
    # 1. Reset specific wallet to unscanned for testing
    # We choose a wallet that we know has data but maybe low PnL
    test_wallet = "0xf244e9a19af1d19f6dd8b98e4b9bb3ace3a226fe"
    
    db = await get_db()
    try:
        # Delete from alerts first (FK constraint)
        await db.execute("DELETE FROM alerts WHERE wallet_address = ?", (test_wallet,))
        # Delete from wallets
        await db.execute("DELETE FROM wallets WHERE address = ?", (test_wallet,))
        await db.commit()
    finally:
        await db.close()

    print(f"Reset {test_wallet} for testing.")

    # 2. Run Analyzer
    print("Running Analyzer...")
    analyzer = AccountAnalyzer()
    await analyzer.analyze_all_wallets()
    await analyzer.close()
    
    # 3. Check Result
    db = await get_db()
    try:
        cursor = await db.execute("SELECT risk_score, analysis_json FROM wallets WHERE address = ?", (test_wallet,))
        row = await cursor.fetchone()
        if row:
            print(f"Wallet Found. Score: {row[0]}")
            if row[0] == 0:
                print("Correctly flagged as low PnL (Score 0).")
            else:
                print(f"High PnL preserved. Analysis: {row[1]}")
        else:
             print("Wallet not found in DB? (Should be there as scanned)")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(verify_filters())
