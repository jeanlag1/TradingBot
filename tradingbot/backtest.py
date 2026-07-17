"""Vectorized backtester with realistic costs and no lookahead.

The core contract: a strategy decides a target weight on the close of day *t*;
that weight is only earned on day *t+1*'s return (``position = weight.shift(1)``).
Every change in position pays fees + slippage on the traded fraction. A strategy
that isn't profitable *after* these costs is not a strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

import pandas as pd

# Coinbase Advanced Trade taker fee at the entry volume tier, per side.
# Deliberately conservative — better to be pessimistic in a backtest.
DEFAULT_FEE = 0.006
DEFAULT_SLIPPAGE = 0.0005


@dataclass
class BacktestResult:
    equity: pd.Series
    net_returns: pd.Series
    position: pd.Series          # weight actually held each day (post-shift)
    gross_returns: pd.Series
    costs: pd.Series


def run(
    df: pd.DataFrame,
    signal: Callable[[pd.DataFrame], pd.Series],
    fee: float = DEFAULT_FEE,
    slippage: float = DEFAULT_SLIPPAGE,
    risk_fn: Optional[Callable[[pd.Series, pd.Series], pd.Series]] = None,
) -> BacktestResult:
    """Backtest ``signal`` on OHLCV ``df``.

    ``signal(df) -> target weight in [0, 1]``. ``risk_fn(weight, close) ->
    adjusted weight`` is applied after the raw signal (e.g. vol targeting).
    """
    close = df["close"]
    asset_ret = close.pct_change().fillna(0.0)

    weight = signal(df).clip(lower=0.0, upper=1.0)
    if risk_fn is not None:
        weight = risk_fn(weight, close)
    weight = weight.reindex(df.index).fillna(0.0)

    # No lookahead: today's return is earned on yesterday's decided weight.
    position = weight.shift(1).fillna(0.0)

    # Costs hit on the fraction of the book we turn over when position changes.
    turnover = position.diff().abs().fillna(position.abs())
    costs = turnover * (fee + slippage)

    gross_returns = position * asset_ret
    net_returns = gross_returns - costs
    equity = (1.0 + net_returns).cumprod()

    return BacktestResult(
        equity=equity,
        net_returns=net_returns,
        position=position,
        gross_returns=gross_returns,
        costs=costs,
    )


@dataclass
class PortfolioResult:
    equity: pd.Series
    net_returns: pd.Series
    gross_exposure: pd.Series     # total capital deployed each day, in [0, 1]
    per_asset_position: pd.DataFrame
    trades: int


def run_portfolio(
    data: Dict[str, pd.DataFrame],
    signal: Callable[[pd.DataFrame], pd.Series],
    fee: float = DEFAULT_FEE,
    slippage: float = DEFAULT_SLIPPAGE,
    risk_fn: Optional[Callable[[pd.Series, pd.Series], pd.Series]] = None,
    allocation: Optional[float] = None,
) -> PortfolioResult:
    """Backtest an equal-weight basket, applying ``signal`` to each asset.

    Each asset may claim up to ``allocation`` of capital (default 1/N) when its
    signal is on, and sits in cash otherwise — so the basket is long/flat and
    never leveraged past 100% deployed. Costs are charged per asset on its own
    turnover. Returns are summed across assets on the shared date index.
    """
    symbols = list(data)
    n = len(symbols)
    alloc = allocation if allocation is not None else 1.0 / n

    # Align every asset to the common set of dates.
    idx = None
    for df in data.values():
        idx = df.index if idx is None else idx.intersection(df.index)
    idx = idx.sort_values()

    contributions, positions, turnovers = [], {}, []
    for sym in symbols:
        df = data[sym].reindex(idx)
        close = df["close"]
        asset_ret = close.pct_change().fillna(0.0)

        weight = signal(df).clip(lower=0.0, upper=1.0)
        if risk_fn is not None:
            weight = risk_fn(weight, close)
        weight = (weight.reindex(idx).fillna(0.0)) * alloc

        position = weight.shift(1).fillna(0.0)   # no lookahead
        turnover = position.diff().abs().fillna(position.abs())

        contributions.append(position * asset_ret - turnover * (fee + slippage))
        positions[sym] = position
        turnovers.append(turnover)

    net_returns = sum(contributions)
    per_asset = pd.DataFrame(positions)
    gross_exposure = per_asset.sum(axis=1)
    total_turnover = sum(turnovers)
    trades = int((total_turnover > 1e-9).sum())
    equity = (1.0 + net_returns).cumprod()

    return PortfolioResult(
        equity=equity,
        net_returns=net_returns,
        gross_exposure=gross_exposure,
        per_asset_position=per_asset,
        trades=trades,
    )
