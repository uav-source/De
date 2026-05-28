# Day 08 Report - Eval Metrics From Saved Trajectories

## Completed Items

- Implemented `src/eval/metrics.py`.
  - `load_tum_pose(path)`
  - `load_axis_csv(path)`
  - `align_se3_if_needed(est, gt)`
  - `compute_ATE(est, gt)`
  - `compute_RPE(est, gt, window)`
  - `compute_axis_error(est, gt, axis_per_frame)`
  - `compute_cross_error(est, gt, axis_per_frame)`
  - `compute_sliding_window_drift_rate(error_series, path_length, window_size, stride)`
  - `compute_window_samples_for_correlation(ODI_series, axis_error_series, weak_error_series)`
- Implemented `scripts/03_eval_metrics.py`.
  - Single sequence mode:
    `python3 scripts/03_eval_metrics.py --seq data/minibench/ST-L3-S01-M1 --odi results/day14/raw/ST-L3-S01-M1_odi.csv --est results/day14/raw/ST-L3-S01-M1_pose_est_toy.tum --out results/day14/metrics/ST-L3-S01-M1_metrics.csv`
  - Batch mode:
    `python3 scripts/03_eval_metrics.py --all --config configs/detector/odi_default.yaml`
- Added Day 8 tests in `tests/test_metrics.py`.
- Updated `scripts/reproduce_day14.sh` to include the Day 8 metrics command with `configs/detector/odi_default.yaml`.

## Reproducibility Record

- Date: 2026-05-28
- Repository: `/home/lj/Degen-LIO`
- Git commit at run start: `b8dd628`
- Detector config: `configs/detector/odi_default.yaml`
- Random seed: `42`
- Window config: `window_size=20`, `window_stride=5`

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
- `python3 -m pytest -q`: `55 passed in 1.76s`

## Output Files

- Window metrics:
  - `results/day14/metrics/OC-L0-S01-M1_metrics.csv`
  - `results/day14/metrics/ST-L3-S01-M1_metrics.csv`
  - `results/day14/metrics/CT-L2-S01-M2_metrics.csv`
  - `results/day14/metrics/RT-L4-S01-M1_metrics.csv`
- Summary table:
  - `results/day14/tables/day08_metric_summary.csv`

## Metric Summary

| sequence_id | ATE_RMSE | RPE_mean | final_axis_error | final_cross_error | mean_axis_error | mean_cross_error | median_axis_drift_rate | median_cross_drift_rate | ODI_mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| OC-L0-S01-M1 | 0.003125 | 0.004051 | 0.000017 | 0.002841 | 0.001343 | 0.002306 | 0.000011 | -0.000036 | 0.512403 |
| ST-L3-S01-M1 | 3.029606 | 0.022082 | 5.222598 | 0.003415 | 2.625349 | 0.001961 | 0.043301 | -0.000004 | 0.728854 |
| CT-L2-S01-M2 | 2.011895 | 0.026967 | 3.479322 | 0.002666 | 1.739733 | 0.001959 | 0.034409 | -0.000001 | 0.728128 |
| RT-L4-S01-M1 | 3.897663 | 0.026148 | 6.717231 | 0.000507 | 3.377445 | 0.001995 | 0.047915 | 0.000001 | 0.728880 |

Full summary with `AIS_mean`, `lambda_min_median`, and `condition_number_median` is saved at:

`results/day14/tables/day08_metric_summary.csv`

## Trend Check

- ST shows clear tunnel-axis drift: final axis error `5.222598 m` versus final cross error `0.003415 m`.
- RT shows clear tunnel-axis drift: final axis error `6.717231 m` versus final cross error `0.000507 m`.
- CT also shows local-axis drift under the curved-axis definition: final axis error `3.479322 m` versus final cross error `0.002666 m`.
- OC does not obviously diverge: `ATE_RMSE=0.003125 m`, final axis error `0.000017 m`, final cross error `0.002841 m`.

## Day 7 Bias Audit

- Day 7 `toy_lio` intentionally used scene-family-dependent motion noise and `axis_bias`: OC near zero, CT/ST/RT higher.
- Day 8 metrics do not trust or reuse the Day 7 internal summary. They are recomputed from:
  - saved estimated TUM trajectory;
  - saved GT TUM trajectory;
  - saved `axis.csv`;
  - saved ODI CSV.
- Day 8 results must not be treated as paper main experiments. They are only the Day 14 synthetic probe for checking whether the minimum pipeline can expose axis drift under weak geometric constraints.
- Day 10 must run per-sequence correlation. A merged-only correlation would be unsafe because scene-family bias could inflate apparent ODI-drift association.

## Failed Items

- None.

## Day 9 Most Important Task

- Implement weak-direction extraction and alignment using the eigenspectrum/eigenvectors from the 6DoF pose block.
- Keep the Day 8 audit constraint active: do not tune `toy_lio` or use ODI to manufacture drift. Weak-direction alignment should be evaluated against saved trajectory/axis behavior, not used to generate it.
