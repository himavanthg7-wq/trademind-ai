import time
from live_data import start_background_feed, get_live_stock_data, get_status_summary

print("========================================")
print("TradeMind AI - Live Combined Data Test")
print("========================================")
print("Starting live feed...")
start_background_feed()

print("Waiting 5 seconds for live market ticks...")
time.sleep(5)

data = get_live_stock_data()
status = get_status_summary()

print(f"\nWebSocket Feed: {status['status']}")
print("----------------------------------------")
for symbol, values in data.items():
    print(
        f"{symbol:<10} | LTP: ₹{values['LTP']:<8.2f} "
        f"| Prev Close: ₹{values['Previous Close']:<8.2f} "
        f"| LTT: {values['Last Traded Time']}"
    )
print("========================================")