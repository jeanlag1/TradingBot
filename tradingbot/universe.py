"""Universe selection: deciding *which* assets are tradeable, point-in-time.

Which coins we trade should not be a hardcoded list forever. Liquidity is the
first-order filter — an illiquid coin looks great in a backtest and then eats
you alive on slippage live. This module ranks candidates by trailing dollar
volume *as of a given date*, so the same logic can drive a live universe that
rotates as coins gain and lose liquidity.

Two important caveats to keep honest about:
  * **Survivorship bias.** We only have data for coins that exist and are listed
    today. Backtesting a universe of today's winners overstates results. Live
    selection (point-in-time, forward) does not have this problem — which is
    exactly why we build the selector to be time-aware now.
  * Liquidity is necessary, not sufficient. It gates *candidacy*; the signal
    still decides direction.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import requests

BASE_URL = "https://api.exchange.coinbase.com"


def list_usd_products() -> list[str]:
    """All live USD-quoted spot products on Coinbase (candidate discovery)."""
    resp = requests.get(f"{BASE_URL}/products", timeout=30)
    resp.raise_for_status()
    products = []
    for p in resp.json():
        if (
            p.get("quote_currency") == "USD"
            and p.get("status") == "online"
            and not p.get("trading_disabled")
            and not p.get("is_disabled")
        ):
            products.append(p["id"])
    return sorted(products)


def dollar_volume(df: pd.DataFrame, lookback: int = 30) -> pd.Series:
    """Rolling mean daily dollar volume (close * base volume)."""
    return (df["close"] * df["volume"]).rolling(lookback).mean()


def select_universe(
    data: dict[str, pd.DataFrame],
    as_of: Optional[pd.Timestamp] = None,
    top_n: int = 10,
    min_dollar_volume: float = 1e7,
    min_history: int = 200,
    lookback: int = 30,
) -> pd.DataFrame:
    """Rank candidates by trailing dollar volume as of ``as_of`` (default: latest).

    Filters out anything below ``min_dollar_volume`` or with less than
    ``min_history`` bars, then returns the top ``top_n`` by liquidity. Returns a
    DataFrame with columns ``[dollar_volume, bars]`` indexed by symbol.
    """
    rows = {}
    for sym, df in data.items():
        window = df if as_of is None else df.loc[df.index <= as_of]
        if len(window) < min_history:
            continue
        dv = float(dollar_volume(window, lookback).iloc[-1])
        if not (dv >= min_dollar_volume):
            continue
        rows[sym] = {"dollar_volume": dv, "bars": len(window)}

    frame = pd.DataFrame.from_dict(rows, orient="index")
    if frame.empty:
        return frame
    return frame.sort_values("dollar_volume", ascending=False).head(top_n)
