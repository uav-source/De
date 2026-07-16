# Harmful-Bias Multihyp Research Spike — Day 3 Read-Only Tap Contract

## 1. Scope and frozen revisions

Day 3 implements only a default-off, bounded, in-memory observation tap that copies FAST-LIO2's existing formal first-valid LiDAR linearization. It does not change estimator decisions and does not produce operational output.

- FAST-LIO2 frozen commit: `7cc4175de6f8ba2edf34bab02a42195b141027e9`
- FAST-LIO2 baseline tag: `checkpoint/fastlio2-pre-readonly-tap-v1`
- FAST-LIO2 implementation branch: `spike/readonly-observation-tap-v1`
- Degen-LIO Day 2 commit: `57fd7591602fd1d4276bea7d19d4c475531b6173`
- Degen-LIO Day 2 checkpoint: `checkpoint/multihyp-d2-pass`
- adapter/schema version: `fastlio2-readonly-observation-v1`

The ROS parameter `harmful_bias/readonly_tap_enabled` defaults to `false`. With the default, no scan lifecycle is started and no correspondence sidecar storage is allocated.

## 2. Scan lifecycle

Each successfully synchronized LiDAR scan receives one monotonically increasing `scan_index`. The tap records:

- scan begin/end timestamps;
- whether the formal update was invoked;
- attempted and valid measurement-model call counts;
- downsampled and valid-correspondence counts;
- whether the first valid linearization was found and emitted;
- one closed-enum skip reason.

The closed skip-reason set is:

```text
NONE
FIRST_SCAN_INITIALIZATION
EMPTY_UNDISTORTED_SCAN
LOCAL_MAP_INITIALIZATION
DOWNSAMPLED_POINTS_TOO_FEW
FILTER_UPDATE_NOT_INVOKED
NO_VALID_LINEARIZATION
EXTRINSIC_ESTIMATION_ENABLED
NONFINITE_OBSERVATION
BUFFER_FULL
INTERNAL_LIFECYCLE_ERROR
```

No free-form machine skip reason is allowed.

## 3. Prior capture boundary

For an update-eligible synchronized scan, FAST-LIO2 first completes IMU propagation. The tap then copies `kf.get_x()` and the complete `23 x 23` `kf.get_P()` before current-scan local-map pruning and before any LiDAR correction.

The tap stores values, not references or filter pointers. The exported pose covariance is the native pose block reordered on both axes from native `[position 0:2, rotation 3:5]` to detector order:

```text
[delta_theta_x, delta_theta_y, delta_theta_z,
 delta_position_x, delta_position_y, delta_position_z]
```

`beginScan()` validates timestamps and ordering, finite position, a finite unit quaternion with tolerance `1e-6`, and every element of the complete native `23 x 23` covariance before activating the scan. An invalid prior emits an `INTERNAL_LIFECYCLE_ERROR` lifecycle record, leaves the collector inactive, and cannot produce an observation.

## 4. First-valid linearization

Every entry to the existing `h_share_model()` increments the current scan's attempted-call count. FAST-LIO2 alone decides `dyn_share.valid`.

- An invalid call emits no observation.
- The first valid call copies the completed formal observation.
- Later valid calls only increase the valid-call count.
- At most one observation record is retained per scan.
- A rejected first valid record is not replaced by a later iteration.

The tap does not independently decide correspondence validity.

`capturePending()` is true only while the tap is enabled, a validated scan is active, and no first-valid capture has been attempted. All tap-only sidecar resizing and copies of planes, accepted indices, residuals, neighbors, Jacobians, and checksum inputs are guarded by this state. After the first valid capture, later iterations retain only lightweight call counts and perform no observation-payload copy.

## 5. Jacobian and residual

The native formal Jacobian has 12 columns and is not modified. The detector view copies columns through the unique C++ constant:

```text
native [3, 4, 5, 0, 1, 2]
    -> detector [delta_theta_xyz, delta_position_xyz]
```

The record preserves both sign conventions:

- `signed_geometric_residual_pd2 = n_world^T p_world + d`
- `formal_filter_innovation_h = -signed_geometric_residual_pd2`

The required numerical check is:

```text
max_i abs(formal_filter_innovation_h[i]
          + signed_geometric_residual_pd2[i]) <= 1e-12
```

No residual or Jacobian is refitted or recomputed by the tap.

## 6. Measurement variance

FAST-LIO2 exclusively owns the formal variance through its baseline definition `#define LASER_POINT_COV (0.001)`. The tap defines no formal variance symbol or constant. `measurement_variance_scalar_m2` is copied from the formal FAST-LIO2 update call site through the `captureFirstValid()` argument and is never used to control the update.

