"""Drive the paper-trading loop.

  --init 2500        start a fresh $2500 paper book
  --step             run one live daily step (idempotent; safe to cron daily)
  --status           show current holdings, equity, and realized stats
  --backfill 250     replay the last 250 bars to build history
  --compare          (with --backfill) check parity vs the vectorized backtest
  --reset            delete the paper state
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingbot import backtest, data, metrics, paper
from tradingbot.strategies import ensemble_momentum


def show_status(state):
    hist = state["history"]
    if not hist:
        print("No history yet. Run --step or --backfill.")
        return
    last = hist[-1]
    curve = paper.equity_curve(state)
    rets = curve.pct_change().dropna()
    start, now = state["start_equity"], last["equity"]
    print(f"\nPaper book  ({len(hist)} steps, latest {last['date']})")
    print(f"  Start equity:   ${start:,.2f}")
    print(f"  Current equity: ${now:,.2f}   ({now/start - 1:+.2%})")
    print(f"  Cash:           ${last['cash']:,.2f}   Invested: ${last['invested']:,.2f}")
    print("  Holdings:")
    for a in state["assets"]:
        units = state["units"][a]
        px = last["prices"][a]
        print(f"    {a:<9} {units:>12.6f} units  = ${units*px:,.2f}  "
              f"(target weight {last['weights'][a]:.0%})")
    if len(rets) > 2:
        s = metrics.summary(rets, curve.ne(curve.shift()).astype(float))
        print(f"  Realized:  Sharpe {s['sharpe']:.2f}   "
              f"MaxDD {metrics.max_drawdown(curve):.1%}   "
              f"total trades {sum(h['trades'] for h in hist)}")


def compare_to_backtest(state, days):
    """Paper replay (band=0) should match the vectorized backtest closely."""
    dfs = {a: data.load(a) for a in state["assets"]}
    bt = backtest.run_portfolio(dfs, ensemble_momentum)
    bt_mult = float((1.0 + bt.net_returns).tail(days).prod())
    paper_mult = state["history"][-1]["equity"] / state["start_equity"]
    print("\n--- Parity check: paper loop vs vectorized backtest (last "
          f"{days} bars) ---")
    print(f"  Backtest equity multiple: {bt_mult:.4f}x")
    print(f"  Paper    equity multiple: {paper_mult:.4f}x")
    diff = abs(bt_mult - paper_mult) / bt_mult
    verdict = "OK — loop reproduces the backtest" if diff < 0.02 else "MISMATCH — investigate"
    print(f"  Relative difference:      {diff:.2%}   [{verdict}]")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--init", type=float, metavar="EQUITY")
    p.add_argument("--step", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--backfill", type=int, metavar="DAYS")
    p.add_argument("--compare", action="store_true")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--band", type=float, default=0.05)
    args = p.parse_args()

    if args.reset:
        if os.path.exists(paper.STATE_PATH):
            os.remove(paper.STATE_PATH)
        print("Paper state reset.")
        return

    if args.init is not None:
        paper.init_state(args.init)
        print(f"Initialized paper book at ${args.init:,.2f}")

    if args.backfill:
        band = 0.0 if args.compare else args.band
        state = paper.backfill(days=args.backfill, band=band)
        print(f"Backfilled {len(state['history'])} steps (band={band}).")
        if args.compare:
            compare_to_backtest(state, args.backfill)
        show_status(state)
        return

    if args.step:
        state, stepped = paper.step(band=args.band)
        print("Stepped." if stepped else "Already up to date for the latest bar.")
        show_status(state)
        return

    if args.status:
        show_status(paper.load_state())


if __name__ == "__main__":
    main()
