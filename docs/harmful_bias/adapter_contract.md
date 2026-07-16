# FAST-LIO2 → Degen-LIO Read-Only Adapter Contract

## 1. Purpose and Day 2 boundary

This document freezes the static interface contract needed to build a read-only FAST-LIO2 observation tap on Day 3. Day 2 performs source inspection only: it does not implement a tap, logger, ROS topic, adapter, build, rosbag replay, or scientific run.

The contract answers one question: where and how can the exact formal point-to-plane linearization be copied without changing the estimator?

## 2. Frozen FAST-LIO2 revision

- Path alias: `$HOME/fastlio2_ws/src/FAST_LIO`
- Branch: `main`
- Commit: `7cc4175de6f8ba2edf34bab02a42195b141027e9`
- Pinned IKD-tree submodule commit: `e2e3f4e9d3b95a9e66b1ba83dc98d4a05ed8a3c4`
- Worktree at audit time: clean

All FAST-LIO2 locations and hashes in this document refer to that commit.

## 3. Frozen Degen-LIO detector revision

- Branch: `spike/harmful-bias-multihyp-dev`
- Detector commit / Day 1 baseline commit: `6655d5ca347c223bd3ad2de06cf9707f8a949fa5`
- Day 1 checkpoint: `checkpoint/multihyp-d1-pass`
- Production detector entrypoint: `src/degen_detector/odi_tracker.py::compute_metrics_for_frame`

`compute_metrics_for_sequence` is an offline batch wrapper that calls the per-frame production entrypoint; it is not a second detector implementation.

## 4. Complete scan-to-map dataflow

The active normal path is:

```text
LiDAR callback + IMU callback
    -> sync_packages: one MeasureGroup
    -> IMU predict through scan end
    -> scan-end undistortion
    -> propagated prior state/covariance
    -> local-map FOV maintenance and possible deletion
    -> scan voxel downsampling
    -> update_iterated_dyn_share_modified
         -> h_share_model, two to five attempted calls at default max_iteration=4
              -> current point to world
              -> conditional nearest-neighbor query
              -> plane fit and correspondence acceptance
              -> compact valid correspondences
              -> construct native N x 12 H and N-vector h
         -> iterated state correction and final covariance correction
    -> posterior state
    -> odometry publication
    -> posterior point transform and map_incremental
    -> IKD-tree insertion/downsample deletion/rebuild maintenance
```

The first map build is a separate branch: `ikdtree.Build` is called and that scan immediately continues without a LiDAR update or observation record.

## 5. State and perturbation definitions

The native error-state covariance has 23 DOF in declaration order:

| Native columns | State block | Perturbation | Physical frame |
|---:|---|---|---|
| 0–2 | position | additive | world |
| 3–5 | IMU rotation | right, `R <- R Exp(delta)` | IMU/body local tangent |
| 6–8 | LiDAR-to-IMU extrinsic rotation | right | LiDAR local tangent |
| 9–11 | LiDAR-to-IMU extrinsic translation | additive | IMU/body |
| 12–14 | velocity | additive | world |
| 15–17 | gyroscope bias | additive | IMU/body |
| 18–20 | accelerometer bias | additive | IMU/body |
| 21–22 | gravity | S2 tangent | world-gravity manifold |

Evidence:

- state declaration: `include/use-ikfom.hpp:12-21`, SHA-256 `1ee2c078ee757ff2dffedf48da764daec152baa79876a70785d010cc2e6165ab`
- SO3 right perturbation: `include/IKFoM_toolkit/mtk/types/SOn.hpp:233-239`, SHA-256 `90a8384a05d656698e6826b892561dc6cd619b62a7e32f9e6e3a9253e5e0c8aa`
- additive vector perturbation: `include/IKFoM_toolkit/mtk/types/vect.hpp:117-122`, SHA-256 `771ecededd51dc694bdadb57f8a49fad7bc6091c6f6112142096954649ac405f`
- declaration-order dispatch: `include/IKFoM_toolkit/mtk/build_manifold.hpp:180-200`, SHA-256 `0e88522551d02e78dc995e6c9d7883d9ecca7190379ec047ab839fff7186ea0f`

## 6. Residual sign and units

Inside `src/laserMapping.cpp::h_share_model`:

```cpp
p_global = s.rot * (s.offset_R_L_I * p_body + s.offset_T_L_I) + s.pos;
pd2 = pabcd(0) * point_world.x
    + pabcd(1) * point_world.y
    + pabcd(2) * point_world.z
    + pabcd(3);
ekfom_data.h(i) = -norm_p.intensity;
```

Variable mapping:

