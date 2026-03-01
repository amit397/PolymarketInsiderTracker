import asyncio
from app.services.gamma_client import GammaClient

async def main():
    client = GammaClient()
    markets = await client.fetch_markets(limit=1, closed=False)
    if markets:
        print("KEYS:", markets[0].keys())
        print("conditionId in keys?", "conditionId" in markets[0])
    else:
        print("NO MARKETS")
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
