# Metric Redesign Stage 1b Gate Report

Final decision: **STAGE1B_NO_GO**.

Scientific gate failure is reported as a normal completed experiment, not as an engineering exception.

## Gate summary

- ENGINEERING_PASS
- MECHANISM_PASS
- PREDICTION_FAIL

### Audited checks

- sensor_count: `{"actual": 90, "expected": 90, "pass": true}`
- process_trial_count: `{"actual": 2700, "expected": 2700, "pass": true}`
- one_row_per_sensor_run: `true`
- process_trials_aggregated: `true`
- common_process_noise: `true`
- full_pytest: `{"branch": "feature/metric-redesign-stage1b", "command": "pytest -q", "duration_seconds": 31.57, "notes": "Exact full-suite command completed from the final Stage 1b result commit; no skipped or deleted Stage 1b tests.", "status": "passed", "test_count": 150, "verified_date": "2026-07-14"}`
- geometry_structure: `true`
- observation_geometry_and_retention: `true`
- geometry_axis_information_pair_rates: `[1.0, 0.8333333333333334]`
- observation_axis_information_pair_rates: `[1.0, 1.0]`
- prediction_details: `{"geometry": {"odi_rho": 0.8294117647058824, "primary_ci": [0.5238095238095238, 0.9523809523809523], "primary_monotonic_pair_rate": 0.8333333333333334, "primary_rho": 0.5794117647058823, "within_level_residual_rho": -0.3941176470588235}, "observation": {"odi_rho": 0.6911764705882353, "primary_ci": [0.5476190476190476, 0.6904761904761905], "primary_monotonic_pair_rate": 1.0, "primary_rho": 0.6235294117647059, "within_level_residual_rho": 0.7823529411764706}}`

## Independent-sample accounting

- Independent sensor runs: 90
- One sensor_run_summary row is one independent spectrum sample.
- Process trials are repeated outcomes within a sensor run and are not independent spectrum samples.

## Level summaries

| Sweep | Split | Level | N | geometry support | axial fraction | axis information | primary metric | primary target |
|---|---|---|---:|---:|---:|---:|---:|---:|
| geometry | test | L1 | 4 | 8.39126 | 0.788997 | 220.648 | 0.00458406 | 5.47811e-06 |
| geometry | train | L1 | 6 | 7.45664 | 0.786589 | 200.521 | 0.00504758 | 6.39413e-06 |
| geometry | test | L2 | 4 | 6.4247 | 0.680599 | 206.972 | 0.0050101 | 1.74363e-06 |
| geometry | train | L2 | 6 | 6.07814 | 0.678711 | 143.797 | 0.00751625 | 3.70544e-06 |
| geometry | test | L3 | 4 | 3.64243 | 0.482878 | 99.1091 | 0.01291 | 9.24753e-06 |
| geometry | train | L3 | 6 | 3.59159 | 0.482227 | 53.7392 | 0.0183736 | 2.75295e-05 |
| geometry | test | L4 | 4 | 1.41997 | 0.236719 | 22.0521 | 0.0720297 | 0.00031137 |
| geometry | train | L4 | 6 | 1.40139 | 0.236784 | 27.7499 | 0.0715341 | 0.000602998 |
| geometry | test | OC | 4 | 0 | 0 | 250.591 | 0.0040013 | 3.3897e-06 |
| geometry | train | OC | 6 | 0 | 0 | 244.27 | 0.00409702 | 9.78058e-07 |
| observation | test | O1 | 4 | 9.10961 | 0.831445 | 204.709 | 0.00491264 | 4.06809e-06 |
| observation | train | O1 | 6 | 7.81484 | 0.831055 | 176.504 | 0.00568681 | 2.26777e-06 |
| observation | test | O2 | 4 | 9.10961 | 0.661784 | 163.818 | 0.00614716 | 3.37396e-06 |
| observation | train | O2 | 6 | 7.81484 | 0.659766 | 140.655 | 0.00715528 | 1.76082e-06 |
| observation | test | O3 | 4 | 9.10961 | 0.326497 | 77.197 | 0.0127965 | 7.34348e-06 |
| observation | train | O3 | 6 | 7.81484 | 0.326888 | 68.0065 | 0.0148711 | 1.40563e-05 |
| observation | test | O4 | 4 | 9.10961 | 0.0867187 | 20.5806 | 0.0528487 | 1.47204e-05 |
| observation | train | O4 | 6 | 7.81484 | 0.089974 | 18.5048 | 0.0598391 | 3.7341e-05 |

## Geometry Sweep correlations

