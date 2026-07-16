# Harmful-Bias Multihyp Research Spike — Day 2 Interface Audit Report

## 1. Day 2 unique question

Day 2 answers only this question:

> Where can a read-only observation tap copy FAST-LIO2's exact formal point-to-plane update inputs so that the estimator's state, covariance, correspondence lifecycle, iteration count, and map are unchanged?

No tap was implemented today.

## 2. Frozen revisions

- Degen-LIO branch: `spike/harmful-bias-multihyp-dev`
- Degen-LIO Day 1 baseline / current HEAD: `6655d5ca347c223bd3ad2de06cf9707f8a949fa5`
- Day 1 checkpoint: `checkpoint/multihyp-d1-pass`
- FAST-LIO2 path alias: `$HOME/fastlio2_ws/src/FAST_LIO`
- FAST-LIO2 branch: `main`
- FAST-LIO2 commit: `7cc4175de6f8ba2edf34bab02a42195b141027e9`
- pinned IKD-tree submodule commit: `e2e3f4e9d3b95a9e66b1ba83dc98d4a05ed8a3c4`
- FAST-LIO2 worktree: clean

## 3. Actual measurement-model entrypoint

The formal point-to-plane model is:

- file: `src/laserMapping.cpp`
- function: `h_share_model`
- lines: 638–754
- file SHA-256: `edba2d22e98507c86c61126dcca6c2c3ad369e418d0b82f2be9e19f3ee757ac8`

It is registered through `kf.init_dyn_share(...)` and called by `update_iterated_dyn_share_modified`.

## 4. Actual residual

The code computes:

```text
p_world = R_world_imu * (R_imu_lidar * p_lidar + t_imu_lidar) + p_world_imu
pd2 = n_world_x*x_world + n_world_y*y_world + n_world_z*z_world + d_world
h[i] = -pd2
```

`esti_plane` normalizes `n_world`, so:

- `pd2` is signed point-to-plane distance;
- units are meters;
- the formal filter innovation is `-pd2`;
- accepted signed `pd2` is stored in `normvec[i].intensity`;
- `res_last[i]` stores only `abs(pd2)` for diagnostics;
- the residual is not robust-weighted.

Result: `RESIDUAL_SIGN_CONFIRMED=true`.

## 5. Actual Jacobian

`h_share_model` constructs an `N x 12` native Jacobian:

```text
[delta_p_world(3),
 delta_theta_imu_body_right(3),
 delta_theta_extrinsic_right(3),
 delta_t_extrinsic_imu_body(3)]
```

The detector mapping is:

```python
J_detector = H_native[:, [3, 4, 5, 0, 1, 2]]
```

Detector order is:

```text
[delta_theta_x, delta_theta_y, delta_theta_z,
 delta_p_x,     delta_p_y,     delta_p_z]
```

No sign change and no numeric coordinate transform are required. The retained tangent coordinates are mixed native coordinates: rotation is a right perturbation in IMU/body-local axes and translation is additive in world axes.

Result: `POSE_JACOBIAN_MAPPING_CONFIRMED=true`.

## 6. Actual noise and weight semantics

FAST-LIO2 passes `LASER_POINT_COV = 0.001` into the formal update. The filter treats it as one scalar measurement variance shared by every row and does not square it.

- representation: `CONSTANT_SCALAR_VARIANCE`
- value: `0.001 m^2`
- native per-point variance: false
- robust weight: none
- detector input: `R_diag = 0.001` for every exported row
- point-selection score: acceptance only, not a variance or weight

Result: `MEASUREMENT_WEIGHT_SEMANTICS_CONFIRMED=true`.

## 7. Prior pose and covariance

IMU propagation reaches the scan end in `src/IMU_Processing.hpp:298-303`. The propagated state is available through `get_x()` and covariance through `get_P()`.

- covariance dimension: `23 x 23`
- `get_P()` native API: const reference
- native pose ordering: position indices 0–2, rotation indices 3–5
- detector pose covariance reorder: `[3,4,5,0,1,2]` on both axes

The Day 3 collector must make its own copy before the LiDAR update call.

Results:

- `PRIOR_POSE_ACCESS_CONFIRMED=true`
- `PRIOR_COVARIANCE_ACCESS_CONFIRMED=true`

## 8. Measurement iteration semantics

At default `max_iteration=4`, FAST-LIO2 can attempt `h_share_model` up to five times for an update-invoked scan. The filter copies `x_propagated` and `P_propagated`, then calls the model before applying any correction.

Consequences:

- the first valid linearization is the IMU-propagated prior;
- if an earlier model call is invalid, it cannot change state, so the later first valid call is still prior;
- nearest neighbors are recomputed conditionally from `dyn_share.converge`;
- point transforms, plane fit, residual, validity, compaction, J, and h are recomputed for every valid call;
- the native loop index is private, but a collector-only attempted-call counter is deterministic;
- export rule is exactly `FIRST_VALID_LINEARIZATION`;
- at most one detector record is exported per synchronized scan.

Results:

- `FIRST_LINEARIZATION_IS_PRIOR_CONFIRMED=true`
- `ITERATION_SEMANTICS_CONFIRMED=true`

## 9. Map mutation boundary

