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
  strategies.py   # signal functions: SMA crossover, ts + ensemble momentum
  backtest.py     # vectorized backtester (single + portfolio) with costs
  metrics.py      # CAGR, Sharpe, Sortino, max drawdown, exposure, turnover
  risk.py         # vol targeting + drawdown kill-switch + rebalance band
  research.py     # parameter sweeps + walk-forward out-of-sample tests
  universe.py     # liquidity-ranked, point-in-time asset selection
  paper.py        # persistent paper-trading book (cash + per-asset units)
scripts/
  fetch_data.py   # cache historical candles to data/
  run_backtest.py # run a strategy and print a performance report
  robustness.py   # sweep + walk-forward + live-universe report
  basket.py       # ensemble-basket backtest, split full / in-sample / OOS
  paper_trade.py  # --init / --step / --status / --backfill / --reset
  dashboard.py    # generate public/index.html (self-contained, theme-aware)
docs/journal/     # milestone log — the why behind each decision
.github/workflows/paper-trade.yml   # daily cloud step + dashboard refresh
```

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Pull ~3 years of daily candles into data/
python scripts/fetch_data.py --products BTC-USD ETH-USD SOL-USD --days 1100

# Backtest, then stress-test for robustness
python scripts/run_backtest.py --product BTC-USD --strategy ensemble_momentum
python scripts/basket.py        # ensemble basket, in-sample vs out-of-sample

# Paper trading (the cloud owns the live book — see below)
python scripts/paper_trade.py --backfill 250 --compare   # parity vs backtest
python scripts/dashboard.py                              # regenerate dashboard
```

## Automation & hosting

- A **GitHub Actions** workflow steps the paper book daily at 00:15 UTC,
  regenerates the dashboard, and commits state back. **The cloud is the source
  of truth for `data/paper_state.json`** — locally, `git pull` to view; do *not*
  run `--step` locally or the book diverges.
- The dashboard is hosted on **Vercel**, serving only `public/` (repo source
  stays private), and auto-redeploys on every push — so it's always current.

## Status

- [x] Data ingestion, backtester, strategies, metrics, risk module
- [x] Robustness harness (sweep + walk-forward) and universe selector
- [x] Ensemble-momentum basket — validated non-overfit out-of-sample
- [x] Paper-trading loop — reproduces the backtest within 1%
- [x] Cloud automation (GitHub Actions) + hosted dashboard (Vercel)
- [ ] Multi-week paper validation *(in progress)*
- [ ] Optional v2: shorting via Coinbase perps (bear-market regimes)
- [ ] Live execution (Coinbase Advanced Trade API)

See [`docs/journal/`](docs/journal/) for the milestone-by-milestone story.

**No real money until paper-trading tracks the backtest for several weeks.**
