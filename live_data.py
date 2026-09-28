import os
import sys
import time
import random
import threading
from datetime import datetime
from dotenv import load_dotenv

import upstox_client
from instruments import get_instrument_key, get_multiple_instrument_keys

# Ensure Windows terminal doesn't crash on utf-8 characters
try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()

ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

# Default core watchlist symbols
DEFAULT_SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK"
]

# Baseline fallback prices when market is closed or offline
MOCK_BASELINES = {
    "RELIANCE": {"ltp": 1247.40, "cp": 1226.40},
    "TCS": {"ltp": 2128.70, "cp": 2105.00},
    "INFY": {"ltp": 1038.50, "cp": 1051.40},
    "HDFCBANK": {"ltp": 739.50, "cp": 731.00},
    "ICICIBANK": {"ltp": 1345.00, "cp": 1338.90},
    "BAJAJFINSV": {"ltp": 16684.00, "cp": 17368.85},
    "BAJFINANCE": {"ltp": 6780.00, "cp": 7125.80},
    "SBIN": {"ltp": 795.30, "cp": 790.10},
    "BHARTIARTL": {"ltp": 1720.50, "cp": 1705.00},
    "ITC": {"ltp": 472.10, "cp": 468.50},
    "KOTAKBANK": {"ltp": 1780.00, "cp": 1772.00},
    "LT": {"ltp": 3610.00, "cp": 3585.00},
    "ASIANPAINT": {"ltp": 3138.00, "cp": 3144.25},
    "AXISBANK": {"ltp": 661.00, "cp": 679.90},
    "CIPLA": {"ltp": 965.00, "cp": 899.95}
}


