# 2026-08-16 — Strategy zoo: 10 models in parallel

## Goal
Get more feedback, faster, without more risk — by running many strategies on
parallel paper books instead of waiting on one.

## Decisions
- **A champion/challenger zoo of 10 pre-registered models** across every
  aggression axis: on/off, speed, exposure, shorting, concentration.
- **Simulated shorting needs no perps API.** A short is trivial to simulate
  (negative units, inverse P&L, a daily funding carry). So the long/short models
  run *now*, on paper — we only build real perps execution if the data earns it.
- **Guard the multiple-comparisons trap.** With 10 candidates one will look good
  by luck, so: pre-register each with a written rationale, rank by Sharpe (not
  raw return), require a minimum track record, and keep the champion untouched.
- **One shared weight function** (`models.weight_series`) drives both backtest
  and every paper book — the zoo can't test one thing and trade another.

## Built
- `tradingbot/models.py` — `ModelSpec` + `weight_series` + the 10-model `ROSTER`.
- `tradingbot/backtest.py::run_spec` — spec-driven backtest with short, leverage,
  vol targeting, and short funding.
- `tradingbot/paper.py` — rewritten as a multi-book runner (`step_all`,
  `backfill_all`); one JSON book per model under `data/paper/`.
- `scripts/paper_trade.py` — leaderboard + parity `--compare`; new-book backfill.
- `scripts/dashboard.py` — leaderboard dashboard (ranked by Sharpe, champion
  highlighted, comparison chart of benchmark vs champion vs top challengers).
- Champion's real 31-day history migrated in intact; workflow now steps all
  models and commits `data/paper/`.

## Findings
- **Parity holds for all 10 models** (worst 0.4% vs `run_spec`), shorts included.
- Backfilled over the same flat month, the **champion still leads or ties the
  challengers on Sharpe** — the aggressive and long/short variants mostly lost
  *more* in the chop. `binary_basket`/`sol_momentum` correctly sat 100% in cash
  (all three assets had negative 90d momentum). Early and low-signal, but a first
  data point that aggression didn't help *in this regime*.

## Caveats
- One flat month is not a verdict on any model. Long/short and aggressive
  strategies earn their keep in trending/bear regimes we haven't seen yet.
- Simulated shorting ignores perp funding spikes and liquidation — the ~11%/yr
  carry is a flat placeholder.

## Next
Let all 10 accumulate. Revisit when a real trend or drawdown appears — that's the
regime that will actually separate them. Still no real money.
