"""Ensemble-momentum basket vs. buy-and-hold basket, split full / IS / OOS.

The two overfitting fixes, tested together:
  * ENSEMBLE: average momentum over 30/60/90/120d -> no single-lookback bet.
  * BASKET: equal-weight BTC/ETH/SOL -> diversification.

We report the SAME fixed strategy over the full period, the first 60%, and the
untouched last 40%. Nothing is tuned on the data, so a stable OOS result here is
meaningfully more trustworthy than the single-asset walk-forward that collapsed.
"""

import argparse
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingbot import backtest, data, research, risk
from tradingbot.strategies import ensemble_momentum, buy_and_hold


def row(name, stats):
    return (f"  {name:<26} {stats['cagr']:>7.1%} {stats['sharpe']:>7.2f} "
            f"{stats['max_drawdown']:>8.1%} {stats['calmar']:>7.2f} "
            f"{stats['exposure']:>7.0%}")


def report(title, result):
    split = research.evaluate_split(result.net_returns, result.gross_exposure)
    print(f"\n{title}   (basket trades: {result.trades})")
    print(f"  {'segment':<26} {'CAGR':>7} {'Sharpe':>7} {'MaxDD':>8} {'Calmar':>7} {'Expo':>7}")
    print(row("full period", split["full"]))
    print(row("in-sample (first 60%)", split["is"]))
    print(row("out-of-sample (last 40%)", split["oos"]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--assets", nargs="+", default=["BTC-USD", "ETH-USD", "SOL-USD"])
    p.add_argument("--days", type=int, default=1100)
    args = p.parse_args()

    dfs = {a: data.load(a, days=args.days) for a in args.assets}
    print("=" * 62)
    print(f"BASKET: {', '.join(args.assets)}  (equal weight, long/flat)")
    print("=" * 62)

    hold = backtest.run_portfolio(dfs, buy_and_hold)
    report("BUY & HOLD basket", hold)

    ens = backtest.run_portfolio(dfs, ensemble_momentum)
    report("ENSEMBLE momentum basket", ens)

    ens_vt = backtest.run_portfolio(
        dfs, ensemble_momentum, risk_fn=partial(risk.vol_target, target_ann_vol=0.30)
    )
    report("ENSEMBLE + vol-target 30%", ens_vt)
    print()


if __name__ == "__main__":
    main()
