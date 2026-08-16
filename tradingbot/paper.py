"""Multi-model paper-trading: run the whole roster in parallel on simulated books.

Each model in ``models.ROSTER`` gets its own persistent book (cash + per-asset
units) under ``data/paper/<name>.json``. One daily ``step_all`` advances every
book using the *same* ``models.weight_series`` the backtester uses, so every
challenger is validated exactly as it would trade. Shorting is simulated
(negative units, inverse P&L, a daily funding carry) — no perps API, no real
money. Nothing here risks a dollar; it exists to generate parallel feedback so we
can compare strategies live without betting on any of them.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd

from . import backtest, data, models

BOOK_DIR = os.path.join(data.DATA_DIR, "paper")
START_EQUITY = 2500.0


def _book_path(name: str) -> str:
    return os.path.join(BOOK_DIR, f"{name}.json")


# ---------------------------------------------------------------- state I/O ---
def init_book(spec, equity: float = START_EQUITY) -> dict:
    book = {
        "name": spec.name,
        "family": spec.family,
        "rationale": spec.rationale,
        "created": datetime.now(timezone.utc).isoformat(),
        "assets": list(spec.assets),
        "start_equity": float(equity),
        "cash": float(equity),
        "units": {a: 0.0 for a in spec.assets},
        "history": [],
    }
    save_book(book)
    return book


def load_book(name: str) -> dict:
    with open(_book_path(name)) as f:
        return json.load(f)


def save_book(book: dict) -> None:
    os.makedirs(BOOK_DIR, exist_ok=True)
    with open(_book_path(book["name"]), "w") as f:
        json.dump(book, f, indent=2)


def _equity(book: dict, prices: dict) -> float:
    return book["cash"] + sum(book["units"][a] * prices[a] for a in book["assets"])


# ------------------------------------------------------------ core rebalance ---
def _rebalance(spec, book, dfs_asof, prices, date, fee, slippage):
    """Advance one book by one bar, in place. Handles longs and shorts."""
    from . import risk  # noqa: F401  (kept explicit for parity with backtest path)

    assets = book["assets"]
    alloc = 1.0 / len(assets)
    equity = _equity(book, prices)
    band = spec.rebalance_band

    n_trades = 0
    weights = {}
    for a in assets:
        w = float(models.weight_series(spec, dfs_asof[a]).iloc[-1])
        weights[a] = w * alloc
        target_notional = weights[a] * equity          # may be negative (short)
        current_notional = book["units"][a] * prices[a]
        delta = target_notional - current_notional

        if abs(delta) < band * equity:                 # inside the no-churn band
            continue

        cost = abs(delta) * (fee + slippage)
        book["units"][a] += delta / prices[a]
        book["cash"] -= delta + cost
        n_trades += 1

    # Daily funding carry on any short exposure (honest simulation of perps).
    short_notional = sum(-book["units"][a] * prices[a]
                         for a in assets if book["units"][a] < 0)
    funding = short_notional * spec.short_funding_daily
    book["cash"] -= funding

    equity_after = _equity(book, prices)
    invested = sum(book["units"][a] * prices[a] for a in assets)
    book["history"].append({
        "date": date, "equity": equity_after, "cash": book["cash"],
        "invested": invested, "weights": weights, "prices": prices,
        "trades": n_trades, "funding": funding,
    })
    return equity_after


# ------------------------------------------------------------------- drivers ---
def step_all(fee=backtest.DEFAULT_FEE, slippage=backtest.DEFAULT_SLIPPAGE) -> dict:
    """Advance every book by one bar against the latest data. Idempotent per bar.

    Auto-initializes any newly-added roster model before stepping, so the zoo can
    grow without a manual backfill (new books just start from today).
    """
    all_syms = sorted({a for m in models.ROSTER for a in m.assets})
    dfs = {a: data.load(a, refresh=True) for a in all_syms}
    date = min(str(dfs[a].index[-1].date()) for a in all_syms)

    summary = {"date": date, "stepped": [], "skipped": []}
    for spec in models.ROSTER:
        if not os.path.exists(_book_path(spec.name)):
            init_book(spec)
        book = load_book(spec.name)
        if book["history"] and book["history"][-1]["date"] >= date:
            summary["skipped"].append(spec.name)
            continue
        prices = {a: float(dfs[a]["close"].iloc[-1]) for a in spec.assets}
        dfs_asof = {a: dfs[a] for a in spec.assets}
        _rebalance(spec, book, dfs_asof, prices, date, fee, slippage)
        save_book(book)
        summary["stepped"].append(spec.name)
    return summary


def backfill_all(days=250, equity=START_EQUITY,
                 fee=backtest.DEFAULT_FEE, slippage=backtest.DEFAULT_SLIPPAGE) -> None:
    """Replay the last ``days`` bars through every book (fresh start each)."""
    all_syms = sorted({a for m in models.ROSTER for a in m.assets})
    dfs = {a: data.load(a) for a in all_syms}

    for spec in models.ROSTER:
        common = None
        for a in spec.assets:
            common = dfs[a].index if common is None else common.intersection(dfs[a].index)
        common = common.sort_values()

        book = init_book(spec, equity)
        for ts in common[-days:]:
            dfs_asof = {a: dfs[a].loc[:ts] for a in spec.assets}
            prices = {a: float(dfs[a].loc[ts, "close"]) for a in spec.assets}
            _rebalance(spec, book, dfs_asof, prices, str(ts.date()), fee, slippage)
        save_book(book)


def equity_curve(book: dict) -> pd.Series:
    if not book["history"]:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([h["date"] for h in book["history"]])
    return pd.Series([h["equity"] for h in book["history"]], index=idx)


def load_all() -> list[dict]:
    return [load_book(m.name) for m in models.ROSTER if os.path.exists(_book_path(m.name))]
