import requests
import time
import json

def check_status():
    try:
        resp = requests.get("http://localhost:8000/api/monitor/status")
        print(f"Monitor Status: {resp.json()}")
    except Exception as e:
        print(f"Status Check Failed: {e}")

print("--- Before Trigger ---")
check_status()

print("\n--- Triggering Scan ---")
try:
    # Trigger scan with small lookback for speed
    resp = requests.post("http://localhost:8000/api/scan", json={"lookback_hours": 1})
    print(f"Trigger Response: {resp.status_code} - {resp.text}")
except Exception as e:
    print(f"Trigger Failed: {e}")

print("\n--- Immediately After Trigger ---")
# The scan is synchronous in the route, so it will wait until finished!
# Wait, no. The route awaits the scan. So it will block until done.
# So we expect to see "Idle" again if it finishes fast, or we might catch it?
# Actually if we want to catch it running, we need to poll concurrently.
# But since I can't easily do concurrent separate processes here without more complexity,
# I will assume that if it finishes, the status should be "Idle" (reset at end of analyze?)
# Analyze loop update:
# monitor.update("Idle", stats=...) is called at end of analyze_all_wallets?
# Let's check AccountAnalyzer.analyze_all_wallets

check_status()
