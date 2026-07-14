# Degen-LIO

Degen-LIO is currently a degeneration-detector research prototype.

Confirmed:

- finite-patch synthetic scenes;
- geometry/observation degradation separation;
- translation-marginal information spectrum;
- ODI-based degradation detection;
- primary weak-direction extraction.

Not confirmed:

- reliable drift magnitude prediction;
- online risk warning;
- weak-subspace update benefit;
- complete LiDAR-inertial odometry method.

Current active stage: **Detector Consolidation Stage 2A**.

Stage 2A asks only whether ODI tracks controlled degradation severity and whether the minimum-eigenvalue direction consistently identifies the known weak direction. It does not run process trials or toy-LIO risk experiments, implement a weak-subspace update, integrate FAST-LIO2, or claim a complete odometry system.

## Reproduce the active detector study

The supported environment is Python 3.11. Install the frozen dependencies with:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock-py311.txt
python -m pytest -q
```

The container definition runs the same test suite:

```bash
docker build -t degen-lio-stage2a .
```

Run the staged workflow in this order:

```bash
python3 scripts/check_env.py
python3 scripts/clean_workspace.py
python3 scripts/clean_workspace.py --apply
python3 scripts/30_run_detector_stage2a.py --quick --run-id detector_stage2a_quick_v1
python3 scripts/30_run_detector_stage2a.py --development --run-id detector_stage2a_dev_v1 --workers 8 --resume
python3 scripts/30_run_detector_stage2a.py --lock-detector --development-run-dir results/detector_stage2a/development/detector_stage2a_dev_v1
python3 scripts/30_run_detector_stage2a.py --test --run-id detector_stage2a_test_v1 --detector-lock results/detector_stage2a/development/detector_stage2a_dev_v1/detector_lock.json --workers 8 --resume
```

The test phase refuses to run unless the detector lock is tracked, source and configuration hashes match, the worktree is clean, reserved test seeds match, and current-commit full-pytest provenance is present. Generated data and results stay ignored; only compact audit summaries are exported under `artifacts/current/`.

Detailed definitions, gates, and output contracts are in [docs/detector_stage2a.md](docs/detector_stage2a.md).

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
