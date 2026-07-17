"""Robustness report: is the momentum edge real, or did we fit noise?

Runs three tests and prints them:
  1. Parameter sweep (Sharpe by lookback x asset) -> look for a plateau.
  2. Walk-forward OOS (tune on first 60%, test on last 40%) -> does it survive?
  3. Current liquidity-ranked universe -> the live asset-selection mechanism.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingbot import data, research, universe


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--assets", nargs="+",
                   default=["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD", "AVAX-USD"])
    p.add_argument("--days", type=int, default=1100)
    args = p.parse_args()

    dfs = {a: data.load(a, days=args.days) for a in args.assets}
    lookbacks = (30, 60, 90, 120, 180)

    print("\n" + "=" * 64)
    print("1. PARAMETER SWEEP  -  Sharpe by lookback x asset")
    print("   (robust = good across a range of rows and most columns)")
    print("=" * 64)
    sweep = research.param_sweep(dfs, lookbacks=lookbacks, metric="sharpe")
    with_avg = sweep.copy()
    with_avg["MEAN"] = sweep.mean(axis=1)
    print(with_avg.round(2).to_string())

    print("\n" + "=" * 64)
    print("2. WALK-FORWARD  -  tune lookback on first 60%, test on last 40%")
    print("   (OOS Sharpe should stay positive and beat buy-and-hold on risk)")
    print("=" * 64)
    print(f"{'asset':<10} {'IS best':>8} {'IS Shrp':>8} {'OOS Shrp':>9} "
          f"{'OOS CAGR':>9} {'OOS MDD':>8} {'B&H Shrp':>9} {'B&H MDD':>8}")
    for a, df in dfs.items():
        wf = research.walk_forward(df, lookbacks=lookbacks)
        oos, bh = wf["oos"], wf["oos_buy_hold"]
        print(f"{a:<10} {wf['best_lookback_is']:>8} {wf['is_sharpe']:>8.2f} "
              f"{oos['sharpe']:>9.2f} {oos['cagr']:>8.1%} {oos['max_drawdown']:>8.1%} "
              f"{bh['sharpe']:>9.2f} {bh['max_drawdown']:>8.1%}")

    print("\n" + "=" * 64)
    print("3. LIVE UNIVERSE  -  top assets by trailing dollar volume (today)")
    print("   (the mechanism that picks tradeable assets as we go live)")
    print("=" * 64)
    uni = universe.select_universe(dfs, top_n=10)
    if uni.empty:
        print("   (no assets passed the liquidity filter)")
    else:
        for sym, row in uni.iterrows():
            print(f"   {sym:<10} ${row['dollar_volume']/1e6:,.1f}M/day   {int(row['bars'])} bars")
    print()


if __name__ == "__main__":
    main()
