"""Cache historical candles to data/ so backtests run offline and fast."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingbot import data


def main():
    p = argparse.ArgumentParser(description="Fetch and cache Coinbase candles.")
    p.add_argument("--products", nargs="+", default=["BTC-USD", "ETH-USD"])
    p.add_argument("--days", type=int, default=1100)
    p.add_argument("--granularity", type=int, default=86400, help="seconds per candle")
    args = p.parse_args()

    for product in args.products:
        df = data.load(product, args.granularity, args.days, refresh=True)
        print(f"{product}: {len(df)} candles  {df.index[0].date()} -> {df.index[-1].date()}")


if __name__ == "__main__":
    main()
