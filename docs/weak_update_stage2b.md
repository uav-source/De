# Weak-Subspace Update Stage 2B

Stage 2B is a controlled synthetic benchmark for a covariance-aware selective LiDAR update. It preserves the frozen Stage 2A ODI formula and primary weak-direction definition. It does not implement FAST-LIO2, real IMU propagation, real data association, drift-risk prediction, or a complete Degen-LIO system.

## Estimator contract

At every frame the estimator propagates the previous pose with the standalone 6-DoF motion surrogate, propagates a finite symmetric 6-by-6 covariance, and relinearizes point-to-plane residuals and Jacobians once at that current prior. The propagation uses `F = I` as a controlled first-order Stage 2B approximation. The process translation covariance is defined in the body frame and rotated into the world frame; it never uses the ground-truth tunnel axis.

All LiDAR methods use the same Huber normal equation with a fixed 2.5-sigma threshold and the same MAP prior. The five methods are `motion_only`, `huber_full`, `huber_global`, `huber_selective`, and the explicitly offline-only `huber_oracle_selective`. Non-oracle estimation does not read `pose_gt` or `axis_per_frame`; ground truth enters only after estimation in the metrics module.

For an actionable detected direction `v`, selective attenuation uses

```text
A_p = I - (1 - sqrt(alpha)) vv^T
A_6 = diag(I_3, A_p)
H_s = A_6^T H A_6
b_s = A_6^T b
```

Alpha equal to one and a non-actionable detector state both reduce exactly to `huber_full`. Alpha equal to zero removes the weak-direction information and its cross terms. The effective information matrix is checked for positive semidefiniteness.

## Locked stress and pairing

The benchmark compares `clean` with a deterministic `axial_correspondence_slip`: 25% of axial patch identities are selected from geometry and sensor seeds, then shifted by 0.08 m along their normals during one locked eight-frame burst. The stress seed excludes method, process seed, and level. It does not change points, normals, the Jacobian formula, or measurement variance. Open Control contains no axial patches and therefore receives zero contamination.

Within every sweep, level, stress, geometry seed, sensor seed, and process seed group, all five methods share observation, stress, process-noise, and initial-state checksums. Geometry seed is the outer bootstrap block.

## Development and Test

Development uses geometry seeds 1709 through 2687 from the frozen list, sensor seeds 55 and 66, and process seeds 3001-3010. It contains 360 sensor-stress blocks and 18,000 saved method trials. Only Development may choose one alpha from `0, 0.1, 0.25, 0.5, 0.75`; the 0.95 Open-Control motion-prior ODI quantile, selected alpha, code/config hashes, stress parameters, and reserved seeds are then frozen in the update lock.

Test uses disjoint geometry seeds 2801 through 3863 from the frozen list, sensor seeds 77 and 88, and process seeds 4001-4020. It contains 360 sensor-stress blocks and 36,000 method trials. Test refuses a dirty tree, an uncommitted lock, any source/config/stress mismatch, missing current-commit pytest provenance, or changed reserved seeds. There is no lock-mismatch override.

Run in order:

```bash
python3 scripts/31_run_weak_update_stage2b.py --quick --run-id weak_update_stage2b_quick_v1
python3 scripts/31_run_weak_update_stage2b.py --development --run-id weak_update_stage2b_dev_v1 --workers 8 --resume
python3 scripts/31_run_weak_update_stage2b.py --lock-update --development-run-dir results/weak_update_stage2b/development/weak_update_stage2b_dev_v1
python3 scripts/29_run_verified_pytest.py --output results/weak_update_stage2b/pytest_provenance.json
python3 scripts/31_run_weak_update_stage2b.py --test --run-id weak_update_stage2b_test_v1 --update-lock artifacts/current/weak_update_stage2b/locked/update_lock.json --workers 8 --resume
python3 scripts/31_run_weak_update_stage2b.py --analyze-only --run-dir results/weak_update_stage2b/test/weak_update_stage2b_test_v1
```

If Development has no feasible alpha, it records `DEVELOPMENT_NO_GO` and Test must not run. Reserved Test results must be consumed once; alpha, Huber threshold, and stress parameters cannot be changed afterward while reusing those Test seeds.

## Gates and claim boundary

The Engineering Gate checks the committed lock/provenance, exact counts, checksum pairing, covariance and solver behavior, GT isolation, and mathematical invariants. The Stress Mechanism Gate checks axial-only, eight-frame, method-independent contamination with unchanged variance. The Selective Update Gate separately requires Geometry and Observation severe-contamination benefit, clean non-inferiority, and Open-Control safety.

Only all gates passing can set both `SELECTIVE_UPDATE_PASS` and `FAST_LIO2_INTEGRATION_AUTHORIZED` true. This is an authorization for a later integration stage, not an integration performed here. `RISK_WARNING_AUTHORIZED` is always false.
