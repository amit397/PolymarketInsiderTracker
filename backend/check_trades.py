import asyncio
from app.services.data_client import DataClient

async def main():
    client = DataClient()
    trades = await client.fetch_trades(limit=5)
    print("KEYS:", trades[0].keys() if trades else "NO TRADES")
    print(trades[0] if trades else "")
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
