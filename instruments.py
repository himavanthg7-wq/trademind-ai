import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "instrument_keys.json")

# Pre-populated cache for top NSE stocks to ensure fast and offline-capable startup
DEFAULT_INSTRUMENT_KEYS = {
    "RELIANCE": "NSE_EQ|INE002A01018",
    "TCS": "NSE_EQ|INE467B01029",
    "INFY": "NSE_EQ|INE009A01021",
    "HDFCBANK": "NSE_EQ|INE040A01034",
    "ICICIBANK": "NSE_EQ|INE090A01021",
    "SBIN": "NSE_EQ|INE062A01020",
    "BHARTIARTL": "NSE_EQ|INE397D01024",
    "ITC": "NSE_EQ|INE154A01025",
    "KOTAKBANK": "NSE_EQ|INE237A01028",
    "LT": "NSE_EQ|INE018A01030",
    "AXISBANK": "NSE_EQ|INE238A01034",
    "ASIANPAINT": "NSE_EQ|INE021A01026",
    "MARUTI": "NSE_EQ|INE585B01010",
    "SUNPHARMA": "NSE_EQ|INE044A01036",
    "TITAN": "NSE_EQ|INE280A01028",
    "BAJFINANCE": "NSE_EQ|INE296A01024",
    "BAJAJFINSV": "NSE_EQ|INE918I01018",
    "HINDUNILVR": "NSE_EQ|INE030A01027",
    "WIPRO": "NSE_EQ|INE075A01022",
    "TATAMOTORS": "NSE_EQ|INE155A01022",
    "TATASTEEL": "NSE_EQ|INE081A01020",
    "NTPC": "NSE_EQ|INE733E01010",
    "POWERGRID": "NSE_EQ|INE752E01010",
    "ONGC": "NSE_EQ|INE213A01029",
    "COALINDIA": "NSE_EQ|INE522F01014"
}


def load_cache():
    """Load cached instrument keys from disk."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge defaults with disk cache
                merged = DEFAULT_INSTRUMENT_KEYS.copy()
                merged.update(data)
                return merged
        except Exception as e:
            print(f"Warning: Could not read instrument cache: {e}")
    return DEFAULT_INSTRUMENT_KEYS.copy()


def save_cache(cache_data):
    """Save instrument keys cache to disk."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save instrument cache: {e}")


# Initialize in-memory cache
_cache = load_cache()


def get_instrument_key(symbol):
    """
    Retrieve Upstox instrument key for a given NSE symbol.
    Checks memory/disk cache first before querying Upstox API.
    """
    symbol = symbol.strip().upper()

    if symbol in _cache and _cache[symbol]:
        return _cache[symbol]

    if not ACCESS_TOKEN:
        return None

    url = "https://api.upstox.com/v2/instruments/search"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    params = {
        "query": symbol,
        "exchanges": "NSE",
        "segments": "EQ",
        "instrument_types": "EQ",
        "page_number": 1,
        "records": 30
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code != 200:
            return None

        data = response.json()
        instruments = data.get("data", [])

        for instrument in instruments:
            if (
                instrument.get("exchange") == "NSE"
                and instrument.get("segment") == "NSE_EQ"
                and instrument.get("instrument_type") == "EQ"
                and instrument.get("trading_symbol") == symbol
            ):
                key = instrument.get("instrument_key")
                _cache[symbol] = key
                save_cache(_cache)
                return key
    except Exception as e:
        print(f"Error fetching instrument key for {symbol}: {e}")

    return None


def get_multiple_instrument_keys(symbols):
    """Resolve instrument keys for a list of symbols."""
    results = {}
    for s in symbols:
        key = get_instrument_key(s)
        if key:
            results[s] = key
    return results


if __name__ == "__main__":
    symbols = [
        "RELIANCE",
        "TCS",
        "INFY",
        "HDFCBANK",
        "ICICIBANK"
    ]

    print("Resolving instrument keys:")
    for sym in symbols:
        k = get_instrument_key(sym)
        print(f"  {sym} -> {k}")