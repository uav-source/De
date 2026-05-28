# Day 09 Report - Weak Direction Extraction and Alignment

## Completed Items

- Implemented `src/degen_detector/weak_direction.py`.
  - `extract_weak_subspace(eigvals, eigvecs, tau_w)`
  - `get_primary_weak_direction(eigvals, eigvecs)`
  - `translation_component(v)`
  - `compute_axis_alignment(weak_dir_translation, axis)`
  - `compute_drift_alignment(weak_dir_translation, drift_vector)`
  - `is_direction_reliable(eigvals, eigvecs, min_gap_ratio, min_translation_norm)`
- Extended `src/degen_detector/odi_tracker.py` so each ODI row exports:
  - `weak_dir_0 ... weak_dir_5`
  - `weak_trans_x`, `weak_trans_y`, `weak_trans_z`
  - `axis_alignment`
  - `weak_reliable`
  - `num_weak_dims`
  - `lambda_min_clamped`
- Extended `scripts/02_compute_odi.py`.
  - Per-frame ODI CSVs now include weak-direction fields.
  - `results/day14/tables/day06_odi_summary.csv` includes `median_lambda_min_clamped`.
  - `results/day14/tables/day09_alignment_summary.csv` is generated in `--all` mode.
- Extended `scripts/03_eval_metrics.py` with window-level `weak_drift_alignment` as a post-hoc comparison between H-derived weak direction and saved TUM drift vector.
- Added Day 9 tests in `tests/test_weak_direction.py`.

## Reproducibility Record

- Date: 2026-05-28
- Repository: `/home/lj/Degen-LIO`
- Base git commit at run start: `cf58351`
- Detector config: `configs/detector/odi_default.yaml`
- Random seed: `42`
- Weak reliability thresholds:
  - `weak_min_gap_ratio=1.0e-3`
  - `weak_min_translation_norm=0.25`
- Weak subspace threshold: `tau_w=0.02`

## Run Commands

```bash
python3 scripts/check_env.py
python3 -m pytest -q
python3 scripts/00_generate_minibench.py --all
python3 scripts/01_simulate_observations.py --all --config configs/detector/odi_default.yaml
python3 scripts/02_compute_odi.py --all --config configs/detector/odi_default.yaml
python3 scripts/02_run_toy_lio.py --all --config configs/detector/odi_default.yaml
python3 scripts/03_eval_metrics.py --all --config configs/detector/odi_default.yaml
```

## Verification

- `python3 scripts/check_env.py`: OK
- `python3 -m pytest -q`: `62 passed in 2.06s`

## Output Files

- Framewise ODI and weak direction:
  - `results/day14/raw/OC-L0-S01-M1_odi.csv`
  - `results/day14/raw/ST-L3-S01-M1_odi.csv`
  - `results/day14/raw/CT-L2-S01-M2_odi.csv`
  - `results/day14/raw/RT-L4-S01-M1_odi.csv`
- Alignment summary:
  - `results/day14/tables/day09_alignment_summary.csv`
- Updated metric summary with weak-drift alignment and clamped lambda:
  - `results/day14/tables/day08_metric_summary.csv`

## Alignment Summary

| sequence_id | median_axis_alignment | mean_axis_alignment | reliable_frame_ratio | num_weak_dims_median | ODI_median | lambda_min_clamped_median |
|---|---:|---:|---:|---:|---:|---:|
| OC-L0-S01-M1 | NaN | NaN | 0.0 | 1.0 | 0.512430 | 1401.462676 |
| ST-L3-S01-M1 | 1.0 | 1.0 | 1.0 | 2.0 | 0.728799 | 0.0 |
| CT-L2-S01-M2 | 1.0 | 1.0 | 1.0 | 2.0 | 0.728232 | 2.273737e-13 |
| RT-L4-S01-M1 | 1.0 | 1.0 | 1.0 | 2.0 | 0.728770 | 0.0 |

## Required Answers

- ST median axis alignment >= 0.70: yes. Median reliable alignment is `1.0`.
- RT median axis alignment >= 0.70: yes. Median reliable alignment is `1.0`.
- CT weak direction uses local axis: yes. `axis_alignment` is computed from `observations.npz::axis_per_frame`, which comes from `axis.csv`. The first CT weak translation is approximately `[-0.315, 0.949, 0]`, matching the first local axis instead of fixed global x. Across CT reliable frames, `std(abs(weak_trans_x))=0.209834`, so it is not a fixed global-x direction.
- OC has no stable strong weak direction: yes. `reliable_frame_ratio=0.0`; axis alignment is reported as `NaN` instead of forced.
- Weak direction source: weak direction is extracted only from each frame's `H_tilde` eigenspectrum/eigenvectors. Day 8 axis error and drift error are not used to infer the weak direction.
- Drift direction comparison: window-level `weak_drift_alignment` is computed only after weak direction is exported, using saved TUM trajectory errors for comparison. It is not used to generate or tune weak direction.

## Drift Alignment Snapshot

From `results/day14/tables/day08_metric_summary.csv`:

| sequence_id | weak_drift_alignment_median | weak_drift_alignment_valid_ratio |
|---|---:|---:|
| OC-L0-S01-M1 | NaN | 0.0 |
| ST-L3-S01-M1 | 0.999980 | 1.0 |
| CT-L2-S01-M2 | 0.587142 | 1.0 |
| RT-L4-S01-M1 | 0.999985 | 1.0 |

## Day 14 Gate Status

Currently satisfied:

- Four sequences generate, simulate, compute ODI, run toy LIO, and evaluate.
- H_tilde validity is covered by tests and successful ODI generation.
- Straight tunnel weak alignment gate is satisfied.
- RT weak alignment also satisfies the same practical threshold.
- ODI trend remains clear: ST/CT/RT median ODI is higher than OC.
- OC has no stable false weak direction under the current reliability checks.
- `lambda_min_clamped` is available in summary tables to avoid interpreting numerical negative roundoff as negative information.

Not yet satisfied or not yet tested:

- Day 10 ODI-drift correlation is not implemented.
- ODI versus `condition_number` or `lambda_min` ranking is not implemented.
- Sensitivity to whitening and `tau_w` is not implemented.
- Day 14 figures, gate table, final manifest, and Go/Conditional Go/No-Go report are not implemented.

## Failed Items

- None.

## Day 10 Most Important Task

- Implement per-sequence correlation between ODI and axis/weak drift rates.
- Keep the Day 8 and Day 9 bias controls active: do not merge-only correlation, do not tune `toy_lio`, and do not use drift error to define weak direction.
