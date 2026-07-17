"""Paper-trading loop: run the real strategy against a persistent simulated book.

This is the bridge between backtest and live money. It uses the *same*
``ensemble_momentum`` signal the backtest uses, but instead of a vectorized
return series it maintains an actual portfolio — cash + per-asset units — that
persists to disk between runs. Each daily step:

  1. pull the latest candles,
  2. compute target weights from the shared signal,
  3. rebalance toward them (subject to a no-churn band), paying modeled costs,
  4. append a history row and save.

If ``backfill`` replays history and does NOT match ``backtest.run_portfolio``,
the live loop has a bug — that parity check is the whole point of this stage.
No real money until this has tracked the backtest live for weeks.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd

from . import backtest, data
from .strategies import ensemble_momentum

STATE_PATH = os.path.join(data.DATA_DIR, "paper_state.json")
DEFAULT_ASSETS = ["BTC-USD", "ETH-USD", "SOL-USD"]


# ---------------------------------------------------------------- state I/O ---
def init_state(equity: float = 2500.0, assets=DEFAULT_ASSETS, path: str = STATE_PATH) -> dict:
    state = {
        "created": datetime.now(timezone.utc).isoformat(),
        "assets": list(assets),
        "start_equity": float(equity),
        "cash": float(equity),
        "units": {a: 0.0 for a in assets},
        "history": [],
    }
    save_state(state, path)
    return state


def load_state(path: str = STATE_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def save_state(state: dict, path: str = STATE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


# ------------------------------------------------------------ core rebalance ---
def _equity(state: dict, prices: dict) -> float:
    return state["cash"] + sum(state["units"][a] * prices[a] for a in state["assets"])


def _rebalance(state, dfs_asof, prices, date, fee, slippage, band):
    """Apply one day's rebalance in place. Returns (equity_after, n_trades)."""
    assets = state["assets"]
    alloc = 1.0 / len(assets)
    equity = _equity(state, prices)

    n_trades = 0
    weights = {}
    for a in assets:
        w = float(ensemble_momentum(dfs_asof[a]).iloc[-1])  # shared signal
        weights[a] = w * alloc
        target_notional = weights[a] * equity
        current_notional = state["units"][a] * prices[a]
        delta = target_notional - current_notional

        # Skip trades smaller than the band to avoid churning on tiny drifts.
        if abs(delta) < band * equity:
            continue

        cost = abs(delta) * (fee + slippage)
        state["units"][a] += delta / prices[a]
        state["cash"] -= delta + cost
        n_trades += 1

    equity_after = _equity(state, prices)
    invested = sum(state["units"][a] * prices[a] for a in assets)
    state["history"].append({
        "date": date,
        "equity": equity_after,
        "cash": state["cash"],
        "invested": invested,
        "weights": weights,
        "prices": prices,
        "trades": n_trades,
    })
    return equity_after, n_trades


# ------------------------------------------------------------------- drivers ---
def step(fee=backtest.DEFAULT_FEE, slippage=backtest.DEFAULT_SLIPPAGE,
         band=0.05, path=STATE_PATH) -> tuple[dict, bool]:
    """Run one live daily step against the latest data. Idempotent per bar."""
    state = load_state(path)
    assets = state["assets"]
    dfs = {a: data.load(a, refresh=True) for a in assets}
    date = min(str(df.index[-1].date()) for df in dfs.values())

    if state["history"] and state["history"][-1]["date"] >= date:
        return state, False  # already stepped for this bar

    prices = {a: float(dfs[a]["close"].iloc[-1]) for a in assets}
    _rebalance(state, dfs, prices, date, fee, slippage, band)
    save_state(state, path)
    return state, True


def backfill(days=250, equity=2500.0, assets=DEFAULT_ASSETS,
             fee=backtest.DEFAULT_FEE, slippage=backtest.DEFAULT_SLIPPAGE,
             band=0.0, path=STATE_PATH) -> dict:
    """Replay the last ``days`` bars through the live loop to build history.

    Signals at each step use full history up to that bar (correct warmup), so
    with ``band=0`` this should reproduce the vectorized backtest closely.
    """
    state = init_state(equity, assets, path)
    dfs = {a: data.load(a) for a in assets}
    common = None
    for df in dfs.values():
        common = df.index if common is None else common.intersection(df.index)
    common = common.sort_values()

    for ts in common[-days:]:
        dfs_asof = {a: dfs[a].loc[:ts] for a in assets}
        prices = {a: float(dfs[a].loc[ts, "close"]) for a in assets}
        _rebalance(state, dfs_asof, prices, str(ts.date()), fee, slippage, band)
    save_state(state, path)
    return state


def equity_curve(state: dict) -> pd.Series:
    if not state["history"]:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([h["date"] for h in state["history"]])
    return pd.Series([h["equity"] for h in state["history"]], index=idx)
