"""Strategy signal functions.

A strategy is a pure function ``df -> target weight`` where ``df`` is an OHLCV
DataFrame and the return value is a Series in ``[0, 1]`` (spot, long/flat):
0 = fully in cash, 1 = fully in the asset. Values are decided using data up to
and including each bar's close; the backtester handles the one-bar execution
delay, so strategies here must NOT shift for lookahead themselves.

Keeping strategies as pure functions is what lets the backtester and the live
loop share identical signal logic.
"""

from __future__ import annotations

import pandas as pd

# Registry so scripts can select a strategy by name.
REGISTRY = {}


def strategy(name):
    def _wrap(fn):
        REGISTRY[name] = fn
        return fn
    return _wrap


@strategy("buy_and_hold")
def buy_and_hold(df: pd.DataFrame) -> pd.Series:
    """Benchmark: always fully invested."""
    return pd.Series(1.0, index=df.index)


@strategy("sma_crossover")
def sma_crossover(df: pd.DataFrame, fast: int = 20, slow: int = 100) -> pd.Series:
    """Long when the fast SMA is above the slow SMA, else flat (in cash).

    A classic, low-turnover trend filter: it keeps you invested during
    sustained uptrends and moves you to cash when the trend rolls over.
    """
    fast_ma = df["close"].rolling(fast).mean()
    slow_ma = df["close"].rolling(slow).mean()
    weight = (fast_ma > slow_ma).astype(float)
    weight[slow_ma.isna()] = 0.0  # no signal until the slow MA is defined
    return weight


@strategy("ts_momentum")
def ts_momentum(df: pd.DataFrame, lookback: int = 90) -> pd.Series:
    """Time-series momentum: long if the trailing return is positive, else flat.

    The most economically robust trend signal there is — documented across
    decades and asset classes. Long-only here because we're spot.
    """
    trailing_return = df["close"].pct_change(lookback)
    weight = (trailing_return > 0).astype(float)
    weight[trailing_return.isna()] = 0.0
    return weight


@strategy("ensemble_momentum")
def ensemble_momentum(df: pd.DataFrame, lookbacks=(30, 60, 90, 120)) -> pd.Series:
    """Average the long/flat momentum signal across several lookbacks.

    Instead of betting on one "best" lookback (which the robustness tests showed
    is overfitting), we vote across horizons: the weight is the *fraction* of
    lookbacks that are positive. If 3 of 4 horizons say uptrend, we hold 0.75.
    This removes the single-parameter dependence that made single-lookback
    momentum fragile, and gives naturally graded exposure into/out of trends.
    """
    signals = []
    for lb in lookbacks:
        trailing_return = df["close"].pct_change(lb)
        sig = (trailing_return > 0).astype(float)
        sig[trailing_return.isna()] = 0.0
        signals.append(sig)
    return sum(signals) / len(signals)
