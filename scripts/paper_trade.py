"""Drive the multi-model paper zoo.

  --step               advance every book one bar (idempotent; safe to cron)
  --status             leaderboard: every model ranked by risk-adjusted return
  --backfill 250       replay the last N bars through every book (fresh start)
  --backfill-new 250   only backfill books that don't exist yet (keeps live ones)
  --compare            (with --backfill) parity check vs run_spec per model
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingbot import backtest, data, metrics, models, paper


def _stats(book):
    curve = paper.equity_curve(book)
    if len(curve) < 2:
        return None
    rets = curve.pct_change().dropna()
    return metrics.summary(rets, (rets != 0).astype(float))


def leaderboard():
    books = paper.load_all()
    rows = []
    for b in books:
        s = _stats(b)
        eq = b["history"][-1]["equity"] if b["history"] else b["start_equity"]
        ret = eq / b["start_equity"] - 1
        rows.append((b["name"], b["family"], len(b["history"]), ret,
                     s["sharpe"] if s else 0.0,
                     metrics.max_drawdown(paper.equity_curve(b)) if b["history"] else 0.0))
    # Rank by Sharpe (risk-adjusted), not raw return — the whole discipline.
    rows.sort(key=lambda r: r[4], reverse=True)
    print(f"\n{'model':<16}{'family':<13}{'days':>5}{'return':>9}{'Sharpe':>8}{'maxDD':>8}   note")
    print("-" * 78)
    for name, fam, days, ret, sharpe, mdd in rows:
        star = " *" if name == models.CHAMPION else ""
        print(f"{name:<16}{fam:<13}{days:>5}{ret:>+9.2%}{sharpe:>8.2f}{mdd:>8.1%}{star}")
    print(f"\n  * = champion (current live book). Ranked by Sharpe. "
          f"Judge on risk-adjusted terms + track record, never raw return.")


def compare(days):
    dfs = {a: data.load(a) for a in sorted({a for m in models.ROSTER for a in m.assets})}
    print(f"\n--- Parity: paper book vs run_spec backtest (last {days} bars) ---")
    print(f"{'model':<16}{'paper':>10}{'backtest':>11}{'diff':>8}")
    for spec in models.ROSTER:
        book = paper.load_book(spec.name)
        paper_mult = book["history"][-1]["equity"] / book["start_equity"]
        bt = backtest.run_spec(spec, {a: dfs[a] for a in spec.assets})
        bt_mult = float((1.0 + bt.net_returns).tail(days).prod())
        diff = abs(bt_mult - paper_mult) / bt_mult
        flag = "ok" if diff < 0.03 else "CHECK"
        print(f"{spec.name:<16}{paper_mult:>10.4f}{bt_mult:>11.4f}{diff:>7.1%} {flag}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--step", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--backfill", type=int, metavar="DAYS")
    p.add_argument("--backfill-new", type=int, metavar="DAYS")
    p.add_argument("--compare", action="store_true")
    args = p.parse_args()

    if args.backfill:
        paper.backfill_all(days=args.backfill)
        print(f"Backfilled all {len(models.ROSTER)} books ({args.backfill} bars).")
        if args.compare:
            compare(args.backfill)
        leaderboard()
        return

    if args.backfill_new:
        made = []
        for spec in models.ROSTER:
            if not os.path.exists(paper._book_path(spec.name)):
                # Backfill just this new book over the window.
                import pandas as pd
                dfs = {a: data.load(a) for a in spec.assets}
                common = None
                for a in spec.assets:
                    common = dfs[a].index if common is None else common.intersection(dfs[a].index)
                book = paper.init_book(spec)
                for ts in common.sort_values()[-args.backfill_new:]:
                    prices = {a: float(dfs[a].loc[ts, "close"]) for a in spec.assets}
                    paper._rebalance(spec, book, {a: dfs[a].loc[:ts] for a in spec.assets},
                                     prices, str(ts.date()), backtest.DEFAULT_FEE, backtest.DEFAULT_SLIPPAGE)
                paper.save_book(book)
                made.append(spec.name)
        print(f"Backfilled {len(made)} new books: {', '.join(made) or '(none)'}")
        leaderboard()
        return

    if args.step:
        summary = paper.step_all()
        print(f"Stepped {len(summary['stepped'])}, skipped {len(summary['skipped'])} "
              f"(bar {summary['date']}).")
        leaderboard()
        return

    if args.status:
        leaderboard()


if __name__ == "__main__":
    main()
