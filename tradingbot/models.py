"""The model roster — a pre-registered zoo of strategies run in parallel.

Each ``ModelSpec`` bundles a signal with its risk configuration (long/flat vs.
long/short, leverage, vol target, asset set) *and a written rationale recorded
up front*. Pre-registration is a discipline, not decoration: with ten candidates
running at once, one will look good by luck, so we commit to *why* we expect each
to work before seeing results, judge on risk-adjusted metrics, and never crown a
winner on raw return or a short track record.

``weight_series`` is the single place a spec turns into per-bar target weights,
shared by both the backtester and the live paper loop — so the zoo can never
test one thing and trade another.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Tuple

import numpy as np
import pandas as pd

from . import risk
from .strategies import (
    buy_and_hold,
    ensemble_momentum,
    ensemble_of,
    signed_ensemble,
    ts_momentum,
)

PERIODS_PER_YEAR = 365
ALL = ("BTC-USD", "ETH-USD", "SOL-USD")


@dataclass(frozen=True)
class ModelSpec:
    name: str
    signal: Callable[[pd.DataFrame], pd.Series]
    rationale: str
    allow_short: bool = False
    max_leverage: float = 1.0          # cap on gross exposure per asset leg
    vol_target: float | None = None    # annualized; None = raw signal * leverage
    assets: Tuple[str, ...] = ALL
    rebalance_band: float = 0.05
    short_funding_daily: float = 0.0003  # ~11%/yr carry charged on short exposure

    @property
    def family(self) -> str:
        if self.allow_short:
            return "long/short"
        if len(self.assets) == 1:
            return "concentrated"
        if self.signal is buy_and_hold:
            return "benchmark"
        return "long/flat"


def weight_series(spec: ModelSpec, df: pd.DataFrame) -> pd.Series:
    """Raw per-asset target weight over the whole df (no rebalance band; each
    consumer applies the band its own way). Long/flat clips at 0; long/short
    keeps the sign. Vol targeting, when set, scales toward the target vol."""
    w = spec.signal(df)
    if not spec.allow_short:
        w = w.clip(lower=0.0)
    w = w.clip(-1.0, 1.0)

    if spec.vol_target is not None:
        daily = df["close"].pct_change()
        realized = daily.rolling(30).std() * np.sqrt(PERIODS_PER_YEAR)
        scale = (spec.vol_target / realized).clip(upper=spec.max_leverage)
        w = w * scale
    else:
        w = w * spec.max_leverage

    return w.clip(-spec.max_leverage, spec.max_leverage).fillna(0.0)


# --- The pre-registered roster ------------------------------------------------
ROSTER = [
    ModelSpec("hold_basket", buy_and_hold,
              "Benchmark: equal-weight BTC/ETH/SOL, always fully invested. Every "
              "model must beat this on risk-adjusted terms to justify its existence."),
    ModelSpec("ensemble_flat", ensemble_momentum,
              "CHAMPION (current live book, running since 2026-07-17). Ensemble "
              "momentum over 30/60/90/120d, long/flat, no vol overlay. The "
              "validated baseline every challenger must beat."),
    ModelSpec("binary_basket", ts_momentum,
              "Aggression via on/off: single 90d momentum, fully in or fully out "
              "per asset. Sharper entries/exits than the graded ensemble."),
    ModelSpec("fast_ensemble", ensemble_of((10, 20, 40)),
              "Aggression via speed: short lookbacks catch moves sooner, at the "
              "cost of more trades and more whipsaw.",
              vol_target=0.30),
    ModelSpec("vol_aggressive", ensemble_momentum,
              "Aggression via exposure: same ensemble signal, vol target raised to "
              "60% so positions run fuller/longer.",
              vol_target=0.60),
    ModelSpec("ls_ensemble", signed_ensemble,
              "SHORTING test: long/short ensemble, vol-targeted 30%. Should profit "
              "in the downtrends the long/flat book can only sidestep. Simulated "
              "short funding ~11%/yr.",
              allow_short=True, vol_target=0.30),
    ModelSpec("ls_aggressive", signed_ensemble,
              "Aggressive shorting: long/short at 1.5x leverage, vol target 45%. "
              "Bigger both ways — the high-variance challenger.",
              allow_short=True, max_leverage=1.5, vol_target=0.45),
    ModelSpec("sol_momentum", ts_momentum,
              "Aggression via concentration: 90d momentum on SOL only, the highest "
              "vol/return name. Concentrated bet on the hot asset.",
              assets=("SOL-USD",)),
    ModelSpec("btc_ensemble", ensemble_momentum,
              "Conservative concentration: ensemble momentum on BTC only, the "
              "calmest major. Low-variance single-asset trend.",
              assets=("BTC-USD",), vol_target=0.30),
    ModelSpec("slow_ensemble", ensemble_of((60, 120, 200)),
              "Steadier: slow lookbacks trade rarely and ride only durable trends. "
              "Fewer fees, less noise, later exits.",
              vol_target=0.30),
]

BY_NAME = {m.name: m for m in ROSTER}
CHAMPION = "ensemble_flat"
