# Day 5 startup-sync V5 execution report

## Outcome

The final strict cross-process replay remediation failed during
`avia_quick_shack/AUDIT_ONLY_R1`. The supervisor stopped immediately; Quick R2,
Quick R3, all pairwise comparisons, and all Outdoor runs were not executed.

`FAILURE_CLASSIFICATION=TAIL_CLOCK_DUPLICATE_TIME`

The final tail-clock state recorded `clock_duplicate_count=226`, so the fixed
zero-duplicate handoff gate failed. The original runner emitted the raw
classification `NONE` with the message `tail-clock stop/handoff did not pass`
because the node's `failure_reason` remained `NONE`; that raw evidence is
preserved. `post_run_failure_adjudication.json` deterministically maps
`handoff_pass=false` plus a positive duplicate count to the required fixed
enum. No code was changed and no replay was rerun after this failure.

Therefore:

- `STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS=ABANDONED_AFTER_V5`
- `STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED=false`
- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`
- no V6 may be created

## What V5 did establish in Quick R1

- rosbag exited naturally after the paused-start LiDAR/IMU handshake passed.
- Tail-clock start succeeded with no publisher overlap.
- `last_bag_clock_ns=1600270417569223231`.
- `tail_first_clock_ns=1600270417570223231`, exactly 1,000,000 ns later.
- Tail publication produced 10,383 values; backward count was zero.
- The wall-bounded drain made no service-call timeout.
- All 491 LiDAR and 9,953 IMU callbacks arrived with exact final stamps.
- Drain passed after 20 stable polls.
- FAST main-loop heartbeat increased from 39,589 to 57,473.
- The final processed MeasureGroup count was 490, with one unprocessed LiDAR
  tail and 20 remaining IMU messages.
- `/laserMapping` and roslaunch exited normally; tail stop returned success.

These facts do not override the duplicate-clock hard failure and do not prove
repeatability.

## Verification and immutability

- Degen targeted tests passed 96/96.
- The complete Degen suite passed 863/863 after temporarily linking three
  archived historical Day11/12 checksum manifests; all links were removed.
- Independent real ROS fixtures passed for tail-clock handoff and three
  consecutive two-second drain service timeouts.
- FAST-LIO2 was not modified, rebuilt, or tested in V5.
- FAST diff SHA, source-lock SHA, frozen-file hashes, and binary SHA matched
  before and after formal replay.
- The endpoint contract and both clip hashes remained fixed.

## Gates and claim boundary

- `TAIL_CLOCK_HANDOFF_PASS=false`
- `TAIL_CLOCK_NO_OVERLAP_PASS=false` because the required six-run matrix was
  incomplete, although the executed run observed zero overlap
- `TAIL_CLOCK_MONOTONIC_PASS=false`
- `DRAIN_SERVICE_WALL_TIMEOUT_PASS=false` as a six-run gate, although the
  executed drain had zero service timeout
- `END_OF_STREAM_DRAIN_PASS=false` as a six-run gate, although R1 drain passed
- `QUICK_BASELINE_REPEATABILITY_PASS=false`
- `OUTDOOR_BASELINE_REPEATABILITY_PASS=false`
- `BASELINE_REPEATABILITY_PASS=false`
- `DAY5_STARTUP_SYNC_V5_PASS=false`
- `DAY5_CAPTURE_EXPORT_REMEDIATION_AUTHORIZED=false`
- `DAY5_RUNTIME_EQUIVALENCE_PASS=false`
- `OFF_ON_REPLAY_EQUIVALENCE_STATUS=NOT_REEVALUATED_STARTUP_SYNC_ONLY`
- `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`

Only `AUDIT_ONLY` was run. Tap OFF/ON equivalence, detector execution, ODI/AIS,
Development, Holdout, Future Test, and harmful-bias detectability were not
evaluated. The recommended fallback evidence route is in-call immutability,
frozen observation records, offline production-detector determinism, and
functional/statistical tolerance for real replay.

Stage 2 remains FAIL/PIVOT, Stage 3 and FAST-LIO2 integration remain
unauthorized, and formal Degen-LIO remains incomplete.
