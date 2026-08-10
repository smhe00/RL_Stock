# Research context for the local Codex reviewer

Status date: 2026-08-11

## Project boundary

RL_Stock is an independent China ETF research repository. It is not an
authorization surface for miniQMT, QMT live trading, account actions, paper
trading, or order generation. Research, simulation, read-only diagnostics, and
live execution remain separate modes.

## Accepted research path

The deterministic MaxDiv path is the accepted core. Its frozen parameters are:

```text
lookback = 120 trading days
covariance shrinkage = 0.5
```

The completed capital-efficiency study compared frozen defensive-cap variants.
M2 was pre-designated and is the accepted principal challenger for a possible
future execution-oriented PREP. This is historical concept validation only;
M2 is not executable or live-ready.

M2 canonical economics:

```text
CAGR                 0.116441
Sharpe               1.219346
MaxDD               -0.076651
defensive allocation 0.25
```

The capital-efficiency research phase is complete. No rerun, retuning, new
backtest, execution study, or new branch follows automatically.

## Closed and stopped paths

- PPO, SAC, and TD3 are closed unless the user explicitly reopens them.
- The `03110.HK` execution-realism mapping remains under a structural STOP. Its
  prior result must not be described as repaired, executable, or live-ready.
- Forward, paper, live, QMT live, instrument substitution, no-trade-band search,
  minimum-trade optimization, and execution-time optimization are not
  authorized by the current state.

## Reviewer intent

The local reviewer preserves contracts and evidence quality. It may approve the
submitted handoff, request revisions, or report a blocker. It does not invent a
next project direction, select a post-result branch, or relax an accepted
constraint without explicit user authorization.

