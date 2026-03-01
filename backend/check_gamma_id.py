import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # test fetch by id
        cid = "0x920aaed19e8665dd291c63a9ab5f398dbbff5f51fa279f4c3f45dca00d3cf2b4"
        resp1 = await client.get(f"https://gamma-api.polymarket.com/markets/{cid}")
        print("GET /markets/cid ->", resp1.status_code)
        
        # test fetch by query
        resp2 = await client.get("https://gamma-api.polymarket.com/markets", params={"condition_id": cid})
        print("GET /markets?condition_id=cid ->", resp2.status_code)
        if resp2.status_code == 200:
            data = resp2.json()
            print("len =", len(data))

if __name__ == "__main__":
    asyncio.run(main())
