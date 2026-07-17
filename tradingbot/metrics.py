"""Performance metrics for a strategy's net daily returns / equity curve."""

from __future__ import annotations

import numpy as np
import pandas as pd

# Crypto trades every calendar day, so we annualize with 365, not 252.
PERIODS_PER_YEAR = 365


def max_drawdown(equity: pd.Series) -> float:
    """Largest peak-to-trough decline of an equity curve (negative number)."""
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min())


def summary(net_returns: pd.Series, position: pd.Series) -> dict:
    """Compute a standard performance report from net daily returns."""
    net_returns = net_returns.dropna()
    equity = (1.0 + net_returns).cumprod()
    n = len(net_returns)
    if n == 0:
        return {}

    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (PERIODS_PER_YEAR / n) - 1.0)
    vol = float(net_returns.std() * np.sqrt(PERIODS_PER_YEAR))
    sharpe = float(net_returns.mean() / net_returns.std() * np.sqrt(PERIODS_PER_YEAR)) if net_returns.std() else 0.0

    downside = net_returns[net_returns < 0].std()
    sortino = float(net_returns.mean() / downside * np.sqrt(PERIODS_PER_YEAR)) if downside else 0.0

    mdd = max_drawdown(equity)
    exposure = float((position.reindex(net_returns.index).fillna(0) > 0).mean())
    # A "trade" is any bar where the target position changed.
    trades = int((position.diff().abs() > 1e-9).sum())

    return {
        "days": n,
        "total_return": total_return,
        "cagr": cagr,
        "ann_vol": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": mdd,
        "calmar": float(cagr / abs(mdd)) if mdd else 0.0,
        "exposure": exposure,
        "trades": trades,
        "final_equity": float(equity.iloc[-1]),
    }


def format_report(name: str, stats: dict) -> str:
    if not stats:
        return f"{name}: no data"
    return (
        f"\n=== {name} ===\n"
        f"  Period:         {stats['days']} days\n"
        f"  Total return:   {stats['total_return']:+.1%}\n"
        f"  CAGR:           {stats['cagr']:+.1%}\n"
        f"  Ann. vol:       {stats['ann_vol']:.1%}\n"
        f"  Sharpe:         {stats['sharpe']:.2f}\n"
        f"  Sortino:        {stats['sortino']:.2f}\n"
        f"  Max drawdown:   {stats['max_drawdown']:.1%}\n"
        f"  Calmar:         {stats['calmar']:.2f}\n"
        f"  Exposure:       {stats['exposure']:.0%} of days in market\n"
        f"  Trades:         {stats['trades']}\n"
        f"  Final equity:   {stats['final_equity']:.3f}x\n"
    )