- `p_body`: undistorted and downsampled point in the scan-end LiDAR frame.
- `s.offset_R_L_I * p_body + s.offset_T_L_I`: point in the IMU/body frame.
- `p_global` / `point_world`: point in the world frame.
- `pabcd[0:3]`: unit plane normal in the world frame.
- `pabcd[3]`: world-plane constant `d` in `n^T x + d = 0`.
- `pd2`: signed point-to-plane distance `n^T p_world + d`, in meters.
- `normvec[i].intensity`: accepted signed `pd2`.
- `res_last[i]`: `abs(pd2)`, used only for mean-residual diagnostics.
- formal filter innovation `ekfom_data.h[i]`: `-pd2`, in meters.

`esti_plane` normalizes the fitted normal, so `pd2` is a signed metric distance. The selection expression

```text
s = 1 - 0.9 * abs(pd2) / sqrt(norm(p_body))
```

is an acceptance score, not a measurement variance or robust weight. There is no robust kernel in the formal path. The residual is therefore unweighted before the filter applies its common scalar covariance.

## 7. Native Jacobian column layout

The formal LiDAR measurement Jacobian is `N x 12`, where `N = effct_feat_num`.

For accepted row `i`:

```text
H_native[i] =
[
  n_world^T,                         # columns 0:2, delta position in world
  (p_imu × R_world_imu^T n_world)^T, # columns 3:5, right rotation in IMU/body tangent
  B^T,                               # columns 6:8, right extrinsic rotation
  C^T                                # columns 9:11, additive extrinsic translation in IMU/body
]
```

When online extrinsic estimation is disabled, columns 6–11 are explicitly zero. The first six pose columns keep the same meaning in every iteration.

## 8. Detector 6DoF Jacobian mapping

The Degen-LIO detector requires:

```text
[delta_theta_x, delta_theta_y, delta_theta_z,
 delta_p_x,     delta_p_y,     delta_p_z]
```

The exact row mapping is:

```text
FAST-LIO2 native row
    [delta_p_world(0:2), delta_theta_body_right(3:5), extrinsic(6:11)]
        ↓ pose-column extraction
    [H_native[3], H_native[4], H_native[5],
     H_native[0], H_native[1], H_native[2]]
        ↓ frame/sign transform
    no numeric frame transform; no sign change
        ↓ Degen-LIO detector row
    [delta_theta_x, delta_theta_y, delta_theta_z,
     delta_p_x,     delta_p_y,     delta_p_z]
```

Equivalent array rule:

```python
J_detector = H_native[:, [3, 4, 5, 0, 1, 2]]
```

The detector tangent frame is intentionally mixed and native: rotation columns are IMU/body-local right perturbations, while translation columns are world-axis additive perturbations. The detector computes information in the supplied tangent coordinates and does not require both blocks to share one physical frame.

No sign change is needed for the Jacobian information calculation. The formal innovation remains `h = -pd2`; Day 3 must not negate `H_native` while claiming it is the native formal Jacobian.

## 9. Measurement noise and weight semantics

FAST-LIO2 defines:

```cpp
#define LASER_POINT_COV (0.001)
kf.update_iterated_dyn_share_modified(LASER_POINT_COV, solve_H_time);
```

The filter uses `R` through algebra equivalent to a common covariance `R I`:

```text
P_temp = (P / R)^-1
P_temp_pose += H^T H
```

Contract:

- representation: `CONSTANT_SCALAR_VARIANCE`
- value: `0.001`
- units: meters squared
- per-measurement native variance: false
- robust weight: none
- squared again by filter: false
- information/inverse variance: false
- acceptance score `s`: not exported as weight
- Day 3 detector input: `R_diag = full(N, 0.001)`

The adapter must export the effective variance itself, not its square root and not its reciprocal.

## 10. Prior pose and prior covariance

The formal prior is the state and covariance after IMU propagation through `lidar_end_time` and before any correction from the same scan.

- scan-end propagation: `src/IMU_Processing.hpp:298-303`
- prior state access: `kf.get_x()`
- prior covariance access: `kf.get_P()`
- covariance dimension: `23 x 23`
- API return type: const reference
- Day 3 storage rule: make a collector-owned copy before calling the LiDAR update

Native pose covariance indices are `[position 0:2, rotation 3:5]`. The detector-order pose block is:

```python
pose_order = [3, 4, 5, 0, 1, 2]
P_pose_detector = P_prior[np.ix_(pose_order, pose_order)]
```

Its frame is the same mixed native tangent frame as the detector Jacobian.

The filter itself copies `x_` and `P_` into `x_propagated` and `P_propagated` before its first measurement-model call. Since `h_dyn_share(x_, ...)` is called before any `boxplus`, the first valid linearization is the propagated prior. If an earlier callback is invalid, no correction occurs, so the later first valid callback is still at the propagated prior.

## 11. Measurement iteration semantics

