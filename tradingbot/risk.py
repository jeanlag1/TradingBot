"""Risk management: volatility targeting and a hard drawdown kill-switch.

This is the module that separates people who keep their money from people who
blow up. A raw signal says *which direction*; risk says *how much* and *when to
stop*. Both functions take a target weight in [0, 1] and return an adjusted
weight in [0, 1] — so they compose with any strategy and stay spot/long-flat.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = 365


def apply_rebalance_band(target: pd.Series, band: float) -> pd.Series:
    """Only move to a new target when it differs from the held weight by ``band``.

    Continuous sizing (e.g. vol targeting) drifts a little every day; acting on
    every drift generates enormous turnover and fees eat the strategy. A band
    means we hold our position until the target moves materially, cutting trades
    by an order of magnitude at negligible tracking cost.
    """
    if band <= 0:
        return target
    out = target.copy()
    held = 0.0
    for i in range(len(target)):
        t = target.iloc[i]
        if abs(t - held) >= band:
            held = t
        out.iloc[i] = held
    return out


def vol_target(
    weight: pd.Series,
    close: pd.Series,
    target_ann_vol: float = 0.40,
    lookback: int = 30,
    max_leverage: float = 1.0,
    rebalance_band: float = 0.10,
) -> pd.Series:
    """Scale the raw weight so realized volatility targets ``target_ann_vol``.

    When the asset is calm we hold more; when it's wild we hold less. Capped at
    ``max_leverage`` (1.0 = no leverage, appropriate for a spot account). This
    smooths the equity curve far more than it costs in return. ``rebalance_band``
    suppresses tiny daily re-trades (see :func:`apply_rebalance_band`).
    """
    daily_ret = close.pct_change()
    realized = daily_ret.rolling(lookback).std() * np.sqrt(PERIODS_PER_YEAR)
    scale = (target_ann_vol / realized).clip(upper=max_leverage)
    scaled = (weight * scale).clip(lower=0.0, upper=max_leverage).fillna(0.0)
    return apply_rebalance_band(scaled, rebalance_band)


def drawdown_kill_switch(
    weight: pd.Series,
    close: pd.Series,
    max_dd: float = 0.25,
    recover: float = 0.05,
) -> pd.Series:
    """Force weight to 0 after the asset falls ``max_dd`` from its peak.

    Re-enters only once price has recovered ``recover`` off its trough. This is
    a coarse circuit breaker on the *asset* (usable live without knowing your
    own equity curve). It caps tail losses at the cost of some whipsaw.
    """
    running_max = close.cummax()
    dd = close / running_max - 1.0

    out = weight.copy()
    halted = False
    trough = np.inf
    for i, ts in enumerate(close.index):
        if halted:
            trough = min(trough, close.iloc[i])
            if close.iloc[i] >= trough * (1.0 + recover):
                halted = False  # recovered enough to re-arm
            else:
                out.iloc[i] = 0.0
                continue
        if dd.iloc[i] <= -max_dd:
            halted = True
            trough = close.iloc[i]
            out.iloc[i] = 0.0
    return out