| Split | Metric | Expected | rho | geometry-block bootstrap 95% CI | N |
|---|---|---|---:|---:|---:|
| train | mean_inverse_axis_information | positive | 0.472174 | [0.214286, 0.904762] | 24 |
| train | harmonic_axis_information | negative | -0.472174 | [-0.904762, -0.214286] | 24 |
| train | low_axis_information_ratio | positive | nan | [nan, nan] | 24 |
| train | longest_low_information_duration_s | positive | nan | [nan, nan] | 24 |
| train | ODI_trans_median | positive | 0.465217 | [0.238095, 0.904762] | 24 |
| train | lambda_min_trans_normalized_median | negative | -0.474783 | [-0.905759, -0.238095] | 24 |
| train | condition_number_trans_median | positive | 0.466087 | [0.238095, 0.904762] | 24 |
| train | axis_information_normalized_median | negative | -0.444348 | [-0.891798, -0.180628] | 24 |
| test | mean_inverse_axis_information | positive | 0.579412 | [0.52381, 0.952381] | 16 |
| test | harmonic_axis_information | negative | -0.579412 | [-0.952381, -0.52381] | 16 |
| test | low_axis_information_ratio | positive | nan | [nan, nan] | 16 |
| test | longest_low_information_duration_s | positive | nan | [nan, nan] | 16 |
| test | ODI_trans_median | positive | 0.829412 | [0.761905, 0.97619] | 16 |
| test | lambda_min_trans_normalized_median | negative | -0.820588 | [-1, -0.642857] | 16 |
| test | condition_number_trans_median | positive | 0.829412 | [0.690476, 0.97619] | 16 |
| test | axis_information_normalized_median | negative | -0.579412 | [-0.952381, -0.52381] | 16 |

## Observation Sweep correlations

| Split | Metric | Expected | rho | geometry-block bootstrap 95% CI | N |
|---|---|---|---:|---:|---:|
| train | mean_inverse_axis_information | positive | 0.501739 | [0.214286, 0.857143] | 24 |
| train | harmonic_axis_information | negative | -0.501739 | [-0.857143, -0.214286] | 24 |
| train | low_axis_information_ratio | positive | nan | [nan, nan] | 24 |
| train | longest_low_information_duration_s | positive | nan | [nan, nan] | 24 |
| train | ODI_trans_median | positive | 0.58087 | [0.238095, 0.952381] | 24 |
| train | lambda_min_trans_normalized_median | negative | -0.541739 | [-0.952381, -0.142857] | 24 |
| train | condition_number_trans_median | positive | 0.56 | [0.214286, 0.97619] | 24 |
| train | axis_information_normalized_median | negative | -0.478261 | [-0.809524, -0.214286] | 24 |
| test | mean_inverse_axis_information | positive | 0.623529 | [0.547619, 0.690476] | 16 |
| test | harmonic_axis_information | negative | -0.623529 | [-0.690476, -0.547619] | 16 |
| test | low_axis_information_ratio | positive | nan | [nan, nan] | 16 |
| test | longest_low_information_duration_s | positive | nan | [nan, nan] | 16 |
| test | ODI_trans_median | positive | 0.691176 | [0.404762, 0.904762] | 16 |
| test | lambda_min_trans_normalized_median | negative | -0.676471 | [-0.904762, -0.357143] | 16 |
| test | condition_number_trans_median | positive | 0.717647 | [0.47619, 0.952381] | 16 |
| test | axis_information_normalized_median | negative | -0.632353 | [-0.690476, -0.547619] | 16 |

## Within-level residual correlations

- geometry train: -0.273043 (train level medians frozen before test).
- geometry test: -0.394118 (train level medians frozen before test).
- observation train: 0.352174 (train level medians frozen before test).
- observation test: 0.782353 (train level medians frozen before test).

## Paired monotonicity

- geometry train: metric pair rate=1; target pair rate=0.722222.
- geometry test: metric pair rate=0.833333; target pair rate=0.666667.
- observation train: metric pair rate=1; target pair rate=0.777778.
- observation test: metric pair rate=1; target pair rate=0.583333.

## Frozen analysis statement

The primary metric, primary target, epsilon, low-information threshold, transforms, directions, and bootstrap design were frozen before test evaluation. Test geometry seeds were evaluated once; the program does not sweep test-set parameters.

## Claim boundary

This stage uses finite synthetic plane patches and a 6DoF motion-propagation surrogate. Frame 0 uses the known initial pose; later estimator propagation and residuals do not read GT. This stage does not implement a weak-subspace update, does not integrate FAST-LIO2, does not validate ODI as a finished method, and is not a complete Degen-LIO estimator.
