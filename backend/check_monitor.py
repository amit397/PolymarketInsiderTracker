import requests
import time

try:
    resp = requests.get("http://localhost:8000/api/monitor/status")
    print(resp.json())
except Exception as e:
    print(f"Error: {e}")
