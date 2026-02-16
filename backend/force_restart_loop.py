import requests
import time
import json

BASE_URL = "http://localhost:8000/api"

def check_status():
    try:
        resp = requests.get(f"{BASE_URL}/monitor/status", timeout=2)
        print(f"Monitor: {json.dumps(resp.json(), indent=2)}")
    except Exception as e:
        print(f"Status Check Failed: {e}")

def stop_loop():
    try:
        print("Stopping loop...")
        resp = requests.post(f"{BASE_URL}/admin/stop-loop", timeout=5)
        print(f"Stop: {resp.text}")
    except Exception as e:
        print(f"Stop Failed: {e}")

def start_loop():
    try:
        print("Starting loop...")
        resp = requests.post(f"{BASE_URL}/admin/start-loop", timeout=5)
        print(f"Start: {resp.text}")
    except Exception as e:
        print(f"Start Failed: {e}")

print("--- Initial Status ---")
check_status()

print("\n--- Restarting Loop ---")
stop_loop()
time.sleep(1)
start_loop()
time.sleep(2) # Give it time to start cycle 1

print("\n--- Final Status ---")
check_status()
