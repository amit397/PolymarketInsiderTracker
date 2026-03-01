import asyncio
import json
from app.services.data_client import DataClient

async def main():
    client = DataClient()
    trades = await client.fetch_trades(limit=1)
    with open("trade.json", "w") as f:
        json.dump(trades[0] if trades else {}, f, indent=2)
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
