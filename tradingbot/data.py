"""Historical candle ingestion from Coinbase's public Exchange API.

The endpoint requires no authentication and returns daily (or intraday) candles
as ``[time, low, high, open, close, volume]``, newest-first, capped at 300
candles per request. We paginate backwards and cache the result as a CSV so we
only hit the network once per (product, granularity).
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

BASE_URL = "https://api.exchange.coinbase.com"
MAX_CANDLES = 300  # Coinbase per-request limit
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Column order returned by the API.
_RAW_COLS = ["time", "low", "high", "open", "close", "volume"]


def _cache_path(product: str, granularity: int) -> str:
    return os.path.join(DATA_DIR, f"{product}_{granularity}.csv")


def fetch_candles(
    product: str = "BTC-USD",
    granularity: int = 86400,
    days: int = 1100,
    pause: float = 0.34,
) -> pd.DataFrame:
    """Fetch ``days`` of candles for ``product`` at ``granularity`` seconds.

    Returns a DataFrame indexed by UTC timestamp with columns
    ``[open, high, low, close, volume]``, sorted oldest-first.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    span = timedelta(seconds=granularity * MAX_CANDLES)

    frames = []
    window_start = start
    while window_start < end:
        window_end = min(window_start + span, end)
        params = {
            "granularity": granularity,
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
        }
        resp = requests.get(
            f"{BASE_URL}/products/{product}/candles", params=params, timeout=30
        )
        resp.raise_for_status()
        rows = resp.json()
        if rows:
            frames.append(pd.DataFrame(rows, columns=_RAW_COLS))
        window_start = window_end
        time.sleep(pause)  # stay under the public rate limit (~10 req/s)

    if not frames:
        raise RuntimeError(f"No candle data returned for {product}")

    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = (
        df.drop_duplicates(subset="time")
        .set_index("time")
        .sort_index()[["open", "high", "low", "close", "volume"]]
        .astype(float)
    )
    return df


def load(
    product: str = "BTC-USD",
    granularity: int = 86400,
    days: int = 1100,
    refresh: bool = False,
) -> pd.DataFrame:
    """Load candles from local cache, fetching from the network if needed."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _cache_path(product, granularity)
    if os.path.exists(path) and not refresh:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df
    df = fetch_candles(product, granularity, days)
    df.to_csv(path)
    return df


if __name__ == "__main__":
    d = load("BTC-USD", refresh=True)
    print(f"Loaded {len(d)} BTC-USD daily candles: {d.index[0].date()} -> {d.index[-1].date()}")
    print(d.tail())
