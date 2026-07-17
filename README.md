# TradingBot

A spot, long/flat crypto trading engine. Built engine-first and venue-agnostic:
the same signal code drives backtest, paper, and (eventually) live trading, so
you never test one thing and run another.

## Design principles

1. **Signal code is shared.** A strategy is a pure function
   `OHLCV DataFrame -> target weight series in [0, 1]`. The backtester and the
   live loop both consume that same function. No divergence.
2. **Costs are always modeled.** Fees + slippage are applied on every change in
   position. A strategy that only looks good with zero costs is not a strategy.
3. **No lookahead.** A weight decided on the close of day *t* is only earned on
   day *t+1*'s return (`position = weight.shift(1)`).
4. **Risk is a first-class module,** not an afterthought: volatility-targeted
   sizing and a hard max-drawdown kill-switch.

## Layout

```
tradingbot/
  data.py         # fetch + cache Coinbase daily candles (public API, no auth)
  strategies.py   # signal functions: SMA crossover, time-series momentum
  backtest.py     # vectorized backtester with fees + slippage
  metrics.py      # CAGR, Sharpe, Sortino, max drawdown, exposure, turnover
  risk.py         # vol targeting + drawdown kill-switch
scripts/
  fetch_data.py   # cache historical candles to data/
  run_backtest.py # run a strategy and print a performance report
```

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Pull ~3 years of BTC + ETH daily candles into data/
python scripts/fetch_data.py --products BTC-USD ETH-USD --days 1100

# Backtest a strategy
python scripts/run_backtest.py --product BTC-USD --strategy sma_crossover
python scripts/run_backtest.py --product BTC-USD --strategy ts_momentum
```

## Status

- [x] Data ingestion (Coinbase public candles)
- [x] Vectorized backtester with costs
- [x] Baseline strategies (SMA crossover, time-series momentum)
- [x] Performance metrics
- [x] Risk module (vol targeting, drawdown kill-switch)
- [ ] Paper-trading loop
- [ ] Live execution (Coinbase Advanced Trade API)

**No real money until paper-trading tracks the backtest for several weeks.**