```text
measurement_weight_representation = CONSTANT_SCALAR_VARIANCE
measurement_variance_scalar_m2 = 0.001
measurement_variance_applies_to_all_rows = true
```

This is a variance in square meters. There is no per-point variance, robust weight, or reinterpretation of the point-selection score.

## 7. Correspondence sidecars

When a formal effective point is compacted into its accepted row, the same serial branch stores its original downsampled source index. This preserves row order without coordinate reverse lookup.

For each accepted row, the tap copies:

- the original source index;
- the exact already-fitted normalized plane coefficients;
- the coordinates from the existing native nearest-neighbor container;
- a deterministic correspondence proxy ID.

It performs no nearest-neighbor query and no plane fit.

## 8. Correspondence proxy ID v1

The proxy is a logging identity only and never enters estimation. Its input is:

```text
scan_index
accepted_source_index
quantized neighbor coordinates sorted lexicographically by x, y, z
quantized normalized plane coefficients
```

Quantization constants are:

```text
neighbor_coordinate_quantization_m = 1e-5
plane_normal_quantization = 1e-8
plane_offset_quantization_m = 1e-5
```

The canonical byte stream uses explicit little-endian integers and `FNV-1a 64-bit`. It excludes memory addresses, thread IDs, method names, and native neighbor input order. Quantization and sorting affect only the proxy ID.

Before hashing, the proxy copy of `[n,d]` is sign-canonicalized: the first normal component with magnitude above `1e-12` is made positive, and `d` is flipped with the normal. Therefore `[n,d]` and `[-n,-d]` produce the same proxy ID. This never modifies the formal plane or residual.

## 9. Buffer and thread boundary

The observation and lifecycle queues are bounded in-memory deques. Default capacity is 4. An enabled tap rejects capacity below 1 or nonfinite/nonpositive quantization steps at startup. A disabled tap ignores unused tap-only parameter validity and preserves original FAST-LIO2 startup behavior.

When the observation queue is full:

- capture returns immediately;
- no existing record is overwritten;
- `drop_count` increments;
- lifecycle skip reason becomes `BUFFER_FULL`.

The tap starts no background thread, performs no wait, performs no disk I/O, changes no OpenMP setting, and exposes records only by copy.

## 10. Extrinsic-estimation gate

The tap may be enabled only when `mapping/extrinsic_est_en=false`.

- Tap disabled: either extrinsic setting preserves original startup behavior.
- Tap enabled and extrinsic estimation disabled: capture is allowed.
- Tap enabled and extrinsic estimation enabled: startup returns an explicit error before normal processing.

The adapter never changes the estimator's extrinsic setting and never silently discards extrinsic Jacobian columns.

## 11. Integrity checks

Observation checksums use:

```text
FNV1A64_EXACT_BYTES_V1
```

Checksums cover the formal native Jacobian, detector Jacobian, formal innovation, geometric residual, accepted indices, proxy IDs, and detector-order prior covariance. The algorithm name is part of every observation record.

## 12. Read-only guarantees

The tap accepts formal inputs as const data and copies them. It does not:

- update state, covariance, Kalman gain, map, or filter configuration;
- add/delete map points;
- change correspondence acceptance, point order, formal weight, iteration count, or thread configuration;
- query the map or fit a plane;
- write CSV, JSON, ROS messages, or any other runtime output.

Day 3 adds no ROS topic, publisher, subscriber, launch file, or data-run configuration.

## 13. Explicitly not implemented

Day 3 does not implement a CSV/ROS logger, a consumer, the detector call, ODI computation, weak-direction computation, multi-hypothesis logic, IMU-conflict logic, or deferred evaluation. No rosbag, real-data run, quick run, development run, or scientific experiment is part of this contract.

The three Day 3 JSON artifacts are synthetic structure examples only. They are not runtime evidence and support no scientific claim.

## 14. Day 4 input boundary

If the Day 3 gate passes, Day 4 may consume only copied `ReadonlyObservationRecord` values through a separate adapter boundary. A consumer must not receive mutable FAST-LIO2 state, covariance, map, filter, or correspondence objects and must not send control signals back to FAST-LIO2.

## 15. Known limitations

- No stable native FAST-LIO2 patch ID exists; the proxy is only deterministic under the documented quantization contract.
- No runtime serializer or consumer exists.
- The bounded buffer has no production drain path in Day 3.
- OFF/ON rosbag numerical equivalence is not tested on Day 3 and remains `NOT_RUN_DAY3`.
- Synthetic validation checks representation and invariants only; it does not validate live timing or real-data behavior.
