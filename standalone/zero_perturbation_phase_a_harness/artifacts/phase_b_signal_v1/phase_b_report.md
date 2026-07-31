# Zero-Perturbation Phase B — Cross-Backend Scene-Effect Survival Test

This compact artifact reports the frozen 42-snapshot, 84-trial Phase B run.
No confidence interval is reported for the three-seed scene cells.

## Decision

- `PHASE_B_SIGNAL_PASS = true`
- `FULL_SYNTHETIC_DEVELOPMENT_PROTOCOL_DESIGN_AUTHORIZED = true`
- `FULL_SYNTHETIC_DEVELOPMENT_RUN_AUTHORIZED = false`
- `CONFIRMATORY_AUTHORIZED = false`
- `REAL_DATA_AUTHORIZED = false`
- `MEASUREMENT_PAPER_MAINLINE_AUTHORIZED = false`

## Frozen signal checks

- Independent-noise-free Spearman rho: `0.9285714285714288`
- Full-noise Spearman rho: `1.0`
- Independent-noise-free common weak scene: `LONG_CORRIDOR`
- Full-noise common weak scene: `LONG_CORRIDOR`
- Main/independent difference count: `0`

All scene medians, three geometry-seed values, average-tie ranks, effect ratios,
absolute differences, failure records, input pairing, and runtimes are in `tables/`.
