# Day 5 Startup-Sync Remediation V3 Report

## Outcome

`DAY5_STARTUP_SYNC_V3_PASS=false`.

The fresh run ID `multihyp_day5_startup_sync_v3` was consumed. Five of six
planned AUDIT_ONLY replays started. Four completed under runner control with a
natural rosbag exit, normal `/laserMapping` shutdown, stable runtime products,
and a valid binary trailer. The controlling runner session was interrupted
after Outdoor R2 rosbag completion and before the runner-recorded shutdown and
product-validation phase. Outdoor R3 was not started and the run ID was not
resumed or reused.

The orphan Outdoor R2 ROS processes were subsequently closed with
`rosnode kill /laserMapping` and roscore SIGINT. No SIGTERM or SIGKILL was
used. This cleanup is not counted as a successful replay because it occurred
outside the locked runner lifecycle. The failure classification is
`RUNTIME_NODE_SHUTDOWN_INCOMPLETE`.

## Remediation evidence

The runtime-output source scan found 12 confirmed outputs: seven repository
`Log/PCD` paths and five mode-gated per-run products. It found zero unresolved
outputs and zero confirmed-but-unallowlisted outputs.

`Log/imu.txt` is now in the allowlist. Its source is
`src/IMU_Processing.hpp:376`, where `fout_imu` opens
`DEBUG_FILE_DIR("imu.txt")` for IMU initialization diagnostics.

All five started runs used absolute run, ROS_HOME, ROS_LOG_DIR, runtime-output,
clip, launch, and binary paths. The runtime-output ROS parameter matched the
resolved per-run directory five times and no duplicated run-root fragment was
observed. Because the sixth run was not executed, the full-matrix absolute-path
gate remains false.

The four runner-completed replays each produced all four required products.
Their four compact binaries passed header, record, checksum, trailer, count,
no-extra-bytes, and converter validation. The interrupted fifth binary was not
promoted to a validated replay product. The unexecuted sixth replay produced no
products.

Observed changed repository runtime outputs in completed runs were
`Log/dbg.txt`, `Log/imu.txt`, `Log/mat_out.txt`, `Log/mat_pre.txt`, and
`Log/pos_log.txt`. All are allowlisted; the observed unexpected count was zero.
The full-matrix allowlist gate remains false because post-run inventory was not
completed for the interrupted replay and the final replay was not executed.

## Partial repeatability evidence

Quick Shack completed three runner-controlled repeats. Their first
MeasureGroup checksum, timestamps, LiDAR point count, and IMU count were
identical. Their total runtime scan counts were `489`, `490`, and `489`.

Outdoor completed only one runner-controlled replay. No six-pair comparator was
run. Pairwise checksum, pose, covariance, linearization, map, and final-map
equivalence fields are therefore `NOT_EVALUATED`, not PASS.

## Tests and locks

The prescribed targeted suite passed with `88 passed`. The full suite initially
exposed the already-archived Day 11/12 checksum manifests; after temporarily
linking the three frozen manifests from the archive, it passed with
`792 passed, 1 warning`. The links were removed after the test.

The FAST-LIO2 checkpoint diff SHA before and after execution was
`3ad02ce3daed73110e828b4c9c73d532deec929a2c4ae34f35f628865e90f3fd`.
FAST-LIO2 source, binary, and frozen clips remained unchanged. FAST-LIO2 was not
rebuilt and its test suite was not run.

The isolated-HOME restore reconstructed the Degen checkout, FAST source plus
overlay, ikd-tree, and livox dependencies. Runtime-output scanning and the
absolute-path, shutdown, binary-trailer, and Gate fixtures passed. External
targeted and full pytest were not runnable because system Python has no pytest
outside the original user's `.local`, while this audit contract explicitly
forbids shipping wheels or a wheelhouse. Both pytest results are reported as
false rather than borrowing the original HOME.

## Scope and fixed state

This task executed AUDIT_ONLY only. It did not execute CAPTURE_ONLY,
COMPACT_EXPORT, a detector, ODI, Development, Holdout-Dev, Future Test, or
tap OFF/ON equivalence.

- `RUNTIME_OUTPUT_CONTRACT_PASS=true`
- `EXPECTED_RUNTIME_OUTPUT_ALLOWLIST_PASS=false`
- `RUNTIME_OUTPUT_ABSOLUTE_PATH_PASS=false`
- `RUNTIME_BINARY_COMPLETENESS_PASS=false`
- `STARTUP_INPUT_BOUNDARY_PASS=false`
- `BASELINE_REPEATABILITY_PASS=false`
- `DAY5_STARTUP_SYNC_V3_PASS=false`
- `DAY5_CAPTURE_EXPORT_REMEDIATION_AUTHORIZED=false`
- `DAY5_RUNTIME_EQUIVALENCE_PASS=false`
- `OFF_ON_REPLAY_EQUIVALENCE_STATUS=NOT_REEVALUATED_STARTUP_SYNC_ONLY`
- `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`
- `STAGE2_GATE=FAIL`
- `TRANSITION=PIVOT`
- `STAGE3_START_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`
- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY5_STARTUP_SYNC_V3`

This work does not evaluate harmful-bias detectability, does not authorize Day
6 even if the bounded engineering checks had passed, and does not complete
formal Degen-LIO.
