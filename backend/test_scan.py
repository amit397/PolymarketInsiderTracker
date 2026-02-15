"""Live scan test — 24h lookback with verbose logging."""
import asyncio
import json
import logging
import sys

# Turn on scanner INFO logging
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s | %(message)s",
    stream=sys.stdout,
)

async def test():
    from app.core.database import init_db
    from app.services.scanner import Scanner
    await init_db()
    s = Scanner()
    try:
        alerts = await s.run_scan(lookback_hours=24)
        print(f"\n=== RESULT: {len(alerts)} alerts generated ===")
        for a in alerts[:10]:
            print(json.dumps({
                "wallet": a["wallet_address"][:16] + "...",
                "question": a.get("market_question", "")[:80],
                "slug": a.get("market_slug", "")[:60],
                "score": round(a["suspicion_score"], 1),
                "size": a["trade_size"],
                "side": a["trade_side"],
            }, indent=2))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
    finally:
        await s.close()

asyncio.run(test())
