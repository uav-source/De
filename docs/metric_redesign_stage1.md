# Metric Redesign Stage 1

## Purpose and claim boundary

The legacy Day 14-Day 21 experiments could not validate ODI because four fixed geometries were reused across many process-noise trials. Tunnel axial information was often exactly zero, the old `Plane` model was infinite, repeated RT structures collapsed to equivalent planes, and the toy estimator used ground truth during propagation and residual construction.

Stage 1 asks one narrower question: when finite local axial support decreases continuously from L1 to L4, do translation information, weak-subspace alignment, and axis drift change reproducibly? It does not implement a weak-subspace update, a complete IMU, or a complete Degen-LIO estimator.

## Independent randomness

- `geometry_seed` controls patch positions, sizes, and orientations. One geometry seed defines one physical scene.
- `sensor_seed` controls finite-patch point sampling, residual noise, visibility/dropout, and therefore one independent spectral observation.
- `process_seed` controls only the standalone motion-propagation surrogate and the resulting trajectory.

Five process trials sharing one sensor run do not provide five independent ODI samples. They are summarized by median, mean, IQR, and MAD before correlation. The primary table therefore has one row per `(sequence_id, sensor_seed)`.

## Finite plane patches and axial support

`PlanePatch` stores an orthonormal `(normal, u_axis, v_axis)` basis, finite half extents, active frame range, sampling weight, and axial-support flag. Sampling is bounded by:

```text
abs((p - center) dot u_axis) <= half_u
abs((p - center) dot v_axis) <= half_v
```

L1-L4 use fixed axial support fractions `0.25`, `0.10`, `0.03`, and `0.005`. Local oblique patches have nonzero tunnel-axis normal components; no full cross-section end cap and no noise-based degeneration is used. L4 is near-degenerate but not constructed as exactly zero information.

The extended `planes.csv` retains the original ten columns and appends basis, extent, weight, and axial-support fields. The loader accepts both schemas.

## Sensor observations

Candidates are sampled from finite patches, transformed into the LiDAR frame, filtered by range and horizontal/vertical field of view, and subjected to seed-controlled dropout. A bounded resampling loop raises an explicit error if it cannot collect the requested points.

Each observation also stores `plane_points_world` and `plane_indices`. The point-to-plane residual at an estimated pose is computed as:

```text
r_i = n_i^T (R_est p_i + t_est - q_i) + measurement_noise_i
```

No ground-truth pose enters this residual.

## Motion propagation surrogate

Ground truth is used once to generate noisy relative translation and rotation measurements in `motion_simulator.py`. Those measurements are saved independently. The estimator then consumes only the motion file and LiDAR observations. Roll, pitch, yaw, and translation are all applied with normalized quaternions.

This is a 6DoF motion-propagation surrogate, not a complete IMU preintegration model or real LIO.

## Translation Schur information

For the whitened 6x6 pose information matrix, rotation is marginalized rather than dropping the cross block:

```text
H_p|theta = H_pp - H_pθ (H_θθ + λI)^-1 H_θp
```

The result is symmetrized and checked for physically significant negative eigenvalues. Information strength is also normalized by the weighted effective sample size:

```text
w_i = 1 / R_i
N_eff = (sum_i w_i)^2 / sum_i w_i^2
H_normalized = H / N_eff
```

`ODI_trans`, normalized translation AIS/lambda-min, translation condition number, trace, weak-subspace dimension, projector alignment, and a gap-qualified primary weak direction are appended to the legacy ODI CSV fields.

## Experiment matrix and outputs

Full mode generates 3 OC geometries and `4 levels x 3 ST geometries`, for 15 geometries total. Two sensor seeds produce 30 independent sensor runs. Five process seeds per sensor run produce 150 trajectory trials, which are aggregated before scientific correlation.

Outputs are written under:

```text
data/metric_redesign_stage1/
results/metric_redesign_stage1/
```

Primary summaries are `sensor_run_summary.csv`, `process_trial_summary.csv`, `window_aggregate.csv`, `level_summary.csv`, `correlation_summary.csv`, `stage1_manifest.json`, and `stage1_gate_report.md`. Raw observations, trajectories, and motion files are ignored by Git.

## Commands

```bash
python3 scripts/26_run_metric_redesign_stage1.py --quick
python3 scripts/26_run_metric_redesign_stage1.py --full
python3 scripts/26_run_metric_redesign_stage1.py --analyze-only
```

Quick mode uses one geometry seed, one sensor seed, two process seeds, OC, and L1-L4. Analyze-only does not regenerate measurements.

## Scientific gate

Execution success is independent of scientific acceptance. The report checks:

- strict `L1 > L2 > L3 > L4` ordering for median normalized translation lambda-min;
- nonzero near-degenerate L4 information;
- increasing `ODI_trans`;
- median L2-L4 weak-subspace axis alignment at least 0.75;
- OC weak-axis false-trigger ratio at most 10%;
- directional Spearman correlation, block-bootstrap 95% interval, independent sample count, and seed-direction stability.

The target correlation magnitude is 0.55, but no parameter is automatically tuned to reach it. Failed mechanism or validity checks produce `NO-GO`; the program still exits successfully when all requested artifacts were generated.
