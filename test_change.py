import time
from live_data import start_background_feed, calculate_live_change, get_status_summary

print("========================================")
print("TradeMind AI - Live Stock Changes Test")
print("========================================")
print("Starting live feed...")
start_background_feed()

print("Waiting 5 seconds for live market ticks...")
time.sleep(5)

data = calculate_live_change()
status = get_status_summary()

print(f"\nFeed Status: {status['status']} (Last tick: {status['last_update']})")
print("----------------------------------------")
print(f"{'SYMBOL':<12} {'LTP (₹)':<10} {'PREV CLOSE':<12} {'CHANGE (%)':<10}")
print("----------------------------------------")

for symbol, values in data.items():
    sign = "+" if values["Live Change"] >= 0 else ""
    print(
        f"{symbol:<12} "
        f"{values['LTP']:<10.2f} "
        f"{values['Previous Close']:<12.2f} "
        f"{sign}{values['Live Change']:.2f}%"
    )
print("========================================")