# Day 5 startup-sync V5 contract

## Scope

V5 is the final authorized remediation of the strict cross-process replay
route. It runs only the existing FAST-LIO2 `AUDIT_ONLY` baseline on the two
frozen Day 5 clips. It does not run `CAPTURE_ONLY`, `COMPACT_EXPORT`, the
production detector, ODI/AIS, weak-direction analysis, Development, Holdout,
Future Test, or any scientific harmful-bias evaluation. It does not compare
tap OFF with tap ON and cannot authorize Day 6.

FAST-LIO2 is immutable in V5. The existing binary is reused without running
`catkin_make` or FAST tests. The comparator, detector, detector configuration,
runtime schemas, observation tap, binary writers, estimator, callbacks, and
map logic are frozen.

## Frozen inputs

The endpoint contract is read directly from the two frozen replay clips and
must remain byte-identical to the V4 contract:

- endpoint contract SHA-256:
  `fc431cb591474a04f5c7c090e3ce687a76183946201991da2a12f156c5ed9b18`
- `avia_quick_shack`: clip SHA-256
  `272325265978787c838e010b1f0da963a15fb4b08ff8730fc3dd9901e32a0e20`,
  491 LiDAR and 9,953 IMU messages
- `avia_outdoor_run_100hz`: clip SHA-256
  `087c552c9c62be37b42d218323383459df8791ce6514fa7b3425f7bab5021284`,
  6,386 LiDAR and 12,914 IMU messages

Historical runtime scan counts are evidence only and are not endpoint
expectations.

## Deterministic tail-clock handoff

The independent ROS node `/day5_tail_clock` starts before rosbag and initially
only subscribes to `/clock`. It does not create a `/clock` publisher during
bag playback. After rosbag exits naturally, `/day5_bag_player` disappears, and
the ROS master reports zero `/clock` publishers, the runner calls
`/day5_tail_clock/start`.

The node then creates its publisher, verifies that `/laserMapping` is still a
`/clock` subscriber, and publishes:

`tail_start_clock_ns + published_index * 1_000_000`

The first value must equal the last bag clock plus 1,000,000 ns. Publication is
scheduled from `time.monotonic_ns()` at 500 Hz, with a 90-second wall limit and
a 45-second simulated-time advance limit. No received self-clock is used to
derive a later clock. Duplicate, backward, or overlapping publishers fail the
handoff.

The node exposes only these `std_srvs/Trigger` services:

- `/day5_tail_clock/start`
- `/day5_tail_clock/stop`
- `/day5_tail_clock/status`

It does not subscribe to LiDAR, IMU, pose, map, ground truth, estimator state,
or detector outputs. The runner keeps the tail clock active through drain and
normal `/laserMapping` shutdown, then calls stop and requires the publisher
thread to join and the node to exit.

## Wall-time bounded drain

Every `/harmful_bias/end_of_stream_status` call is made by a short-lived
`rosservice call` subprocess with an independent 2.0-second wall timeout.
Three consecutive service timeouts immediately produce
`DRAIN_SERVICE_CALL_TIMEOUT`. The total drain timeout remains 60 seconds.

Each poll records start/end monotonic timestamps, duration, return code,
Trigger success, parse status, timeout status, exception text, and consecutive
timeout count. A valid drain still requires exact callback counts and final
header stamps, no processable MeasureGroup, equal LiDAR/time buffer sizes, 20
stable polls at 0.1 seconds, and a strictly increasing FAST main-loop
heartbeat.

## Fixed execution and strict comparison

The fixed run-id is `multihyp_day5_startup_sync_v5`. Quick R1/R2/R3 execute
first and are compared immediately; Outdoor is prohibited if Quick fails.
Single-run wall limits are 450 seconds for Quick and 510 seconds for Outdoor.
The detached supervisor writes a five-second heartbeat and stops on a missing
or stale child heartbeat.

For each sequence, R1/R2, R1/R3, and R2/R3 must have identical scan pairing,
timestamps, checksums, accepted indices, correspondences, posterior values,
map sizes, and final-map digest. Position, rotation, and covariance differences
must each be at most `1e-12`. Tail step, last bag clock, first tail clock,
processed MeasureGroup endpoint, unprocessed LiDAR tail, and remaining IMU
count must also repeat exactly.

## Final stop-loss

After formal V5 replay starts, any hard-gate failure fixes:

- `STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS=ABANDONED_AFTER_V5`
- `STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED=false`
- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`

No V6 may be created. The only recommended fallback evidence route is
`IN_CALL_IMMUTABILITY + FROZEN_OBSERVATION_RECORD +
OFFLINE_PRODUCTION_DETECTOR_DETERMINISM +
REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE`.

The scientific state remains `STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`, with
Stage 3, FAST-LIO2 integration, patent, warning, and public disclosure
unauthorized. Formal Degen-LIO remains incomplete.

