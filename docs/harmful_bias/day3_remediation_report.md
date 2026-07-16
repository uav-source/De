# Harmful-Bias Multihyp Research Spike — Day 3 Remediation Report

## 1. Scope and outcome

This remediation fixes the three blocking findings in the original Day 3 read-only tap and adds two low-risk hardening changes. Both repository HEADs remain on their frozen commits and all remediation changes remain uncommitted.

```text
DAY3_REMEDIATION_PASS=true
DAY3_READONLY_TAP_IMPLEMENTATION_PASS=true
DAY4_DETECTOR_INTEGRATION_AUTHORIZED=true
OFF_ON_REPLAY_EQUIVALENCE_STATUS=NOT_RUN_DAY3
```

Day 4 authorization means only that an offline or side-path detector adapter may consume copied observation records. It does not authorize Stage 3, formal FAST-LIO2 integration, estimator modification, or a complete Degen-LIO system.

## 2. Blocking issue 1: formal variance ownership

The first Day 3 implementation replaced FAST-LIO2's baseline macro with a function defined by the tap. Although the numerical value remained unchanged, this reversed the dependency boundary: the formal update depended on an observational adapter for its measurement variance.

The remediation restores the baseline expression exactly:

```cpp
#define LASER_POINT_COV (0.001)
```

`formalLaserPointVariance()` and `kFormalLaserPointVarianceM2` were removed from tap production code. The unchanged formal update continues to use `LASER_POINT_COV`; the observation hook passes `static_cast<double>(LASER_POINT_COV)` into `captureFirstValid()`. The tap only copies this caller-owned value.

The `FormalVarianceIsCopiedFromCaller` test passes both `0.001` and `0.0025` and verifies exact record values. Static audit confirms zero formal-variance symbols and zero `0.001` literals in the tap production files.

## 3. Blocking issue 2: post-capture payload copying

The first implementation guarded sidecars with `scanActive()`. A scan remains active throughout all filter iterations, so later iterations continued resizing and copying accepted indices, planes, residuals, neighbors, and temporary observation payload even though the first record could no longer be replaced. This unnecessary work could affect real-time latency.

The new read-only query is:

```text
capturePending = enabled && scan_active && !first_valid_captured
```

Every tap-only sidecar allocation and payload copy in `h_share_model()` is guarded by a snapshot of `capturePending()`. After the first valid capture, later valid iterations call only the lightweight counters. Formal FAST-LIO2 arrays and calculations remain outside the guard and therefore unchanged.

Tests verify that `capturePending()` remains true after an invalid call, becomes false after the first valid capture, later call counts continue, only one observation exists, and deliberately different second-call J/residual/index values cannot replace the first record.

## 4. Blocking issue 3: invalid-prior lifecycle

The first `beginScan()` set `scan_active_ = true` before validating inputs. A failed validation therefore left a partially initialized scan able to receive measurement calls.

The remediation validates before activation:

- finite begin/end timestamps and nondecreasing order;
- finite three-component position;
- finite, nonzero unit quaternion with tolerance `1e-6` and no automatic normalization;
- exact `23 x 23` native covariance shape;
- every native covariance element finite, including entries outside the extracted pose block;
- no second `beginScan()` while another scan is active.

An invalid prior emits one lifecycle record with `INTERNAL_LIFECYCLE_ERROR`, `record_emitted=false`, and `first_valid_linearization_found=false`. It leaves `scanActive()` and `capturePending()` false, and subsequent calls cannot create an observation.

## 5. Configuration validation

When enabled, the tap now rejects:

- buffer capacity below 1;
- zero, negative, or nonfinite neighbor-coordinate quantization;
- zero, negative, or nonfinite plane-normal quantization;
- zero, negative, or nonfinite plane-offset quantization;
- enabled tap with extrinsic estimation active.

Disabled mode ignores unused tap-only parameter validity and preserves the original FAST-LIO2 startup path. The ROS call site no longer clamps an invalid capacity to 1 before validation.

## 6. Plane proxy sign canonicalization

