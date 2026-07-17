"""Run a strategy through the backtester and print a performance report.

Always prints buy-and-hold alongside the strategy: a trend strategy that can't
beat (or at least meaningfully de-risk vs.) just holding the asset isn't earning
its complexity.
"""

import argparse
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingbot import backtest, data, metrics, risk
from tradingbot.strategies import REGISTRY


def main():
    p = argparse.ArgumentParser(description="Backtest a strategy.")
    p.add_argument("--product", default="BTC-USD")
    p.add_argument("--strategy", default="sma_crossover", choices=sorted(REGISTRY))
    p.add_argument("--fee", type=float, default=backtest.DEFAULT_FEE)
    p.add_argument("--slippage", type=float, default=backtest.DEFAULT_SLIPPAGE)
    p.add_argument("--vol-target", type=float, default=None,
                   help="if set, scale exposure to this annualized vol (e.g. 0.40)")
    p.add_argument("--days", type=int, default=1100)
    args = p.parse_args()

    df = data.load(args.product, days=args.days)
    signal = REGISTRY[args.strategy]

    risk_fn = None
    if args.vol_target is not None:
        risk_fn = partial(risk.vol_target, target_ann_vol=args.vol_target)

    strat = backtest.run(df, signal, fee=args.fee, slippage=args.slippage, risk_fn=risk_fn)
    hold = backtest.run(df, REGISTRY["buy_and_hold"], fee=args.fee, slippage=args.slippage)

    label = args.strategy + (f" (vol@{args.vol_target:.0%})" if args.vol_target else "")
    print(metrics.format_report(f"{args.product}  buy_and_hold", metrics.summary(hold.net_returns, hold.position)))
    print(metrics.format_report(f"{args.product}  {label}", metrics.summary(strat.net_returns, strat.position)))


if __name__ == "__main__":
    main()
