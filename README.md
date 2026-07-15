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

Current active task: **Stage 2 Failure-Mechanism Diagnosis — Day 9**.

Confirmed:

- controlled degeneracy detection;
- controlled weak-direction identification.

Negative results:

- Stage 2B column-scaling selective update;
- Stage 2C projected-gain update.

Under diagnosis:

- weak-direction coherent innovation and update-error causality.

Not implemented:

- innovation monitor;
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
