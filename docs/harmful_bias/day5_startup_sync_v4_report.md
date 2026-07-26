# Day 5 startup-sync V4 execution report

## Outcome

Day 5 startup-sync V4 failed at the first Quick drain gate.

`FAILURE_CLASSIFICATION=DRAIN_SERVICE_IMPLEMENTATION_INVALID`

The fixed run-id `multihyp_day5_startup_sync_v4` is consumed and must not be
resumed or reused. Outdoor was not run.

## Preconditions and implementation evidence

- The V3 audit SHA-256 matched
  `faa5e50de6ff726221935fde918cea0871ebcb4b599cbc4ce2e56d5e64013150`.
- The two frozen clip hashes matched.
- The endpoint contract was generated twice byte-for-byte identically. Its
  SHA-256 is
  `fc431cb591474a04f5c7c090e3ce687a76183946201991da2a12f156c5ed9b18`.
- Direct bag reads established 491/9,953 LiDAR/IMU messages for Quick and
  6,386/12,914 for Outdoor. The historical V3 output counts 489/490/489 were
  not used as expectations.
- Degen targeted tests passed 65/65; the complete suite passed 819/819 after
  temporarily linking the four archived historical Day11/12 checksum inputs.
  The links were removed immediately after the test.
- FAST-LIO2 built successfully and passed 132/132 tests.
- The production binary SHA-256 is
  `8e890dc353a20c0737588598e8a3b42d9cdfad6970618e7a81375e1a3a073425`.
- Static V4 scope checks passed, and the tap, binary writers, comparator, and
  detector remained unchanged from the V3 input state.
- A pre-run ROS fixture proved the service schema, C++/Python checksum
  agreement, and wall-clock heartbeat while `/use_sim_time` was not active.

## Runtime failure

The detached supervisor started successfully and remained alive after its
parent shell exited. Quick R1 passed the paused TCPROS handshake, played the
complete frozen bag, and entered `DRAINING` only after rosbag exited naturally.

The post-bag status request never completed. The runtime used
`/use_sim_time=true`; when rosbag exited, `/clock` stopped. The unchanged FAST
main loop uses `ros::Rate::sleep()`, so it remained waiting for simulated time
and could not return to `ros::spinOnce()` to dispatch the newly queued drain
service request. A second read-only client reproduced the same blocked service
call while the service was registered and the FAST process was alive.

No extra `/clock` message was published, no hot patch was applied, and no
fixed sleep was treated as drain evidence. The supervisor was terminated
through its signal handler, wrote `INTERRUPTED`, and cleaned up only its own ROS
processes. The incomplete runtime binary correctly failed trailer validation.

## Gates and claim boundary

- `REPLAY_ENDPOINT_CONTRACT_PASS=true`
- `END_OF_STREAM_AUDIT_IMPLEMENTATION_PASS=false`
- `ALL_CALLBACKS_RECEIVED_PASS=false`
- `END_OF_STREAM_DRAIN_PASS=false`
- `RUNNER_PERSISTENCE_PASS=false`
- `QUICK_BASELINE_REPEATABILITY_PASS=false`
- `OUTDOOR_BASELINE_REPEATABILITY_PASS=false`
- `BASELINE_REPEATABILITY_PASS=false`
- `DAY5_STARTUP_SYNC_V4_PASS=false`
- `DAY5_CAPTURE_EXPORT_REMEDIATION_AUTHORIZED=false`
- `DAY5_RUNTIME_EQUIVALENCE_PASS=false`
- `OFF_ON_REPLAY_EQUIVALENCE_STATUS=NOT_REEVALUATED_STARTUP_SYNC_ONLY`
- `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`

Only `AUDIT_ONLY` was attempted. Tap OFF/ON equivalence, detector output, ODI,
Development, Holdout, Future Test, and harmful-bias detectability were not
evaluated. Stage 2 remains FAIL/PIVOT, Stage 3 and FAST-LIO2 integration remain
unauthorized, and formal Degen-LIO remains incomplete.
