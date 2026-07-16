# Harmful-Bias Multihyp Research Spike — Day 3 Read-Only Tap Report

## 1. Outcome

Day 3 implemented a default-off, read-only FAST-LIO2 observation tap on branch `spike/readonly-observation-tap-v1` while keeping both repository HEADs at their frozen commits.

The tap copies the propagated prior and the first formal valid point-to-plane linearization into bounded in-memory records. It does not run a consumer, write runtime records, publish a ROS topic, call the detector, or modify estimator outputs.

```text
DAY3_READONLY_TAP_IMPLEMENTATION_PASS=true
DAY4_DETECTOR_INTEGRATION_AUTHORIZED=true
OFF_ON_REPLAY_EQUIVALENCE_STATUS=NOT_RUN_DAY3
```

This authorization is limited to the next read-only research-adapter step. Formal FAST-LIO2 integration remains unauthorized.

## 2. Revisions

- Degen-LIO branch: `spike/harmful-bias-multihyp-dev`
- Degen-LIO Day 2 commit/current HEAD: `57fd7591602fd1d4276bea7d19d4c475531b6173`
- Degen-LIO Day 2 checkpoint: `checkpoint/multihyp-d2-pass`
- FAST-LIO2 starting branch: `main`
- FAST-LIO2 baseline/current commit: `7cc4175de6f8ba2edf34bab02a42195b141027e9`
- FAST-LIO2 baseline tag: `checkpoint/fastlio2-pre-readonly-tap-v1`
- FAST-LIO2 tap branch: `spike/readonly-observation-tap-v1`
- ikd-Tree commit: `e2e3f4e9d3b95a9e66b1ba83dc98d4a05ed8a3c4`
- livox_ros_driver workspace dependency commit: `3d240d5666129e1a3052e78ee8487a04b08fdda3`

No Day 3 commit was created and nothing was pushed.

## 3. FAST-LIO2 implementation

The implementation is split between:

- `include/readonly_observation_tap.hpp`: records, configuration, closed enums, constants, and read-only API;
- `src/readonly_observation_tap.cpp`: bounded queues, copying, validation, checksums, covariance/Jacobian projection, and proxy IDs;
- `src/laserMapping.cpp`: minimal lifecycle and formal-observation copy hooks;
- `test/test_readonly_observation_tap.cpp`: focused unit tests;
- `CMakeLists.txt`: tap library and catkin gtest target.

The tap defaults to disabled with capacity 4. It has no background thread and no disk or ROS output path.

The prior is copied immediately after `p_imu->Process()` and `kf.get_x()/get_P()`, before `lasermap_fov_segment()` and before the formal LiDAR update.

Inside `h_share_model()`, the existing code still performs correspondence search, plane fitting, acceptance, compaction, Jacobian construction, and innovation construction. The tap only copies:

- native `h_x` and `h`;
- signed `pd2` from the already accepted formal rows;
- original accepted source indices saved in the existing serial compaction branch;
- exact already fitted plane coefficients;
- the existing nearest-neighbor vectors.

The tap does not issue another nearest-neighbor query, fit another plane, or recompute J/residual values.

The remediation restores formal variance ownership to FAST-LIO2's baseline `#define LASER_POINT_COV (0.001)`. The tap no longer defines `formalLaserPointVariance()` or a production variance constant; it only copies the value passed from the formal call site.

All tap-only sidecar and payload construction is now guarded by `capturePending()`. Once the first valid capture is attempted, later iterations only update call counters. Invalid priors are fully validated before activation and emit `INTERNAL_LIFECYCLE_ERROR` without permitting observation capture.

## 4. Data contract

The JSON schema and Python validator define:

- one scan lifecycle record;
- one first-valid observation record;
- explicit frames, units, dimensions, enums, and versions;
- `23 x 23` native covariance provenance and `6 x 6` detector-order covariance;
- native Jacobian columns 0–11 and detector mapping `[3,4,5,0,1,2]`;
- `formal_filter_innovation_h = -signed_geometric_residual_pd2`;
- one positive scalar formal measurement variance for all rows;
- accepted source indices, native neighbors, planes, and deterministic proxy IDs;
- named `FNV1A64_EXACT_BYTES_V1` checksums.

The schema contains none of the prohibited scientific or deferred-evaluation fields. The Python validator recursively rejects them and does not call detector logic.

## 5. Correspondence proxy

Proxy ID v1 uses FNV-1a 64-bit over explicit little-endian values:

```text
scan index
accepted source index
lexicographically sorted quantized neighbor coordinates
quantized plane coefficients
```

Quantization is `1e-5 m` for neighbor coordinates, `1e-8` for plane normals, and `1e-5 m` for plane offset. The proxy copy of the plane is sign-canonicalized, so `[n,d]` and `[-n,-d]` hash identically. Unit tests confirm sign invariance, repeatability, neighbor-order invariance, and changes under scan, source-index, or above-step plane changes.

## 6. Guard and buffer behavior

Enabling the tap while `mapping/extrinsic_est_en=true` fails adapter startup with an explicit error and does not alter the estimator configuration. When the tap is disabled, extrinsic estimation preserves original startup behavior.

An enabled tap also rejects capacity below 1 and nonfinite or nonpositive quantization values. Disabled mode ignores these unused tap-only values.

