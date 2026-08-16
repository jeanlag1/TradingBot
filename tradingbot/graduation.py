"""Evaluate a paper book against the pre-registered graduation gates.

See docs/graduation.md for the commitment. Gates 1-3 are computable here; gates
4-5 (regime coverage, fresh walk-forward) are manual review gates surfaced as
reminders once 1-3 pass. Nothing here trades or graduates anything — it only
reports progress against a fixed bar so we can't move the goalposts later.
"""

from __future__ import annotations

MIN_DAYS = 90
SHARPE_EDGE = 0.20


def evaluate(book_stats: dict, champion_stats: dict, is_champion: bool) -> dict:
    """book_stats / champion_stats: {days, sharpe, mdd}. Returns gate results."""
    days = book_stats["days"]
    gates = [
        ("Track record ≥ 90 days", days >= MIN_DAYS, f"{days} / {MIN_DAYS}"),
        ("Sharpe ≥ champion + 0.20",
         book_stats["sharpe"] >= champion_stats["sharpe"] + SHARPE_EDGE,
         f"{book_stats['sharpe']:.2f} vs {champion_stats['sharpe'] + SHARPE_EDGE:.2f} needed"),
        ("Drawdown no worse than champion",
         book_stats["mdd"] >= champion_stats["mdd"],
         f"{book_stats['mdd']:.1%} vs {champion_stats['mdd']:.1%}"),
    ]
    manual = ["Regime coverage (1 trending + 1 choppy month)",
              "Fresh walk-forward at graduation"]
    auto_pass = all(g[1] for g in gates)
    return {
        "gates": gates,
        "manual": manual,
        "auto_pass": auto_pass,
        "is_champion": is_champion,
        # A challenger is "eligible" only if it clears autos AND beats the incumbent.
        "eligible_pending_review": auto_pass and not is_champion,
    }
