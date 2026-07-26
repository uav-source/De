# Day 6 Experiment A Input and Map Stage Hash Contract

Experiment A is an internal engineering divergence-stage diagnostic. It is not
a scientific causality result, detector-effectiveness result, Day 7 result, or
authorization to integrate a robust FAST-LIO2 update.

The only live executions are two sequential Quick Shack replays:

- `multihyp_day6_experiment_a_hash_r1`
- `multihyp_day6_experiment_a_hash_r2`

Both use the immutable clip SHA-256
`272325265978787c838e010b1f0da963a15fb4b08ff8730fc3dd9901e32a0e20`.
The diagnostic window is scan 135 through 160 inclusive. No third replay is
authorized.

## Canonical checksums

All hashes use `FNV1A64_EXACT_BYTES_V1` through the existing
`ExactBytesChecksum` byte semantics. Integers have explicit widths and
little-endian byte order. Floating-point inputs are hashed as their raw IEEE
bit patterns without rounding, quantization, clipping, `-0` normalization, or
NaN replacement. Every ordered payload digest carries its element count, byte
count, nonfinite count, and checksum.

Equal values mean only `MATCHED_BY_CANONICAL_CHECKSUM`. FNV-1a is finite and
collisions are possible; equality is not a collision-free mathematical proof.

### Raw Livox payload

The callback-side digest includes header seconds/nanoseconds, frame-id length
and bytes, `timebase`, `point_num`, `lidar_id`, point-vector length, then every
point in original message order as `offset_time`, raw float `x/y/z`,
`reflectivity`, `tag`, and `line`.

### IMU bundle

The digest covers exactly the ordered `MeasureGroup.imu` messages consumed by
the scan. Each message includes header stamp/frame, orientation and covariance,
angular velocity and covariance, and linear acceleration and covariance.

### Undistorted cloud

After the unchanged IMU `Process` call and before measurement construction,
each point is hashed in current order as raw float `x/y/z`, intensity,
`normal_x/y/z`, and curvature.

### Map content and traversal

The in-memory read-only map snapshot contains only valid traversal points and
is never written. A point hash covers raw float `x/y/z` and intensity; unused
point fields are explicit zeroes in the canonical eight-float point record.

`MapContentDigestV1` combines point count, XOR, unsigned sum modulo 2^64,
unsigned sum of each point hash rotated by its own low six bits, minimum hash,
and maximum hash. These commutative aggregates are folded into the content
checksum, so traversal order does not affect it.

`MapTraversalDigestV1` folds the point count and point hashes in the exact
read-only traversal order. BBox, valid count, nonfinite count, and snapshot
runtime are recorded separately.

### Insertion batches

The two existing `Add_Points` input batches are read immediately before their
unchanged calls. Ordered and multiset digests are recorded per batch and for
the combined two-batch sequence. Diagnostics neither sort nor modify the
formal vectors.

## Reused formal evidence

The first valid `h_share_model` call reuses current checksum helpers and formal
objects for prior state/covariance, accepted indices, correspondence, native
Jacobian, detector-column Jacobian, innovation, signed residual, posterior
state/covariance, and correspondence count. It performs no new nearest search,
plane fit, or correspondence construction.

## Collector boundary

`ExperimentAStageHashAudit` is disabled by default, has no thread, topic, RNG,
or realtime file output, retains at most 26 compact records, and returns them
without clearing through `/harmful_bias/experiment_a_stage_hash_status`
(`std_srvs/Trigger`). State, covariance, valid map count, and formal buffer
sizes are compared around each diagnostic operation. A nonzero diagnostic
mutation or internal-error count is an evidence gap.

The restricted classification vocabulary is:

- `INPUT_STAGE_DIVERGED`
- `UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED`
- `MAP_STATE_ALREADY_DIVERGED`
- `MAP_STORAGE_ORDER_DIFFERED_WITH_MATCHED_CONTENT`
- `CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_MATCHED_INPUT_AND_MAP_CONTENT`
- `FILTER_UPDATE_STAGE_DIVERGED`
- `MAP_INSERTION_STAGE_DIVERGED`
- `NO_DIVERGENCE_IN_DIAGNOSTIC_PAIR`
- `EVIDENCE_GAP`

`DAY7_AUTHORIZED`, `EXPERIMENT_B_AUTHORIZED`,
`EXPERIMENT_C_AUTHORIZED`, `STAGE3_START_AUTHORIZED`, and
`FAST_LIO2_INTEGRATION_AUTHORIZED` remain false regardless of classification.