class LiveDataManager:
    """
    Thread-safe Singleton manager for Upstox WebSocket market data streaming
    with automated caching, dynamic symbol subscriptions, and offline simulation fallback.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LiveDataManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.stocks = {}  # symbol -> instrument_key
        self.key_to_symbol = {}  # instrument_key -> symbol
        self.latest_data = {}  # instrument_key -> {LTP, Previous Close, Last Traded Time}
        self.status = "DISCONNECTED"  # DISCONNECTED, CONNECTING, CONNECTED, SIMULATED, ERROR
        self.error_message = ""
        self.last_update_time = None
        self.data_lock = threading.Lock()
        self.feed_thread = None
        self.simulation_thread = None
        self.streamer = None
        self.is_running = False
        self.simulation_active = False

        # Preload default symbols using cached keys and baselines
        self.subscribe_symbols(DEFAULT_SYMBOLS, MOCK_BASELINES)

    def subscribe_symbols(self, symbols, initial_baselines=None):
        """
        Add symbols to the active subscription list and immediately initialize their price snapshot.
        If WebSocket streamer is currently running, actively subscribes to the new instrument keys.
        """
        new_keys = []
        with self.data_lock:
            for symbol in symbols:
                symbol = symbol.strip().upper()
                if symbol not in self.stocks:
                    key = get_instrument_key(symbol)
                    if key:
                        self.stocks[symbol] = key
                        self.key_to_symbol[key] = symbol
                        new_keys.append(key)

                        # Seed initial snapshot from baseline so symbol shows up immediately
                        base = None
                        if initial_baselines and symbol in initial_baselines:
                            base = initial_baselines[symbol]
                            MOCK_BASELINES[symbol] = base
                        elif symbol in MOCK_BASELINES:
                            base = MOCK_BASELINES[symbol]

                        if base and key not in self.latest_data:
                            self.latest_data[key] = {
                                "LTP": float(base["ltp"]),
                                "Previous Close": float(base.get("cp", base["ltp"])),
                                "Last Traded Time": str(int(time.time() * 1000))
                            }
                            self.last_update_time = datetime.now()

        # If streamer is running and connected, actively subscribe to the new keys on the WebSocket
        if self.streamer and new_keys and self.status == "CONNECTED":
            try:
                self.streamer.subscribe(new_keys, "ltpc")
                print(f"[INFO] Subscribed Upstox live streamer to: {new_keys}")
            except Exception as e:
                print(f"[WARN] Failed to dynamically subscribe keys on streamer: {e}")

        return new_keys

    def unsubscribe_symbols(self, symbols):
        """Remove symbols from active watchlist and WebSocket subscription."""
        removed_keys = []
        with self.data_lock:
            for symbol in symbols:
                symbol = symbol.strip().upper()
                if symbol in self.stocks:
                    key = self.stocks.pop(symbol)
                    self.key_to_symbol.pop(key, None)
                    self.latest_data.pop(key, None)
                    removed_keys.append(key)

        if self.streamer and removed_keys and self.status == "CONNECTED":
            try:
                self.streamer.unsubscribe(removed_keys)
                print(f"[INFO] Unsubscribed keys: {removed_keys}")
            except Exception as e:
                print(f"[WARN] Failed to unsubscribe keys: {e}")

        return removed_keys

    def on_message(self, message):
        """Handle incoming WebSocket tick payload."""
        try:
            feeds = message.get("feeds", {})
            with self.data_lock:
                for instrument_key, feed in feeds.items():
                    ltpc = feed.get("ltpc", {})
                    if "ltp" in ltpc:
                        self.latest_data[instrument_key] = {
                            "LTP": float(ltpc["ltp"]),
                            "Previous Close": float(ltpc.get("cp", 0)),
                            "Last Traded Time": ltpc.get("ltt", str(int(time.time() * 1000)))
                        }
                self.last_update_time = datetime.now()
                self.status = "CONNECTED"
        except Exception as e:
            print(f"Message processing error: {e}")

    def _run_streamer(self):
        """Internal worker function to establish Upstox MarketDataStreamer connection."""
        if not ACCESS_TOKEN:
            self.status = "ERROR"
            self.error_message = "UPSTOX_ACCESS_TOKEN not found in .env"
            print(self.error_message)
            return

        try:
            self.status = "CONNECTING"
            configuration = upstox_client.Configuration()
            configuration.access_token = ACCESS_TOKEN

            api_client = upstox_client.ApiClient(configuration)
            instrument_keys = list(self.stocks.values())

            if not instrument_keys:
                print("No instrument keys available to stream.")
                self.status = "DISCONNECTED"
                return

            print("Connecting to Upstox Market Streamer...")
            self.streamer = upstox_client.MarketDataStreamerV3(
                api_client,
                instrument_keys,
                "ltpc"
            )

            self.streamer.on("message", self.on_message)
            self.streamer.on("open", lambda: self._on_open())
            self.streamer.on("error", lambda err: self._on_error(err))
            self.streamer.on("close", lambda: self._on_close())

            self.streamer.connect()
        except Exception as e:
            self.status = "ERROR"
            self.error_message = str(e)
            print(f"Streamer connection error: {e}")

    def _on_open(self):
        print("[INFO] Upstox Live market connection opened successfully.")
        self.status = "CONNECTED"
        self.last_update_time = datetime.now()

        # Re-subscribe current stocks in case new symbols were added before open
        with self.data_lock:
            current_keys = list(self.stocks.values())
        if self.streamer and current_keys:
            try:
                self.streamer.subscribe(current_keys, "ltpc")
            except Exception as e:
                print(f"[WARN] Initial subscription error: {e}")

    def _on_error(self, error):
        print(f"[WARN] WebSocket error: {error}")
        self.error_message = str(error)

    def _on_close(self):
        print("[INFO] WebSocket connection closed.")
        if self.status != "SIMULATED":
            self.status = "DISCONNECTED"

    def start_background_feed(self):
        """Start the background live market stream."""
        if self.feed_thread and self.feed_thread.is_alive():
            return self.feed_thread

        self.is_running = True
        self.feed_thread = threading.Thread(target=self._run_streamer, daemon=True)
        self.feed_thread.start()
        return self.feed_thread

    def _run_simulation(self):
        """Generates realistic micro-ticks for demonstration when market is closed."""
        print("[INFO] Market simulation thread active.")
        while self.simulation_active:
            with self.data_lock:
                active_symbols = list(self.stocks.items())

            for symbol, key in active_symbols:
                base = MOCK_BASELINES.get(symbol, {"ltp": 1000.0, "cp": 990.0})
                with self.data_lock:
                    current_entry = self.latest_data.get(key)
                    if current_entry:
                        current_ltp = current_entry["LTP"]
                        cp = current_entry["Previous Close"]
                    else:
                        current_ltp = base["ltp"]
                        cp = base.get("cp", base["ltp"])

                    # Jitter price by +/- 0.15%
                    delta = (random.random() - 0.49) * 0.003 * current_ltp
                    new_ltp = round(max(1.0, current_ltp + delta), 2)

                    self.latest_data[key] = {
                        "LTP": new_ltp,
                        "Previous Close": cp,
                        "Last Traded Time": str(int(time.time() * 1000))
                    }
            with self.data_lock:
                self.last_update_time = datetime.now()
            time.sleep(2.0)

    def enable_simulation(self, enabled=True):
        """Enable or disable realistic tick simulation (ideal for off-hours testing)."""
        if enabled:
            if not self.simulation_active:
                self.simulation_active = True
                self.status = "SIMULATED"
                self.simulation_thread = threading.Thread(target=self._run_simulation, daemon=True)
                self.simulation_thread.start()
        else:
            self.simulation_active = False
            if self.status == "SIMULATED":
                self.status = "CONNECTED" if (self.feed_thread and self.feed_thread.is_alive()) else "DISCONNECTED"

    def get_latest_data(self):
        """Return a copy of latest raw tick records."""
        with self.data_lock:
            return self.latest_data.copy()

    def get_symbol_from_key(self, instrument_key):
        """Convert instrument key to stock symbol."""
        with self.data_lock:
            return self.key_to_symbol.get(instrument_key)

    def get_live_stock_data(self):
        """Get processed dictionary of {Symbol: {LTP, Previous Close, Last Traded Time}}."""
        raw_data = self.get_latest_data()
        result = {}
        with self.data_lock:
            for key, values in raw_data.items():
                symbol = self.key_to_symbol.get(key)
                if symbol:
                    result[symbol] = {
                        "LTP": values["LTP"],
                        "Previous Close": values["Previous Close"],
                        "Last Traded Time": values["Last Traded Time"]
                    }
        return result

    def calculate_live_change(self):
        """
        Calculate live percentage change from Previous Close.
        Returns: {Symbol: {LTP, Previous Close, Live Change, Last Traded Time}}
        """
        live_data = self.get_live_stock_data()
        result = {}

        for symbol, values in live_data.items():
            ltp = values["LTP"]
            previous_close = values["Previous Close"]

            if previous_close and previous_close != 0:
                change = ((ltp - previous_close) / previous_close) * 100
            else:
                change = 0.0

            result[symbol] = {
                "LTP": round(ltp, 2),
                "Previous Close": round(previous_close, 2),
                "Live Change": round(change, 2),
                "Last Traded Time": values["Last Traded Time"]
            }

        return result

    def get_status_summary(self):
        """Returns diagnostic info about streamer status and health."""
        with self.data_lock:
            return {
                "status": self.status,
                "error": self.error_message,
                "subscribed_count": len(self.stocks),
                "received_ticks_count": len(self.latest_data),
                "last_update": self.last_update_time.strftime("%H:%M:%S") if self.last_update_time else "Never",
                "is_simulated": self.simulation_active,
                "active_symbols": list(self.stocks.keys())
            }


# Module-level singleton instance
_manager = LiveDataManager()

# Expose backward-compatible global references and helper functions
STOCKS = _manager.stocks
latest_data = _manager.latest_data
start_background_feed = _manager.start_background_feed
get_latest_data = _manager.get_latest_data
get_symbol_from_key = _manager.get_symbol_from_key
get_live_stock_data = _manager.get_live_stock_data
calculate_live_change = _manager.calculate_live_change
get_status_summary = _manager.get_status_summary
enable_simulation = _manager.enable_simulation
subscribe_symbols = _manager.subscribe_symbols
unsubscribe_symbols = _manager.unsubscribe_symbols