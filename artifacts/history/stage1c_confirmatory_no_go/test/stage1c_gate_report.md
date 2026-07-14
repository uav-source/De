# Metric Redesign Stage 1c Confirmatory Gate Report

- Engineering: **ENGINEERING_PASS**
- Mechanism: **MECHANISM_FAIL**
- Detector: **DETECTOR_FAIL**
- Prediction: **PREDICTION_FAIL**
- WEAK_UPDATE_AUTHORIZED: **false**
- RISK_WARNING_AUTHORIZED: **false**

## Detector results

- geometry: rho=0.699794, CI=[0.53653, 0.829542], median tau=0.540062, positive geometry ratio=0.875, paired rate=0.666667, severe weak alignment=0.
- observation: rho=0.819327, CI=[0.784488, 0.858146], median tau=0.617213, positive geometry ratio=1, paired rate=0.729167, severe weak alignment=0.

Open-control weak-axis aligned false-trigger rate: 0.

## Primary exposure prediction

- geometry: rho=0.477656, CI=[0.272167, 0.642942], positive geometry ratio=0.875, paired rate=0.958333.
- observation: rho=0.166163, CI=[-0.0589476, 0.406542], positive geometry ratio=0.75, paired rate=1.

## ODI auxiliary risk association

- geometry: rho=0.525321, CI=[0.359166, 0.68407].
- observation: rho=0.253526, CI=[0.0568286, 0.46321].

## Development-centered test residuals

- geometry: rho=0.0897436, CI=[-0.22736, 0.35376].
- observation: rho=-0.207647, CI=[-0.348963, -0.01365].

## Audited checks

- engineering: `{"combined_process_trials": 7020, "combined_sensor_runs": 234, "config_matches_lock": true, "development_test_isolated": true, "git_status_clean": true, "longest_low_information_duration_unique_count": 14, "low_information_ratio_unique_count": 16, "manifest_version_tracking": true, "no_gt_leakage_regression": true, "process_noise_independence_violations": 0, "process_noise_pairing_violations": 0, "source_tree_matches_lock": true, "test_provenance_current_commit": true, "test_unique_noise_sequences": 1440, "thirty_trials_per_sensor": true, "trajectories_complete": true, "verified_pytest_twice": true}`
- mechanism: `{"geometry_axis_information_ordered_blocks": 6, "geometry_block_count": 8, "geometry_structure_pass": true, "observation_axis_information_ordered_blocks": 8, "observation_block_count": 8, "observation_retention_nested": true, "observation_structure_pass": true}`
- detector: `{"geometry": false, "observation": false, "open_control": {"sensor_run_count": 16, "weak_alignment_median": 0.0, "weak_axis_aligned_false_trigger_rate": 0.0}}`
- prediction: `{"geometry": false, "observation": false}`

## Claim boundary

Stage 1c authorizes or rejects only the next controlled research stage. It does not implement a weak-subspace update, integrate FAST-LIO2, validate online drift warning in a real LIO system, or complete Degen-LIO.
