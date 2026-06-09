import requests
import time
import json
from datetime import datetime
import os

url = "https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol=NIFTY&expiry=09-Jun-2026"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

# Create folder if it doesn't exist
os.makedirs("nifty_data", exist_ok=True)

while True:
    try:
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code == 200:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            filename = f"nifty_data/nifty_{timestamp}.json"

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(r.json(), f, indent=2)

            print(f"[{timestamp}] Saved: {filename}")

        else:
            print(f"Failed. Status Code: {r.status_code}")

    except Exception as e:
        print("Error:", e)

    # Wait 5 minutes (300 seconds)
    time.sleep(1500)
    