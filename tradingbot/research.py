"""Robustness research: parameter sweeps and walk-forward out-of-sample tests.

The point of this module is to *try to disprove* a strategy before trusting it.
An edge that only shows up at one parameter value, on one asset, in one time
window is almost certainly overfit noise. A real edge shows a broad plateau of
decent parameters, works across several assets, and survives on data it was
never tuned on.

Functions return plain DataFrames / dicts so a future dashboard can render them
directly.
"""

from __future__ import annotations

from functools import partial

import pandas as pd

from . import backtest, metrics
from .strategies import ts_momentum, buy_and_hold


def _momentum(lookback: int):
    return partial(ts_momentum, lookback=lookback)


def param_sweep(
    data: dict[str, pd.DataFrame],
    lookbacks=(30, 60, 90, 120, 180),
    metric: str = "sharpe",
    **bt_kwargs,
) -> pd.DataFrame:
    """Sweep momentum lookbacks across assets.

    Returns a DataFrame indexed by lookback, one column per asset, holding the
    chosen ``metric`` (default Sharpe). Scan it for a plateau: robust params are
    good across a *range* of lookbacks and *most* assets, not a lone spike.
    """
    out = {}
    for sym, df in data.items():
        col = {}
        for lb in lookbacks:
            res = backtest.run(df, _momentum(lb), **bt_kwargs)
            stats = metrics.summary(res.net_returns, res.position)
            col[lb] = stats.get(metric, float("nan"))
        out[sym] = col
    frame = pd.DataFrame(out)
    frame.index.name = f"lookback ({metric})"
    return frame


def evaluate_split(net_returns: pd.Series, position: pd.Series, split: float = 0.6) -> dict:
    """Report full / in-sample / out-of-sample stats for one return stream.

    Used for strategies with no parameter to tune (e.g. the ensemble) — we're
    not choosing anything on the in-sample data, just checking the *same* fixed
    strategy holds up on the untouched tail.
    """
    n = len(net_returns)
    cut = int(n * split)
    return {
        "full": metrics.summary(net_returns, position),
        "is": metrics.summary(net_returns.iloc[:cut], position.iloc[:cut]),
        "oos": metrics.summary(net_returns.iloc[cut:], position.iloc[cut:]),
    }


def walk_forward(
    df: pd.DataFrame,
    lookbacks=(30, 60, 90, 120, 180),
    split: float = 0.6,
    **bt_kwargs,
) -> dict:
    """Tune the lookback on the first ``split`` of the data, test on the rest.

    Picks the best-Sharpe lookback in-sample, then reports its performance on the
    untouched out-of-sample tail alongside buy-and-hold over that same tail. If
    the OOS result collapses, the in-sample tuning was fitting noise.
    """
    n = len(df)
    cut = int(n * split)
    is_df = df.iloc[:cut]

    best_lb, best_sharpe = None, float("-inf")
    for lb in lookbacks:
        res = backtest.run(is_df, _momentum(lb), **bt_kwargs)
        stats = metrics.summary(res.net_returns, res.position)
        if stats and stats["sharpe"] > best_sharpe:
            best_lb, best_sharpe = lb, stats["sharpe"]

    # Run on the FULL series (so the OOS segment has its warmup history) then
    # slice out only the out-of-sample tail for scoring — no cold-start bias.
    full = backtest.run(df, _momentum(best_lb), **bt_kwargs)
    oos_stats = metrics.summary(full.net_returns.iloc[cut:], full.position.iloc[cut:])

    hold = backtest.run(df, buy_and_hold, **bt_kwargs)
    hold_oos = metrics.summary(hold.net_returns.iloc[cut:], hold.position.iloc[cut:])

    return {
        "best_lookback_is": best_lb,
        "is_sharpe": best_sharpe,
        "oos": oos_stats,
        "oos_buy_hold": hold_oos,
    }
