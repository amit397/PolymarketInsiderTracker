import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'insider_tracker.db')
conn = sqlite3.connect(db_path)
conn.execute('UPDATE wallets SET last_scanned = "2000-01-01T00:00:00"')
conn.commit()
conn.close()
print("Updated all wallets to be rescanned.")