Only the proxy-hash copy of `[n,d]` is canonicalized. The first normal component with magnitude above `1e-12` is made positive and `d` is flipped with the normal. Thus `[n,d]` and `[-n,-d]` produce the same ID. A near-zero normal is rejected as an invalid observation. Formal planes, correspondences, and residuals are never modified.

## 7. Files changed

FAST-LIO2 remains limited to:

- `include/readonly_observation_tap.hpp`;
- `src/readonly_observation_tap.cpp`;
- `test/test_readonly_observation_tap.cpp`;
- `src/laserMapping.cpp`;
- `CMakeLists.txt`.

Degen-LIO remediation changes are limited to the Day 3 contract/report/manifest, `tests/test_readonly_observation_contract.py`, this report, and the remediation manifest. The schema and synthetic record shape did not change.

## 8. Tests and audits

FAST-LIO2:

- RelWithDebInfo build: pass;
- gtest cases: 34 passed, 0 failures, 0 errors;
- direct gtest repeat 1: 34 passed;
- direct gtest repeat 2: 34 passed.

Twenty-one behavior cases were added over the original 13, covering variance ownership, capture suppression, invalid priors, complete covariance validation, timestamps, quaternion norm, configuration rejection, and plane-sign invariance.

Degen-LIO:

- targeted schema/contract tests: 41 passed;
- full pytest: 631 passed, 1 pre-existing deprecation warning.

Static audit confirms:

- baseline and current `LASER_POINT_COV` are both `(0.001)`;
- tap formal-variance symbol count is 0;
- tap production `0.001` count is 0;
- new forbidden formal-operation calls are 0;
- unguarded tap payload-copy operations are 0;
- prohibited estimator/thread/random/I/O dependencies are 0.

The package-level isolated restoration also passes 41/41 Degen-LIO targeted
tests, a clean FAST-LIO2 RelWithDebInfo build, and 34/34 FAST-LIO2 gtests. The
isolated Degen-LIO full-suite status is intentionally recorded as false with
reason `HISTORICAL_IGNORED_EVIDENCE_NOT_PACKED`: historical ignored-results
checksums are evidence rather than source and are not injected into the
restoration HOME. This does not replace or weaken the original-workspace
631/631 full-suite gate.

The exact FAST-LIO2 baseline Git bundle was generated and verified at
`7cc4175de6f8ba2edf34bab02a42195b141027e9`, but is 132,869,709 bytes and cannot
fit inside the complete 100 MiB audit-package limit. The package therefore
contains a hash-pinned build-source snapshot from that fixed HEAD, plus pinned
ikd-Tree and livox_ros_driver snapshots. The omission and replacement hashes
are recorded explicitly in the remediation manifest and evidence.

## 9. Actions not performed

Today did not run roscore, roslaunch, rosbag, a FAST-LIO2 node, quick/development/holdout/future evaluation, or any scientific experiment. It did not call the detector or compute ODI, AIS, weak direction, or eigengap. It did not implement multi-hypothesis logic, IMU conflict, future-frame validation, a CSV logger, disk writer, or ROS topic.

No formal state, covariance, gain, map, correspondence, measurement weight, model equation, iteration count, or thread setting was modified. No Day 3 commit was created and nothing was pushed.

## 10. Scientific and integration state

```text
STAGE2_GATE=FAIL
TRANSITION=PIVOT
COHERENT_BIAS_HARMFUL_MECHANISM_SUPPORTED=true
COHERENT_BIAS_STABLY_ONLINE_DETECTABLE=false
STAGE3_START_AUTHORIZED=false
STAGE4_START_AUTHORIZED=false
PATENT2_AUTHORIZED=false
FAST_LIO2_INTEGRATION_AUTHORIZED=false
RISK_WARNING_AUTHORIZED=false
PUBLIC_DISCLOSURE_AUTHORIZED=false
```

Day 3 now provides a remediated read-only tap only. OFF/ON rosbag equivalence remains untested, no detector is connected, and formal Degen-LIO remains incomplete.