Confirmed map operations:

- current-scan local-map range update and possible delete: `lasermap_fov_segment`, before J/r construction;
- nearest-neighbor map read: inside `h_share_model`;
- initial map `Build`: separate branch that skips the scan update;
- post-update insertion/downsample deletion: `map_incremental` and `KD_TREE::Add_Points`;
- rebuild coordination: inside IKD-tree add/delete paths;
- map size reads: `validnum()` and `size()`.

The current-scan FOV delete occurs before the formal observation exists. Therefore the approved design is split:

1. copy prior pose/covariance and reset collector state after IMU propagation, before FOV pruning;
2. copy exact first-valid J/r/correspondences after native row construction inside `h_share_model`;
3. finalize outside the update with no estimator control signal.

The formal copied observation is explicitly defined against the post-FOV-prune map. It is copied before state correction for that callback, before post-update map insertion, and before the next scan's map deletion.

Result: `MAP_MUTATION_BOUNDARY_CONFIRMED=true`.

## 10. Correspondence ID feasibility

FAST-LIO2 exposes current point index, current point coordinates, ordered native neighbor coordinates, neighbor distances during a query, fitted plane coefficients, validity, and accepted count. It exposes no stable map-point or patch ID.

Mode: `DERIVABLE_PROXY`.

The contract defines a deterministic SHA-256 proxy over sequence ID, scan index, current point index, ordered quantized neighbor coordinates, and quantized plane coefficients. Memory addresses and thread order are excluded.

Result: `CORRESPONDENCE_SOURCE_CONFIRMED=true`.

## 11. Detector input mapping

The unique production per-frame detector is:

```text
src/degen_detector/odi_tracker.py::compute_metrics_for_frame
```

It requires:

- `J` with shape `[N, 6]`;
- `R_diag` with shape `[N]`, strictly positive variances;
- state order rotation first, translation second;
- scale matrix `diag(s_theta,s_theta,s_theta,s_p,s_p,s_p)`.

It computes the whitened pose information, translation Schur information, ODI, weak direction, eigengap/stability, trigger state, and output metric dictionary. Residual values are not required by the current detector entrypoint, but the Day 3 draft record retains formal residuals for audit checksums and future traceability.

Results:

- `DETECTOR_ENTRYPOINT_CONFIRMED=true`
- `DETECTOR_INPUT_MAPPING_CONFIRMED=true`

## 12. Ground-truth boundary

The formal detector input is J, variance, and configuration. Ground-truth pose is not consumed. Axis is an optional diagnostic; removing it makes axis-alignment outputs unavailable but leaves core detector outputs unchanged, as verified by `tests/test_detector_no_gt_dependency.py`.

Result: `NO_GT_INTERFACE_CONFIRMED=true`.

## 13. Unresolved items

Source-map unresolved count: 0.

No source-semantic blocker remains. Day 3 still needs implementation review for canonical serialization, bounded buffering, and numerical identity regression tests. Those are implementation obligations rather than unresolved interface semantics.

## 14. Day 3 authorization

All required source roles are present:

- source-map rows: 46
- `CONFIRMED`: 43
- `DERIVABLE`: 3
- `NOT_NATIVE`: 0
- `UNRESOLVED`: 0
- required roles: 31 of 31

Static conclusion:

```text
FASTLIO2_SOURCE_MAP_COMPLETE=true
DAY2_INTERFACE_AUDIT_PASS=true
DAY3_READONLY_TAP_AUTHORIZED=true
```

This authorization is limited to implementing and validating a read-only tap under the frozen contract. It does not authorize real-data runs, rosbag replay, scientific claims, Stage 3, or formal FAST-LIO2 integration.

## 15. Actions explicitly not performed

Today:

- no Degen-LIO source, script, test, or config was modified;
- no FAST-LIO2 source was modified;
- FAST-LIO2 was not compiled;
- no rosbag was read or replayed;
- no dataset or scientific experiment was run;
- no observation tap, logger, adapter, or ROS topic was implemented;
- no Day 2 commit was created;
- nothing was pushed.

Artifact index:

| Artifact | SHA-256 |
|---|---|
| `docs/harmful_bias/adapter_contract.md` | `e9a23a61427f79d074fb63ae74768a7bed22b94784a8842979e6f1e51c6addfe` |
| `docs/harmful_bias/fastlio2_dataflow.md` | `ccc8c5be06d7804a187ed2e1622fe4d47f63266142c8e309a5475fbcce40b070` |
| `manifests/harmful_bias/fastlio2_source_map.csv` | `dbafa32d4fe34c3ac30c010520fe0617445175abeab6c16c0d3e4c98487a50b3` |
| `manifests/harmful_bias/fastlio2_state_layout.csv` | `808d19bf6c7bebeda106a7b90c7d03673138fbba203d2a6286ca249ac7200d9a` |
| `manifests/harmful_bias/fastlio2_mutation_boundary.csv` | `36b9e34ef7949cd2ddd36d281e42c929b2bd33db25abe8dcad655fb6352c3f9c` |
| `manifests/harmful_bias/detector_input_source_map.csv` | `f9dba2c28d24271f96f85723fa44b0b7dd78d2bf8fb260591e668fa264be4ddb` |