At the default `max_iteration=4`, the loop executes indices `i=-1,0,1,2,3`, so there are at most five attempted measurement-model calls for an update-invoked scan. Normal early return requires two converged valid corrections; therefore an eligible scan ordinarily has two to five attempted calls.

- first call: `dyn_share.converge=true`; nearest neighbors are recomputed.
- subsequent call: nearest neighbors are recomputed only when the previous correction met the convergence limits; otherwise cached neighbor sets are reused.
- every valid call: point transforms, plane fitting, residual selection, compaction, Jacobian construction, and residual-vector construction are recomputed.
- final call: either the second converged valid correction or the last permitted iteration; posterior covariance is then finalized.

The native loop index is private and is not passed to `h_share_model`. Day 3 may derive a collector-only call index by:

1. resetting it exactly once before `update_iterated_dyn_share_modified`;
2. incrementing it exactly once on entry to `h_share_model`;
3. never returning it to estimator logic;
4. exporting only the first callback for which `ekfom_data.valid` remains true after J/r construction.

Sampling rule:

```text
observation_tap_sample = FIRST_VALID_LINEARIZATION
```

Every scan exports at most one detector observation.

## 12. Correspondence source and deterministic ID

Native data available for each accepted row:

- current downsampled point index `i`;
- current LiDAR-frame point;
- current world-frame point;
- `Nearest_Points[i]`;
- neighbor squared distances during a native query;
- fitted normalized plane coefficients `[nx, ny, nz, d]`;
- validity flag `point_selected_surf[i]`;
- accepted-row count `effct_feat_num`.

No stable native map-point or patch ID exists. Day 3 will use `DERIVABLE_PROXY`:

```text
SHA-256(
  length-prefixed UTF-8 sequence_id,
  uint64 scan_index,
  uint64 current_point_index,
  uint32 ordered_neighbor_count,
  ordered quantized neighbor coordinates,
  quantized [nx, ny, nz, d]
)
```

Locked quantization:

- neighbor coordinates: `1e-4 m`
- plane normal components: `1e-6`
- plane constant `d`: `1e-4 m`
- signed integer quantizer: round to nearest with halves away from zero
- serialized integers: signed 64-bit little-endian

The ordered neighbor coordinates must be copied from the native `Nearest_Points[i]` result; no extra query is allowed. Memory addresses, function names, and thread scheduling order are forbidden inputs. Under OpenMP, any temporary collection must be indexed by native point index and compacted in the existing serial accepted-row order.

## 13. Map read/write boundary

Map reads:

- `KD_TREE::Nearest_Search`
- `KD_TREE::size`
- `KD_TREE::validnum`
- read of cached neighbors during insertion selection

Map writes:

- initial `ikdtree.Build`
- current-scan `lasermap_fov_segment` / `Delete_Point_Boxes`
- post-update `map_incremental` / `Add_Points`
- downsample deletion inside `Add_Points`
- IKD-tree rebuild maintenance and operation logging

Important architecture fact: current-scan local-map deletion occurs before formal J/r construction. A single code location cannot be both after complete J/r construction and before that current-scan delete. The authorized design is therefore split:

1. scan-level collector start after IMU propagation and before `lasermap_fov_segment`, copying prior pose/covariance, timestamps, and resetting collector state;
2. measurement-model read-only copy immediately after all `h_x` and `h` rows are constructed, operating on the post-FOV-prune map;
3. scan-level finalization outside the update, with no estimator control signal.

The measurement-model copy must still complete before state correction for that callback, all post-update map insertion/downsample deletion, and the next scan's local-map deletion.

## 14. Timestamp and scan identity

- raw LiDAR timestamp enters through the callback message header.
- `MeasureGroup.lidar_beg_time` is copied from `time_buffer`.
- `MeasureGroup.lidar_end_time` is derived from the final point offset or running mean scan time.
- IMU propagation covers the previous scan tail through the current scan end.
- odometry and point publications use `lidar_end_time`.
- all `h_share_model` calls are synchronous children of one `update_iterated_dyn_share_modified` invocation for the active global `Measures`.

The callback-global `scan_count` is not attached to buffered scans and is not a reliable synchronized-scan identity. Day 3 may add a collector-only monotonic `scan_index` that increments once after a successful `sync_packages`, does not depend on measurement call count, does not affect estimation, and is not used as a random seed.

## 15. Draft Day 3 observation record

Every field below is `DRAFT_FOR_DAY3` and `NOT_IMPLEMENTED_DAY2`.

