# 2026-07-17 — Paper trading, dashboard, cloud automation

## Goal
Turn the validated backtest into something running in the real world, on
autopilot, that we can watch — the multi-week paper-validation phase.

## Decisions
- **Path A (validate) over path B (add shorting).** Prove we can execute the
  honest strategy we have before expanding scope. Shorting stays a deliberate
  later upgrade.
- **Cloud automation via GitHub Actions**, not a Claude cloud routine or local
  cron. For a deterministic daily script it's the right tool: free, native repo
  access, commits state back, and doesn't depend on the laptop being awake.
- **The cloud is now the source of truth** for `data/paper_state.json`. Locally,
  `git pull` to view; don't run `--step` locally or the book diverges.
- **Private repo, but the hosted dashboard serves only `public/`** — source
  stays private while just the dashboard is web-visible (default `.vercel.app`
  domains are public).

## Built
- `tradingbot/paper.py` + `scripts/paper_trade.py` — persistent paper book
  (cash + per-asset units in JSON), idempotent daily `--step`, rebalance band to
  control turnover, and a `--backfill … --compare` parity check.
- `scripts/dashboard.py` — self-contained, theme-aware HTML dashboard (inline
  SVG, hover crosshair) using the validated dataviz palette. Output → `public/`.
- `.github/workflows/paper-trade.yml` — daily at 00:15 UTC: step, refresh
  dashboard, commit state back. Verified green end-to-end.
- Private GitHub repo `jeanlag1/TradingBot`; Vercel hosting of the dashboard.

## Findings
- **Parity confirmed:** the live loop reproduces the vectorized backtest to
  within **0.97%** over a 250-bar replay. The execution logic is correct.
- Seeded a $2,500 paper book. On day one the strategy is **~83% in cash** (BTC
  momentum negative, ETH/SOL weak) — the risk control behaving exactly as
  designed in a soft tape.
- The idempotency guard held in CI: a same-day re-run stepped nothing.

## Caveats
- One day of live history. The whole point is to let weeks accumulate and then
  compare realized vs. backtested behavior.
- The hosted dashboard is public (data only, no secrets) — fine, but worth
  remembering it's world-readable.

## Next
Let the validation window run on autopilot for several weeks. Open decision:
start **path B (shorting via Coinbase perps)** while we wait, or hold until the
paper track record is in.
