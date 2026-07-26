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

Current completed stage:
Stage 2 Failure-Mechanism Diagnosis

Stage 2 final decision:
**FAIL**

Confirmed:

- Day 11B v2 provenance-complete locked replay;
- no-GT causal diagnostics;
- reproducible four-figure mechanism pipeline;
- nonnegative run-length axis and 14-source input-lock contracts;
- preregistered SHA-256 seed generation with disjoint calibration/evaluation roles.
- controlled degeneracy detection;
- controlled weak-direction identification;
- coherent-slip stress can increase harmful weak-direction updates.

The Day 14 review found corrected Geometry and Observation AUROCs of 0.5993 and
0.6862, both below the preregistered 0.80 threshold. The controlled harmful
mechanism is supported, but stable no-GT online coherent-bias detection is not.
Stage 2 is complete with a formal NO-GO and the project transition is `PIVOT`.

## Read-only FAST-LIO2 evidence closure

The strict OFF/ON cross-process replay equivalence was not established.
The observed divergence also occurs between nominally identical OFF/OFF and
ON/ON runs and is associated with FAST-LIO2/map-query nondeterminism.

The accepted read-only safety evidence is:

1. same-call input immutability;
2. frozen-observation determinism;
3. no detector feedback into FAST-LIO2.

The Day 5--Day 9 investigation is closed at this boundary. It does not prove
real-data detector effectiveness, real-data ODI superiority, stable online
harmful-bias detection, a beneficial weak-direction update, or a complete
Degen-LIO estimator. `STAGE2_GATE=FAIL` and `TRANSITION=PIVOT` remain fixed.

## Current active stage

Measurement Real Validation Pilot

Goal:

- run the frozen detector on one real FAST-LIO2 sequence;
- evaluate real ODI, AIS, weak direction and direction reliability;
- compare with conventional spectral indicators.

Explicitly stopped:

- weak-direction state update;
- harmful-bias online prediction;
- ikd-tree nondeterminism investigation;
- complete robust Degen-LIO.

MUN-FRL Lighthouse pilot outcome:

- Engineering Gate: **PASS**;
- Runtime target Gate: **PASS**;
- Scientific Pilot Gate: **FAIL**;
- `MEASUREMENT_REAL_PILOT_PASS=false`;
- `SECOND_DATASET_EXPANSION_AUTHORIZED=false`;
- `ODI_ADVANTAGE_ESTABLISHED=false`.

The frozen structural candidate did not pass the weak-direction, ODI
effectiveness, or control false-trigger conditions. This negative result does
not change `STAGE2_GATE=FAIL` or `TRANSITION=PIVOT`, and no second-dataset
expansion is authorized. Compact evidence is under
`artifacts/current/measurement_real_validation_pilot/`.

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

- stable no-GT online detection of coherent bias;
- reliable innovation gate;
- bias-state estimator;
- robust complete Degen-LIO.

Authorized pivot:

- Patent 1;
- degeneracy-detection and weak-direction paper;
- private detector-only real-LIO adapter;
- public-dataset external validation of H1.

Stopped:

- Stage 3 innovation-gating route;
- Stage 4 bias-state route;
- Patent 2;
- complete robust Degen-LIO T-RO route.

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
- FAST-LIO2 estimator modification or feedback integration (the read-only
  observation tap is implemented);
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
# Day 13 matched-analysis correction V2

The frozen Day 13 V1 trials are reanalysed without rerunning the estimator by
`scripts/39_run_stage2_failure_day13_correction.py`. The correction uses one-to-one
same-scene, same-seed, same-frame clean matches for AUROC negatives and reports
weak-clean and Open Control FPR separately. See
`docs/stage2_day13_analysis_correction_v2.md` for the protocol and scientific
limitations.
