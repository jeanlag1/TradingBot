# 2026-07-07 — Foundations: engine, robustness, a validated strategy

## Goal
Go from "I want a trading bot to make modest income" to a real, testable system
— without fooling ourselves into thinking noise is edge.

## Decisions
- **Goal framing:** steady modest income + learning, explicitly *not* swinging
  for big returns. Risk budget: up to $2,500 once something proves out.
- **Not a prediction problem.** With an ML background the temptation is to train
  a model to predict price. That's where quant-curious engineers donate money
  (non-stationary data, near-zero signal-to-noise, overfitting). Keep the alpha
  simple and economically motivated; spend the engineering on execution and risk.
- **Venue: spot-only on Coinbase.** Long/flat, no leverage, no liquidation —
  matches the low risk appetite. As a US resident, Binance derivatives aren't
  accessible anyway; US-regulated crypto perps now exist via Coinbase/Kraken and
  are a deliberate *v2* path if we ever want shorting.
- **High Coinbase fees (~0.6%/side) drive the design:** trade infrequently
  (daily bars), which also means less noise and no racing HFT firms.
- **Engine-first, venue-agnostic:** the same signal code must drive backtest,
  paper, and live — so we never test one thing and run another.

## Built
Data ingestion (Coinbase public candles) · vectorized, cost-aware, no-lookahead
backtester · strategies (SMA crossover, time-series momentum, ensemble) ·
metrics (CAGR/Sharpe/Sortino/maxDD/Calmar) · risk module (vol targeting +
drawdown kill-switch) · robustness harness (parameter sweep, walk-forward) ·
liquidity-based universe selector.

## Findings
- First BTC result looked great (90-day momentum: +128% vs +104% hold, drawdown
  −27% vs −53%). **It was partly overfit.** The parameter sweep showed no
  plateau (best lookback differed per asset), and walk-forward collapsed
  out-of-sample (in-sample Sharpes 0.9–1.8 → OOS −1.0 to +0.7).
- **The robust finding:** across all five assets, in- and out-of-sample,
  momentum roughly **halves the max drawdown** vs. buy-and-hold. So it's a
  *risk-reducer*, not a reliable alpha engine.
- The **ensemble + basket** (average momentum over 30/60/90/120d, equal-weight
  BTC/ETH/SOL) survived the same walk-forward: full-period Sharpe 0.80 vs 0.75,
  drawdown −37% vs −64%; with vol-targeting, drawdown −24% and Sharpe 0.87. No
  parameter tuned on the data.
- Universe selector: only **BTC/ETH/SOL** clear a $10M/day liquidity filter on
  Coinbase USD — the realistic universe is three names, not five.

## Caveats
- Three years, one mostly-bullish regime. Not proof, just non-disproof.
- Long/flat **cannot profit in a downturn** — it goes to cash and bleeds less.
  Profiting from bear markets would require shorting (a v2 decision).

## Next
Build the paper-trading loop on the ensemble-basket and validate it reproduces
the backtest — the discipline gate before any real money.
