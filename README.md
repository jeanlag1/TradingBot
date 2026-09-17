# TradingBot

A spot, long/flat crypto trading engine that runs a **zoo of strategies in
parallel on simulated money** and lets them compete. Built engine-first and
venue-agnostic: the same signal code drives backtest, paper, and (eventually)
live trading, so you never test one thing and run another.

No real dollars are at risk. This is a learn-something-cool project with a hard
rule — nothing touches real money until a model earns it (see Graduation below).

## Design principles

1. **Signal code is shared.** A strategy is a pure function
   `OHLCV DataFrame -> target weight series`. The backtester and the live paper
   loop both consume that same function (`models.weight_series`). No divergence.
2. **Costs are always modeled.** Fees + slippage are applied on every change in
   position. A strategy that only looks good with zero costs is not a strategy.
3. **No lookahead.** A weight decided on the close of day *t* is only earned on
   day *t+1*'s return (`position = weight.shift(1)`).
4. **Risk is a first-class module,** not an afterthought: volatility-targeted
   sizing, a rebalance band to cut churn, and a hard max-drawdown kill-switch.
5. **Pre-register, then judge.** Every model's rationale is written *before*
   seeing results, and graduation criteria are fixed in advance — so a winner
   can't be crowned by luck or a moved finish line.

## The strategy zoo

Eleven models run against each other every night, each with its own persistent
paper book. They're deliberately varied — different lookbacks, exposure, and
risk postures — so the experiment surfaces *what actually holds up*, not what
looks good once. Ranked on risk-adjusted terms (Sharpe + drawdown), never raw
return.

| model | family | idea |
|---|---|---|
| `hold_basket` | benchmark | Equal-weight BTC/ETH/SOL, always invested. The bar to beat. |
| `ensemble_flat` | long/flat | **Champion.** Ensemble momentum (30/60/90/120d), no vol overlay. |
| `binary_basket` | long/flat | Single 90d momentum, fully in or fully out per asset. |
| `fast_ensemble` | long/flat | Short lookbacks (10/20/40d) — catch moves sooner, more whipsaw. |
| `slow_ensemble` | long/flat | Slow lookbacks (60/120/200d) — ride only durable trends. |
| `vol_aggressive` | long/flat | Same ensemble, vol target raised to 60% — runs fuller. |
| `ls_ensemble` | long/short | Shorting test, vol-targeted 30%, simulated funding carry. |
| `ls_aggressive` | long/short | Shorting at 1.5x, vol target 45% — the high-variance one. |
| `btc_ensemble` | concentrated | Ensemble on BTC only — the calmest major. |
| `sol_momentum` | concentrated | 90d momentum on SOL only — concentrated bet on the hot name. |
| `cs_momentum_rotator` | rotation | Hold the top-3 by momentum from 8 liquid names, rotating daily. |

Model specs and rationales live in [`tradingbot/models.py`](tradingbot/models.py).

## Graduation

A challenger is only allowed near real money if it clears **all five** gates,
pre-registered in [`docs/graduation.md`](docs/graduation.md):

1. ≥ 90 live paper days
2. Sharpe ≥ champion + 0.20
3. Max drawdown no worse than the champion
4. Survived ≥ 1 trending **and** ≥ 1 choppy/down month
5. A fresh walk-forward at graduation time

Gates 1–3 are auto-evaluated ([`tradingbot/graduation.py`](tradingbot/graduation.py));
4–5 are manual. The champion is only dethroned by a challenger clearing everything.

## Layout

```
tradingbot/
  data.py         # fetch + cache Coinbase daily candles (public API, no auth)
  strategies.py   # signal functions: SMA crossover, ts + ensemble momentum
  models.py       # the pre-registered roster (ModelSpec) + shared weight_series
  backtest.py     # vectorized backtester (single + portfolio + spec) with costs
  metrics.py      # CAGR, Sharpe, Sortino, max drawdown, exposure, turnover
  risk.py         # vol targeting + drawdown kill-switch + rebalance band
  graduation.py   # auto-evaluate the graduation gates
  research.py     # parameter sweeps + walk-forward out-of-sample tests
  universe.py     # liquidity-ranked, point-in-time asset selection
  paper.py        # multi-model paper books (one JSON per model, cash + units)
scripts/
  fetch_data.py   # cache historical candles to data/
  run_backtest.py # run a strategy and print a performance report
  robustness.py   # sweep + walk-forward + live-universe report
  basket.py       # ensemble-basket backtest, split full / in-sample / OOS
  paper_trade.py  # --step / --status / --backfill / --backfill-new / --compare
  dashboard.py    # generate public/ (leaderboard + per-model pages, theme-aware)
docs/graduation.md                  # the pre-registered graduation criteria
docs/journal/                       # milestone log — the why behind each decision
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

# Inspect the live zoo (the cloud owns the books — see below)
python scripts/paper_trade.py --status     # leaderboard, ranked by Sharpe
python scripts/paper_trade.py --compare    # paper-vs-backtest parity check
python scripts/dashboard.py                # regenerate the dashboard
```

## Automation & hosting

- A **GitHub Actions** workflow steps every paper book daily at 00:15 UTC,
  regenerates the dashboard, and commits state back. **The cloud is the source
  of truth for `data/paper/`** — locally, `git pull` to view; do *not* run
  `--step` locally or the books diverge.
- The dashboard is hosted on **Vercel**, serving only `public/` (nothing in the
  repo is secret, but source stays out of the hosted site), and auto-redeploys
  on every push — so it's always current.

## Status

- [x] Data ingestion, backtester, strategies, metrics, risk module
- [x] Robustness harness (sweep + walk-forward) and universe selector
- [x] Ensemble-momentum basket — validated non-overfit out-of-sample
- [x] Strategy zoo — 11 models competing on parallel paper books
- [x] Paper-trading loop — reproduces the backtest within 1%
- [x] Cloud automation (GitHub Actions) + hosted multi-page dashboard (Vercel)
- [x] Pre-registered graduation criteria + per-model gate tracking
- [ ] Multi-month paper validation toward the 90-day gate *(in progress)*
- [ ] Optional v2: shorting via Coinbase perps (bear-market regimes)
- [ ] Live execution (Coinbase Advanced Trade API)

See [`docs/journal/`](docs/journal/) for the milestone-by-milestone story.

**No real money until a model clears every graduation gate.**
