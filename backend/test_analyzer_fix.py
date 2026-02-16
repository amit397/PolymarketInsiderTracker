import asyncio
import logging
from app.services.account_analyzer import AccountAnalyzer
from app.core.database import get_db

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_fix():
    # Known wallet with trades in DB
    wallet = "0xf244e9a19af1d19f6dd8b98e4b9bb3ace3a226fe"
    
    analyzer = AccountAnalyzer()
    
    print(f"Analyzing wallet {wallet} using local DB path...")
    try:
        await analyzer.analyze_wallet(wallet)
    except Exception as e:
        print(f"Analysis failed: {e}")
    finally:
        await analyzer.close()
        
    # Check if analysis result was written to DB
    db = await get_db()
    try:
        cursor = await db.execute("SELECT risk_score, analysis_json FROM wallets WHERE address = ?", (wallet,))
        row = await cursor.fetchone()
        if row:
            print(f"Verification Success! Wallet {wallet} updated.")
            print(f"Risk Score: {row[0]}")
            print(f"Analysis: {row[1]}")
        else:
            print("Verification Failed: Wallet not updated in DB.")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(verify_fix())
