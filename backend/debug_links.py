import asyncio
from app.services.data_client import DataClient
from app.services.gamma_client import GammaClient

async def main():
    # 1. Get condition ID for the slug first
    gamma = GammaClient()
    condition_id = None
    try:
        slug = "mex-gua-ame-2026-02-14-gua"
        markets = await gamma.fetch_markets(slug=slug)
        if markets:
            condition_id = markets[0].get("conditionId")
            print(f"Condition ID: {condition_id}")
    finally:
        await gamma.close()

    if not condition_id:
        print("Could not find condition ID")
        return

    # 2. Fetch trades for this condition ID
    data = DataClient()
    try:
        trades = await data.fetch_market_trades(condition_id, max_pages=1)
        if trades:
            t = trades[0]
            print(f"TRADE_SLUG: {t.get('slug')}")
            print(f"TRADE_MARKET_SLUG: {t.get('marketSlug')}")
            print(f"TRADE_EVENT_SLUG: {t.get('eventSlug')}")
            
            # Check other potential fields
            for k, v in t.items():
                if isinstance(v, str) and "mex" in v:
                    print(f"TRADE_MATCH_KEY [{k}]: {v}")
        else:
            print("No trades found")
    finally:
        await data.close()

if __name__ == "__main__":
    asyncio.run(main())
