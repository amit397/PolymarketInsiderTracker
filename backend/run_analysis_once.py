import asyncio
import logging
from app.services.account_analyzer import AccountAnalyzer

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)

async def run_analysis():
    print("Initializing AccountAnalyzer...")
    analyzer = AccountAnalyzer()
    try:
        print("Starting analysis of all wallets...")
        await analyzer.analyze_all_wallets()
        print("Analysis complete.")
    finally:
        await analyzer.close()

if __name__ == "__main__":
    asyncio.run(run_analysis())
