# Day 7 Map-Update Root-Cause Diagnostic Contract

Status: `DAY7_CONTRACT_LOCK_CANDIDATE=true`

## Scope and authorization lineage

Day 7 is an internal engineering diagnostic of map mutation, rebuild logging,
and ikd-tree state only. The source Day 6 package retains its internal Gate
status `FAIL`. Day 7 proceeds only through the independent
`day7_authorization_amendment_v1` adjudication:

- `SOURCE_DAY6_INTERNAL_GATE_STATUS=FAIL`
- `DAY7_EXTERNAL_ADJUDICATION_APPLIED=true`
- `DAY7_EXTERNAL_ADJUDICATION_REASON=OVER_CONSTRAINED_SAME_SCAN_EQUALITY_RULE_FOR_MAP_INSERTION_STAGE`
- `DAY7_AUTHORIZED=true`
- `STAGE3_START_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`

The adjudication changes no scientific payload or runtime evidence. It permits
a coherent `map_content_after` divergence to precede the later observation
effect.

## Fixed execution

- Sequence: `avia_quick_shack`
- Scan window: 150 through 170 inclusive
- Runs: exactly four, sequentially
- ROS master ports: 20411, 20412, 20413, 20414
- FAST CPU: 22
- rosbag CPU: 23
- Playback rate: 0.25
- Maximum diagnostic events per run: 131072
- Maximum rebuild commit records per run: 4096

No fifth replay is authorized. The detector, ODI, AIS, weak-direction
analysis, GT, Development, Holdout, and Future Test remain outside scope.

## Read-only instrumentation boundary

The instrumentation may read existing candidate points, formal voxel box
bounds, the existing `Downsample_Storage`, selected representative, existing
logger operation, rebuild generation, and the point vector already copied by
`CoherentMapSnapshotV2`. It may append only to pre-reserved diagnostic
buffers.

It must not perform another nearest/range search, access the map a second time
for a call-level digest, change a formal container, change Add/Delete
conditions, alter logger order, alter rebuild selection/commit, or extend a
formal lock scope. Call-level `map_content_before` and `map_content_after` are
therefore explicitly marked `NOT_CAPTURED_NO_SECOND_MAP_ACCESS`; the
scan-level coherent before/after snapshots are the authoritative content
evidence.

`INSTRUMENTATION_TIMING_PERTURBATION_PRESENT=true`: hashing, bounded buffer
writes, and diagnostic atomics can slightly perturb scheduling. Any observed
timing association is not evidence by itself of a data race or of behavior in
the uninstrumented binary.

## Identity and trace schemas

`MapPointIdentityV1` is SHA-256 over the big-endian IEEE-754 bytes of:
`x`, `y`, `z`, `intensity`, `normal_x`, `normal_y`, `normal_z`, and
`curvature`. A theoretical SHA-256 collision remains possible. The point
trace stores hashes, never recoverable point coordinates.

`VoxelIdentityV1` serializes the six exact float bit patterns from the formal
voxel box bounds already computed by `KD_TREE::Add_Points`. No parallel voxel
formula is allowed.

Ordered and multiset batch/context summaries use
`FNV1A64_EXACT_BYTES_V1`. Mutation and logger binaries have a fixed header,
record count, trailer, and file SHA-256. Map point identity records contain a
canonical-sorted SHA-256 list and per-record checksum.

## Fail-closed conditions

The trace fails if any event is unclassified, any checksum or schema fails,
any buffer overflows, any required scan snapshot is missing/incoherent, any
call count delta does not close, or any map-after symmetric-difference point
cannot be linked to a mutation/logger/rebuild record.

`SAME_EVENT_TRACE_DIFFERENT_MAP_AFTER` is an evidence gap, not a localized
root cause. Logger timing alone never sets `DATA_RACE_PROVEN=true`.
`FORMAL_IKDTREE_BUG_PROVEN` also remains false unless evidence establishes an
actual formal algorithm violation.

## Conclusion boundary

Day 7 may report a first divergent mutation event and one or more bounded
root-cause classifications. It is not a detector-effectiveness result,
scientific causal proof, Stage 3 result, robust FAST-LIO2 result, or public
disclosure authorization.

`DAY8_AUTHORIZED=false` is invariant. A Day 8 recommendation, if earned, still
requires a later GPT audit and explicit authorization.