| Field | Draft type / meaning | Status |
|---|---|---|
| `sequence_id` | approved data-namespace sequence ID | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `scan_index` | collector-only monotonic synchronized-scan index | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `timestamp_begin` | `MeasureGroup.lidar_beg_time` | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `timestamp_end` | `MeasureGroup.lidar_end_time` | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `measurement_call_index` | collector-only attempted callback index | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `prior_position` | propagated `state_ikfom.pos` copy | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `prior_orientation` | propagated `state_ikfom.rot` copy | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `prior_pose_frame` | position world; rotation IMU/body-local tangent | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `prior_covariance_pose_block` | detector-order `6 x 6` copy | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `prior_covariance_frame` | mixed native tangent frame | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `prior_covariance_checksum` | SHA-256 of canonical serialized block | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `pose_jacobian_rows` | `H_native[:, [3,4,5,0,1,2]]` | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `point_to_plane_residuals` | formal innovation vector `h=-pd2` | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `measurement_variance_or_effective_weight` | variance vector filled with `0.001` | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `current_point_indices` | accepted native downsampled-point indices | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `correspondence_proxy_ids` | deterministic SHA-256 proxies | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `valid_correspondence_count` | `effct_feat_num` | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `formal_residual_checksum` | SHA-256 of canonical formal `h` bytes | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `formal_jacobian_checksum` | SHA-256 of canonical detector-row bytes | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `formal_correspondence_checksum` | SHA-256 over ordered proxy IDs | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `source_commit` | frozen FAST-LIO2 commit | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |
| `adapter_contract_version` | `fastlio2-degen-readonly-v1-draft` | DRAFT_FOR_DAY3; NOT_IMPLEMENTED_DAY2 |

## 16. Recommended Day 3 collection points

Use a split collector:

1. `src/laserMapping.cpp`, after `p_imu->Process` and prior-state access at lines 888–890, before `lasermap_fov_segment` at line 901:
   copy prior state/covariance and timestamps; reset scan-local collector state.
2. `src/laserMapping.cpp::h_share_model`, immediately after the row loop ending at line 751 and before return at line 754:
   if this is the first valid linearization, copy the already-constructed native J/r, constant variance, accepted source indices, native neighbors, and plane data.
3. outside `update_iterated_dyn_share_modified`:
   finalize or enqueue the collector-owned record without changing the filter result.

No collection step may trigger a new nearest-neighbor search, plane fit, residual computation, or Jacobian computation.

## 17. Absolutely forbidden writes

The Day 3 tap must not:

- change `x_`, `P_`, `dyn_share.valid`, `dyn_share.converge`, iteration limits, or call count;
- change `Nearest_Points`, `point_selected_surf`, `normvec`, `laserCloudOri`, `corr_normvect`, `effct_feat_num`, or formal `h_x/h`;
- insert, delete, rebuild, flatten, lock for mutation, or otherwise alter the IKD-tree;
- alter callback buffers, timestamps, scan acceptance, preprocessing, downsampling, publication, or random state;
- return any value that changes estimator control flow;
- duplicate an intermediate iteration as another scan;
- label posterior state/covariance as prior.

## 18. Unresolved issues

No source-semantic blocker remains for a read-only Day 3 implementation. Implementation work still requiring review includes canonical byte serialization, bounded collector buffering, and a regression test proving estimator output identity with the tap disabled/enabled. These are implementation obligations, not unresolved FAST-LIO2 data semantics.

## 19. Day 3 authorization conditions

Static authorization is granted only if all Day 2 gates remain true and Day 3 preserves:

- first valid linearization sampling;
- exact native row extraction and detector reorder;
- common variance `0.001`;
- propagated prior snapshot before LiDAR correction;
- one record maximum per synchronized scan;
- post-prune-map correspondence semantics;
- zero estimator/map/control-flow writes;
- unchanged FAST-LIO2 numerical outputs under regression comparison.

Day 2 conclusion: `DAY3_READONLY_TAP_AUTHORIZED=true`.

This authorizes only implementation and validation of a read-only tap. It does not authorize FAST-LIO2 scientific integration runs, rosbag replay, detector claims on real data, Stage 3, or a completed Degen-LIO claim.

## 20. Source maps and SHA-256 index

| Artifact | SHA-256 |
|---|---|
| `manifests/harmful_bias/fastlio2_source_map.csv` | `dbafa32d4fe34c3ac30c010520fe0617445175abeab6c16c0d3e4c98487a50b3` |
| `manifests/harmful_bias/fastlio2_state_layout.csv` | `808d19bf6c7bebeda106a7b90c7d03673138fbba203d2a6286ca249ac7200d9a` |
| `manifests/harmful_bias/fastlio2_mutation_boundary.csv` | `36b9e34ef7949cd2ddd36d281e42c929b2bd33db25abe8dcad655fb6352c3f9c` |
| `manifests/harmful_bias/detector_input_source_map.csv` | `f9dba2c28d24271f96f85723fa44b0b7dd78d2bf8fb260591e668fa264be4ddb` |
