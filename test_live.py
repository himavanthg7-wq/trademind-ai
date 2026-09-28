import time
import sys
from live_data import start_background_feed, get_latest_data, get_status_summary

print("========================================")
print("TradeMind AI - Live Feed Test")
print("========================================")
print("Starting live market feed...")

start_background_feed()

print("Monitoring ticks (Press Ctrl+C to stop)...")
try:
    for i in range(12):  # Run for 1 minute or until interrupted
        time.sleep(5)
        status = get_status_summary()
        data = get_latest_data()
        print(f"\n[Status: {status['status']} | Ticks: {status['received_ticks_count']}]")
        for key, val in data.items():
            print(f"  {key}: LTP = ₹{val['LTP']} | CP = ₹{val['Previous Close']}")
except KeyboardInterrupt:
    print("\nLive feed test stopped by user.")