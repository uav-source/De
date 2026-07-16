# Degen-LIO

Degen-LIO is currently a degeneration-detector plus weak-direction research prototype.

Confirmed:

- finite-patch synthetic scenes;
- geometry/observation degradation separation;
- translation-marginal information spectrum;
- ODI-based degradation detection;
- primary weak-direction extraction.

Not confirmed:

- reliable drift magnitude prediction;
- online risk warning;
- projected-gain weak-direction update benefit under the Stage 2C benchmark;
- complete LiDAR-inertial odometry method.

Current active task:
Stage 2 Day 13 — Preregistered New-Seed Diagnostic AUROC/FPR Evaluation

Confirmed:

- Day 11B v2 provenance-complete locked replay;
- no-GT causal diagnostics;
- reproducible four-figure mechanism pipeline;
- nonnegative run-length axis and 14-source input-lock contracts;
- preregistered SHA-256 seed generation with disjoint calibration/evaluation roles.

Current Day 13 output is restricted to preliminary held-out diagnostic AUROC,
clean-FPR, geometry-block stability, offline causal association, and gross
Huber-control summaries. Its calibration-only operating point cannot be retuned
from evaluation results and is not a Stage 3 threshold. Stage 2 remains
incomplete until the separate Day 14 review.

Day 11A selects no historical "representative seed." It locks one Geometry and
one Observation diagnostic case from the frozen Test seed namespace using a
result-independent SHA-256 rule. It runs no estimator or replay. The frozen
Stage 2C stress name is `coherent_subhuber_slip`; the earlier Stage 2B name
`axial_correspondence_slip` is not aliased into Stage 2C.

Day 11B replays exactly the locked Geometry and Observation cases across
`clean`/`coherent_subhuber_slip` and the two formal methods. This is a
mechanism-only diagnostic replay, not an independent Test or representative
sample, and it cannot select a threshold or decide the Stage 2 gate.

Not established:

- coherent-bias separability;
- AUROC/FPR;
- cross-seed stability;
- online threshold;
- Stage 2 Gate.

Earlier confirmed:

- controlled degeneracy detection;
- controlled weak-direction identification;
- causal frame and window diagnostics.

Negative results:

- Stage 2B column-scaling selective update;
- Stage 2C projected-gain update.

Not implemented:

- Stage 3 innovation gate;
- bias-state estimator;
- FAST-LIO2 integration;
- real IMU propagation;
- real data association;
- complete Degen-LIO.

Frozen Stage 2B outcome: **the column-scaled update is a mathematical and empirical NO-GO.** Its compact evidence is archived under `artifacts/history/stage2b_column_scaling_no_go/`.

Locked Stage 2C outcome: **the projected-gain formulation is mathematically correct but fails the reserved Test performance gate.** Geometry and Observation axis-RMSE reductions were positive but only 0.3720% and 0.4926%, far below the locked 15% threshold. Engineering, formulation, stress, clean, and Open-Control gates passed; both coherent-stress performance gates failed. FAST-LIO2 integration and risk warning remain unauthorized. The compact audit is in `artifacts/current/weak_update_stage2c/`.

## Reproduce the active Stage 2C study

The supported environment is Python 3.11. Install the frozen dependencies with:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock-py311.txt
python -m pytest -q
```

The container definition runs the same test suite:

```bash
docker build -t degen-lio-stage2c .
```

Run the staged workflow in this order:

```bash
python3 scripts/check_env.py
python3 scripts/clean_workspace.py
python3 scripts/clean_workspace.py --apply
python3 scripts/32_run_weak_update_stage2c.py --quick --run-id weak_update_stage2c_quick_v1
python3 scripts/32_run_weak_update_stage2c.py --development --run-id weak_update_stage2c_dev_v1 --workers 8 --resume
python3 scripts/32_run_weak_update_stage2c.py --lock-update --development-run-dir results/weak_update_stage2c/development/weak_update_stage2c_dev_v1
python3 scripts/32_run_weak_update_stage2c.py --test --run-id weak_update_stage2c_test_v1 --update-lock artifacts/current/weak_update_stage2c/locked/update_lock.json --workers 8 --resume
python3 scripts/32_run_weak_update_stage2c.py --analyze-only --run-dir results/weak_update_stage2c/test/weak_update_stage2c_test_v1
```

The lock command is allowed only after Development passes. It writes an ignored run-local copy and a compact copy under `artifacts/current/weak_update_stage2c/locked/`; commit that compact lock before Test. Test refuses to run unless the lock is committed, source/configuration/stress and historical-artifact hashes match, the worktree is clean, reserved seeds are disjoint and unchanged, and current-commit full-pytest provenance is present. Generated data and results remain ignored.

Detailed definitions, gates, and output contracts are in [docs/weak_update_stage2c.md](docs/weak_update_stage2c.md). Stage 2A remains frozen and documented in [docs/detector_stage2a.md](docs/detector_stage2a.md).

## Repository scope

- `src/degen_detector/`: information spectrum, ODI, trigger state, and direction semantics.
- `src/minibench/`: deterministic finite-patch scenes and observation generation.
- `src/eval/`: common I/O, hierarchical statistics, locks, provenance, and Stage 2A evaluation.
- `configs/`: frozen detector, scene, development, and reserved-test definitions.
- `scripts/clean_workspace.py`: allowlist-only cleanup; dry-run by default.
- `artifacts/history/`: compact, immutable historical evidence.
- `artifacts/current/`: current small audit summaries only.

## Historical evidence

The prior confirmatory no-go evidence is preserved at [artifacts/history/stage1c_confirmatory_no_go](artifacts/history/stage1c_confirmatory_no_go). Its risk-prediction route remains paused, while detector confirmation is pursued separately.

The full historical tree remains recoverable from the local annotated tag:

```bash
git show archive/stage1c-confirmatory-no-go:<path>
```

The compact research timeline is in [docs/history/metric_redesign_timeline.md](docs/history/metric_redesign_timeline.md).