The observation queue is bounded and non-overwriting. A full queue increments `drop_count`, returns immediately, retains the older record, and records `BUFFER_FULL` in the scan lifecycle.

## 7. Verification

FAST-LIO2:

```text
catkin_make -DCMAKE_BUILD_TYPE=RelWithDebInfo
catkin_make run_tests_fast_lio
catkin_test_results --verbose
```

Results:

- build: pass;
- gtest: 34 test cases passed;
- catkin result: 0 errors, 0 failures, 0 skipped.

The CMake change preserves Debug as the default only when no build type is supplied, so the required RelWithDebInfo command is no longer overwritten. The test target uses its build-tree RPATH to avoid an unrelated `/usr/local/lib` GTest ABI collision present in this environment.

The external restore package also carries source snapshots for the pinned ikd-Tree submodule and the clean livox_ros_driver workspace dependency, because neither is contained in the FAST-LIO2 baseline bundle.

The prior Day 3 package reconstruction passed its targeted Python tests and FAST-LIO2 build/tests. The remediation package records its own independent restore result separately. The external Degen full suite is not self-contained because it expects 172 MiB of Git-ignored historical Stage 2 results and additional historical checkpoint refs; these are not claimed as externally passed.

The exact FAST-LIO2 Git bundle was also generated and verified, but its size was 132,869,709 bytes because upstream history contains large documentation media. Since that one file exceeds the complete audit-package 100 MiB limit, it is not embedded. The upload package instead contains `FAST-LIO-readonly-tap-D3-build-source.tar.gz`, an exact export of all build-required paths at commit `7cc4175...`, plus the pinned dependency snapshots. The omission, original bundle SHA-256, size, and replacement semantics are recorded in the audit evidence.

Degen-LIO:

```text
python3 -m pytest -q \
  tests/test_readonly_observation_schema.py \
  tests/test_readonly_observation_contract.py
```

Result after remediation: `41 passed`.

```text
python3 -m pytest -q
```

Result after remediation: `631 passed, 1 warning`.

The warning is the pre-existing deprecation warning in `test_huber_normal_equation.py`.

Static read-only audit:

- newly added forbidden formal-operation calls: 0;
- forbidden tap ownership/thread/random/deferred-data tokens: 0;
- `STATIC_READONLY_AUDIT_PASS=true`.

## 8. Synthetic artifacts

The lifecycle and observation examples use only handcrafted values with `synthetic_only=true` and `N=3`. Both pass the JSON schema and Python validators.

They are representation tests only. They are not FAST-LIO2 runtime records, replay evidence, or scientific evidence.

## 9. Mutation and action audit

Confirmed false:

- state, covariance, gain, map, formal correspondence, formal weight, measurement iteration, and thread configuration modifications;
- roscore, roslaunch, rosbag, quick, development, holdout, deferred, or scientific runs;
- detector calls, ODI, weak direction, multi-hypothesis, IMU conflict, or deferred validation;
- CSV logger, runtime JSON writer, or ROS topic;
- Day 3 commit or push.

Both repositories remain within the exact Day 3 file allowlists.

## 10. Gate

```text
TAP_DEFAULT_OFF_CONFIRMED=true
EXTRINSIC_ESTIMATION_GUARD_PASS=true
PRIOR_CAPTURE_BEFORE_LIDAR_UPDATE_PASS=true
FIRST_VALID_ONLY_PASS=true
JACOBIAN_MAPPING_TEST_PASS=true
COVARIANCE_REORDER_TEST_PASS=true
RESIDUAL_SIGN_TEST_PASS=true
FORMAL_VARIANCE_SOURCE_PASS=true
ACCEPTED_SOURCE_INDEX_PASS=true
CORRESPONDENCE_PROXY_DETERMINISM_PASS=true
INPUT_IMMUTABILITY_PASS=true
BOUNDED_NONBLOCKING_BUFFER_PASS=true
NO_GT_SCHEMA_PASS=true
STATIC_READONLY_AUDIT_PASS=true
FASTLIO2_BUILD_PASS=true
FASTLIO2_UNIT_TEST_PASS=true
DEGEN_TARGETED_TEST_PASS=true
DEGEN_FULL_TEST_PASS=true
DAY3_DIFF_SCOPE_PASS=true
FORMAL_VARIANCE_READONLY_BOUNDARY_PASS=true
SUBSEQUENT_ITERATION_COPY_SUPPRESSION_PASS=true
INVALID_PRIOR_LIFECYCLE_PASS=true
TAP_CONFIGURATION_VALIDATION_PASS=true
PLANE_PROXY_SIGN_CANONICALIZATION_PASS=true
DAY3_REMEDIATION_PASS=true
DAY3_READONLY_TAP_IMPLEMENTATION_PASS=true
DAY4_DETECTOR_INTEGRATION_AUTHORIZED=true
```

The higher-level project state is unchanged:

```text
STAGE2_GATE=FAIL
TRANSITION=PIVOT
STAGE3_START_AUTHORIZED=false
FAST_LIO2_INTEGRATION_AUTHORIZED=false
```

Day 3 implements only the read-only tap. OFF/ON rosbag equivalence remains unverified, and the formal Degen-LIO system is not complete.
