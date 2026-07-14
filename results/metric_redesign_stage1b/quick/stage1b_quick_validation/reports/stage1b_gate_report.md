# Metric Redesign Stage 1b Gate Report

Final decision: **STAGE1B_NO_GO**.

Scientific gate failure is reported as a normal completed experiment, not as an engineering exception.

## Gate summary

- ENGINEERING_PASS
- MECHANISM_PASS
- PREDICTION_FAIL

### Audited checks

- sensor_count: `{"actual": 9, "expected": 9, "pass": true}`
- process_trial_count: `{"actual": 27, "expected": 27, "pass": true}`
- one_row_per_sensor_run: `true`
- process_trials_aggregated: `true`
- common_process_noise: `true`
- full_pytest: `{"branch": "feature/metric-redesign-stage1b", "command": "pytest -q", "duration_seconds": 30.84, "notes": "Exact full-suite command completed after the Stage 1b full run; no skipped or deleted Stage 1b tests.", "status": "passed", "test_count": 150, "verified_date": "2026-07-14"}`
- geometry_structure: `true`
- observation_geometry_and_retention: `true`
- geometry_axis_information_pair_rates: `[1.0]`
- observation_axis_information_pair_rates: `[1.0]`
- prediction_details: `{"geometry": {"odi_rho": NaN, "primary_ci": [NaN, NaN], "primary_monotonic_pair_rate": NaN, "primary_rho": NaN, "within_level_residual_rho": NaN}, "observation": {"odi_rho": NaN, "primary_ci": [NaN, NaN], "primary_monotonic_pair_rate": NaN, "primary_rho": NaN, "within_level_residual_rho": NaN}}`

## Independent-sample accounting

- Independent sensor runs: 9
- One sensor_run_summary row is one independent spectrum sample.
- Process trials are repeated outcomes within a sensor run and are not independent spectrum samples.

## Level summaries

| Sweep | Split | Level | N | geometry support | axial fraction | axis information | primary metric | primary target |
|---|---|---|---:|---:|---:|---:|---:|---:|
| geometry | train | L1 | 1 | 8.7915 | 0.786458 | 197.898 | 0.00504574 | 1.1385e-05 |
| geometry | train | L2 | 1 | 7.15921 | 0.68151 | 173.21 | 0.00818637 | 5.03135e-06 |
| geometry | train | L3 | 1 | 3.59159 | 0.48112 | 90.4426 | 0.0177371 | 2.78792e-05 |
| geometry | train | L4 | 1 | 1.32525 | 0.23776 | 34.3074 | 0.0371745 | 0.000673735 |
| geometry | train | OC | 1 | 0 | 0 | 246.146 | 0.0040809 | 3.32317e-06 |
| observation | train | O1 | 1 | 9.15188 | 0.833464 | 188.722 | 0.00534766 | 3.02816e-06 |
| observation | train | O2 | 1 | 9.15188 | 0.659635 | 156.817 | 0.00643651 | 8.84494e-07 |
| observation | train | O3 | 1 | 9.15188 | 0.323828 | 79.5076 | 0.0128482 | 1.05336e-05 |
| observation | train | O4 | 1 | 9.15188 | 0.0901042 | 20.528 | 0.0532421 | 2.72608e-05 |

## Geometry Sweep correlations

| Split | Metric | Expected | rho | geometry-block bootstrap 95% CI | N |
|---|---|---|---:|---:|---:|
| train | mean_inverse_axis_information | positive | 0.8 | [nan, nan] | 4 |
| train | harmonic_axis_information | negative | -0.8 | [nan, nan] | 4 |
| train | low_axis_information_ratio | positive | nan | [nan, nan] | 4 |
| train | longest_low_information_duration_s | positive | nan | [nan, nan] | 4 |
| train | ODI_trans_median | positive | 0.8 | [nan, nan] | 4 |
| train | lambda_min_trans_normalized_median | negative | -0.8 | [nan, nan] | 4 |
| train | condition_number_trans_median | positive | 0.8 | [nan, nan] | 4 |
| train | axis_information_normalized_median | negative | -0.8 | [nan, nan] | 4 |

## Observation Sweep correlations

| Split | Metric | Expected | rho | geometry-block bootstrap 95% CI | N |
|---|---|---|---:|---:|---:|
| train | mean_inverse_axis_information | positive | 0.8 | [nan, nan] | 4 |
| train | harmonic_axis_information | negative | -0.8 | [nan, nan] | 4 |
| train | low_axis_information_ratio | positive | nan | [nan, nan] | 4 |
| train | longest_low_information_duration_s | positive | nan | [nan, nan] | 4 |
| train | ODI_trans_median | positive | 1 | [nan, nan] | 4 |
| train | lambda_min_trans_normalized_median | negative | -1 | [nan, nan] | 4 |
| train | condition_number_trans_median | positive | 1 | [nan, nan] | 4 |
| train | axis_information_normalized_median | negative | -0.8 | [nan, nan] | 4 |

## Within-level residual correlations

- geometry train: nan (train level medians frozen before test).
- observation train: nan (train level medians frozen before test).

## Paired monotonicity

- geometry train: metric pair rate=1; target pair rate=0.666667.
- observation train: metric pair rate=1; target pair rate=0.666667.

## Frozen analysis statement

The primary metric, primary target, epsilon, low-information threshold, transforms, directions, and bootstrap design were frozen before test evaluation. Test geometry seeds were evaluated once; the program does not sweep test-set parameters.

## Claim boundary

This stage uses finite synthetic plane patches and a 6DoF motion-propagation surrogate. Frame 0 uses the known initial pose; later estimator propagation and residuals do not read GT. This stage does not implement a weak-subspace update, does not integrate FAST-LIO2, does not validate ODI as a finished method, and is not a complete Degen-LIO estimator.
