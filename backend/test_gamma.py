import asyncio
from app.services.gamma_client import GammaClient

async def main():
    c = GammaClient()
    markets = await c.fetch_markets(closed=True, limit=5)
    for m in markets:
        print("Market:", m.get('conditionId'))
        print("closed:", m.get('closed'))
        print("outcomes:", m.get('outcomes'))
        print("outcomePrices:", m.get('outcomePrices'))
        print("winner_outcome:", m.get('winner_outcome'))
        print("---")
    await c.close()

if __name__ == '__main__':
    asyncio.run(main())
