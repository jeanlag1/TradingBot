# 2026-08-16 — Graduation criteria + asset-selection reality check

## Goal
Give the zoo a finish line (graduation bar), and answer "can a model hunt the
most volatile / profitable assets?" honestly.

## Decisions
- **Pre-register graduation criteria now**, while neutral, so we can't move the
  goalposts to fit a winner later. Five gates; champion only dethroned by a
  challenger clearing all five. See `docs/graduation.md`.
- **"Coins that 3–5x in a day" is a trap** — and the data proves it (below). The
  disciplined version of the instinct is *cross-sectional momentum* over a
  *liquid* pool, so we built that instead as one more challenger.

## Built
- `docs/graduation.md` + `tradingbot/graduation.py`; each model page now shows a
  graduation-progress card (gates 1–3 auto, 4–5 manual).
- `cs_momentum_rotator`: from 8 liquid names (BTC/ETH/SOL/XRP/DOGE/LINK/ADA/AVAX)
  hold the top-3 by 90d momentum, rotating daily. New `cross_sectional` path in
  `models.py` / `backtest.run_spec` / `paper.py`, with rotation-aware leg reasons.

## Findings
- Pulled all **397 Coinbase USD products**. Over ~2 years, **zero** tradeable
  asset 3x'd in a single day; the wildest liquid names (~100% ann vol) topped out
  around +35–70% on their best day and had −20–28% days too. The coins that do
  5x/day are illiquid microcaps (~$1M/day) where a $2.5k order is the market and
  most go to zero (survivorship bias). Higher vol ≠ higher return — we already
  saw the high-vol models post the worst risk-adjusted results.
- Rotator over the common 800-day window: Sharpe 0.11 vs champion −0.07, **but
  max drawdown −72% vs −39%** — worse even than buy-and-hold. Concentrating into
  the hottest names amplifies reversals. Selection concentrated risk; it didn't
  remove it. Parity vs backtest: 0.0%.

## Caveats
- Local BTC/ETH/SOL cache is 800 common bars and this window is net-negative for
  crypto, so absolute returns are all negative — the *relative* comparison is the
  valid read. Live paper + a graduation walk-forward give the real verdict.

## Next
Let all 11 run. Define nothing further until a model approaches the 90-day gate.
Still no real money.
