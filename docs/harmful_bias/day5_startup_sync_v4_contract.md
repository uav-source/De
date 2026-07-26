# Day 5 startup-sync V4 contract

## Scope

This remediation freezes the input endpoint of the two existing replay clips and
tests only FAST-LIO2 `AUDIT_ONLY` baseline repeatability. It does not run
`CAPTURE_ONLY`, `COMPACT_EXPORT`, the detector, ODI, Development, Holdout, or
Future Test. It does not authorize Day 6 even if every V4 gate passes.

The previous V3 Quick scan counts were 489, 490, and 489. Those output counts are
evidence of the failure and are not used as an input expectation. The V4 input
expectation comes from a direct read of every frozen rosbag message:

- `avia_quick_shack`: 491 LiDAR and 9,953 IMU messages.
- `avia_outdoor_run_100hz`: 6,386 LiDAR and 12,914 IMU messages.

Each endpoint records the first and last header stamp, bag time, and SHA-256 of
the ROS serialization bytes. The complete endpoint contract is generated twice
and the files must be byte-identical.

## Read-only end-of-stream status

`/harmful_bias/end_of_stream_audit_enabled` defaults to `false`. When explicitly
enabled for these V4 runs, FAST-LIO2 registers the read-only
`/harmful_bias/end_of_stream_status` `std_srvs/Trigger` service. The service is
called only after rosbag exits naturally.

The service reports callback counts, raw and adjusted IMU header stamps,
processed MeasureGroup count and endpoint, LiDAR/IMU/time buffer sizes,
`lidar_pushed`, the current LiDAR end time, latest adjusted IMU time, front-scan
evaluation, processability, main-loop heartbeat, and runtime audit row count.
The snapshot takes the existing buffer mutex only to read these fields. It
does not call `sync_packages`, nearest-neighbor search, measurement
linearization, filter update, or map update.

## Drain gate

A run may enter normal shutdown only when all expected LiDAR and IMU callbacks
have arrived, the final raw header stamps match the endpoint contract, the
front scan has been evaluated, no complete MeasureGroup remains processable,
and LiDAR/time buffer sizes agree. The state fields must then remain unchanged
for 20 polls at 0.1 seconds while the main-loop heartbeat strictly increases.
The timeout is 60 seconds.

A nonempty LiDAR tail is allowed only when its front scan has already been
evaluated and the final IMU endpoint cannot complete it. This preserves the
existing `sync_packages` semantics; no frame is ignored, popped, shifted, or
realigned by the audit layer.

The old fixed five-second delay was insufficient because elapsed wall time
could not prove callback completeness or that all still-processable
MeasureGroups had been consumed.

## Persistent execution

The matrix supervisor runs detached with `nohup setsid`, owns an exclusive file
lock, writes an atomic matrix state and five-second heartbeat, and launches one
replay per child process. Quick R1/R2/R3 always run first and are compared
immediately. Outdoor is forbidden if Quick fails. The fixed run-id cannot be
resumed or reused after interruption.

Strict comparison covers all three pairs per sequence, exact scan pairing and
checksums, final map digest, and 1e-12 pose/covariance tolerances. The processed
MeasureGroup endpoint and unprocessed tail counts must also match across all
three repeats.

## Claim boundary

V4 only freezes and audits replay completion. It does not compare tap OFF
versus ON and does not evaluate harmful-bias detectability. The Stage 2 gate
remains FAIL/PIVOT, Stage 3 remains unauthorized, and formal Degen-LIO remains
incomplete.
