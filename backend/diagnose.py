"""Diagnostic script to check database state and identify pipeline issues."""
import sqlite3
import os
import glob

# Find all .db files
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.db'):
            path = os.path.join(root, f)
            print(f"\n{'='*60}")
            print(f"DATABASE: {path} ({os.path.getsize(path)} bytes)")
            print('='*60)
            
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            for t in tables:
                name = t[0]
                count = c.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
                print(f"  {name}: {count} rows")
            
            # Check trades
            try:
                row = c.execute("SELECT COUNT(*) FROM trades").fetchone()
                print(f"\n  TRADES: {row[0]} total")
                
                if row[0] > 0:
                    # Size distribution
                    print("\n  Trade size distribution:")
                    for threshold in [100, 1000, 5000, 10000, 50000]:
                        cnt = c.execute(f"SELECT COUNT(*) FROM trades WHERE size >= {threshold}").fetchone()[0]
                        print(f"    >= ${threshold:,}: {cnt} trades")
                    
                    # Sample trades
                    print("\n  Last 5 trades:")
                    rows = c.execute("SELECT proxy_wallet, size, side, market_question, timestamp FROM trades ORDER BY timestamp DESC LIMIT 5").fetchall()
                    for r in rows:
                        print(f"    ${r[1]:,.0f} {r[2]} by {r[0][:10]}... | {r[3][:50] if r[3] else 'N/A'}")
                    
                    # Unique wallets
                    wallets = c.execute("SELECT COUNT(DISTINCT proxy_wallet) FROM trades").fetchone()[0]
                    print(f"\n  Unique wallets: {wallets}")
                    
                    # Wallets with >= $10K in a single market
                    whale_q = """
                        SELECT proxy_wallet, condition_id, SUM(size) as total 
                        FROM trades 
                        WHERE proxy_wallet IS NOT NULL AND proxy_wallet != ''
                        GROUP BY proxy_wallet, condition_id 
                        HAVING SUM(size) >= 10000
                    """
                    whales = c.execute(whale_q).fetchall()
                    print(f"  Wallets with >= $10K in single market: {len(set(r[0] for r in whales))}")
                    if whales:
                        for w in whales[:5]:
                            print(f"    {w[0][:10]}... -> ${w[2]:,.0f} in market {w[1][:20]}...")
            except Exception as e:
                print(f"  Error checking trades: {e}")
            
            # Check wallets table
            try:
                wcount = c.execute("SELECT COUNT(*) FROM wallets").fetchone()[0]
                print(f"\n  WALLETS analyzed: {wcount}")
                if wcount > 0:
                    rows = c.execute("SELECT address, risk_score, total_trades, total_volume FROM wallets ORDER BY risk_score DESC LIMIT 5").fetchall()
                    for r in rows:
                        print(f"    {r[0][:10]}... Score={r[1]:.1f} Trades={r[2]} Vol=${r[3]:,.0f}")
            except Exception as e:
                print(f"  Error checking wallets: {e}")
            
            # Check alerts
            try:
                acount = c.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
                print(f"\n  ALERTS: {acount}")
            except Exception as e:
                print(f"  Error checking alerts: {e}")
            
            conn.close()

print("\n\nDone.")
