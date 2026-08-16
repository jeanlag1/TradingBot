# Graduation criteria — the bar to reach real money

**Pre-registered 2026-08-16, before any challenger was eligible.** Written while
we are neutral, precisely so we can't reverse-engineer the bar to fit whatever
happens to be winning later. This is the anti-data-dredging commitment.

A model may **only** be considered for real capital if it clears **every** gate
below. The current champion (`ensemble_flat`) is the incumbent and is only
dethroned by a challenger that clears all five — a tie or a marginal edge keeps
the incumbent. That asymmetry is deliberate: it stops us chasing noise.

## The five gates

1. **Track record — ≥ 90 live paper days.** One lucky month is noise; three
   months is the minimum to distinguish signal from luck at daily frequency.

2. **Risk-adjusted edge — Sharpe ≥ champion's Sharpe + 0.20.** We rank on
   Sharpe, never raw return. A challenger must be meaningfully better on a
   risk-adjusted basis, not just higher-returning because it took more risk.

3. **No worse drawdown — max drawdown ≥ champion's max drawdown.** We never
   accept more pain for the same or less reward. (Less-negative or equal.)

4. **Regime coverage — survived ≥ 1 trending month AND ≥ 1 choppy/down month.**
   Manual review gate. Proof it works across conditions, not just the one it got
   lucky in. A model that only ever saw a bull run has not been tested.

5. **Fresh walk-forward at graduation.** Manual review gate. Re-run the
   out-of-sample walk-forward on all data available at graduation time; the edge
   must still hold. Guards against slow, creeping overfit.

## What graduation is NOT

Clearing the bar makes a model **eligible for a real-money decision** — it is not
an automatic switch to live trading. Real execution (Coinbase order placement,
and for short models the perps API + margin/liquidation controls) is a separate,
explicitly-authorized build. The standing rule holds: **no real money until a
model clears all five gates and live execution is deliberately turned on.**

## Status

Gates 1–3 are checked automatically on each model's dashboard page. Gates 4–5 are
manual reviews performed only once a model has cleared 1–3. As of writing, every
model is at ~31 days — nothing is close to eligible yet, by design.
