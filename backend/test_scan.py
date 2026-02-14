"""Quick scan test — run directly to see tracebacks."""
import asyncio
import traceback
import json

async def test():
    from app.core.database import init_db
    from app.services.scanner import Scanner
    await init_db()
    s = Scanner()
    try:
        alerts = await s.run_scan(lookback_hours=1)
        print(f"SUCCESS: {len(alerts)} alerts generated")
        for a in alerts[:3]:
            print(json.dumps(
                {k: a.get(k) for k in ["wallet_address", "suspicion_score", "trade_size", "trade_side"]},
                indent=2
            ))
    except Exception:
        traceback.print_exc()
    finally:
        await s.close()

asyncio.run(test())
