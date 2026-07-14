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
- selective weak-direction update benefit (under evaluation);
- complete LiDAR-inertial odometry method.

Current active stage: **Weak-Subspace Update Stage 2B**.

Confirmed: the detector and weak direction. Under evaluation: a covariance-aware selective weak-direction update. Risk prediction remains paused. FAST-LIO2 integration, real IMU propagation, real data association, and a complete Degen-LIO system are not implemented.

## Reproduce the active Stage 2B study

The supported environment is Python 3.11. Install the frozen dependencies with:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock-py311.txt
python -m pytest -q
```

The container definition runs the same test suite:

```bash
docker build -t degen-lio-stage2b .
```

Run the staged workflow in this order:

```bash
python3 scripts/check_env.py
python3 scripts/clean_workspace.py
python3 scripts/clean_workspace.py --apply
python3 scripts/31_run_weak_update_stage2b.py --quick --run-id weak_update_stage2b_quick_v1
python3 scripts/31_run_weak_update_stage2b.py --development --run-id weak_update_stage2b_dev_v1 --workers 8 --resume
python3 scripts/31_run_weak_update_stage2b.py --lock-update --development-run-dir results/weak_update_stage2b/development/weak_update_stage2b_dev_v1
python3 scripts/31_run_weak_update_stage2b.py --test --run-id weak_update_stage2b_test_v1 --update-lock artifacts/current/weak_update_stage2b/locked/update_lock.json --workers 8 --resume
python3 scripts/31_run_weak_update_stage2b.py --analyze-only --run-dir results/weak_update_stage2b/test/weak_update_stage2b_test_v1
```

The lock command writes an ignored run-local copy and a compact copy under `artifacts/current/weak_update_stage2b/locked/`; commit that compact lock before Test. Test refuses to run unless the lock is committed, source/configuration/stress hashes match, the worktree is clean, reserved seeds are disjoint and unchanged, and current-commit full-pytest provenance is present. Generated data and results remain ignored.

Detailed definitions, gates, and output contracts are in [docs/weak_update_stage2b.md](docs/weak_update_stage2b.md). Stage 2A remains frozen and documented in [docs/detector_stage2a.md](docs/detector_stage2a.md).

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
