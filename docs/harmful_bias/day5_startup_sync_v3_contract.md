# Day 5 Startup-Sync Remediation V3 Contract

## Scope

This task is an engineering runtime repeatability check. It runs exactly two
frozen Quick sequences, three AUDIT_ONLY repeats per sequence, in fixed order.
It does not run CAPTURE_ONLY, COMPACT_EXPORT, a production detector, ODI,
Development, Holdout-Dev, Future Test, or Day 6.

The task does not evaluate harmful-bias detectability and does not reevaluate
tap OFF/ON equivalence.

## Previous stop

Startup-Sync V2 stopped because the repository runtime-output allowlist omitted
`Log/imu.txt`, per-run output paths were not consistently absolute, and the
runtime binary found after forced shutdown had no valid trailer.

`Log/imu.txt` is opened by `fout_imu` in `src/IMU_Processing.hpp` through
`DEBUG_FILE_DIR("imu.txt")` after IMU initialization.

## Runtime-output contract

The V3 source scan deterministically resolves production `DEBUG_FILE_DIR`,
repository `Log/PCD` outputs, and per-run runtime products. Confirmed outputs
must be allowlisted and unresolved outputs must be zero before ROS execution.
Repository runtime files remain excluded from Git-aware source identity.

Every replay records allowlist inventories before clearing, after clearing, and
after execution. Any changed `Log/PCD` path outside the frozen allowlist fails
the matrix immediately.

## Absolute paths

The runner expands and resolves the run root immediately after argument
parsing. Run directories, ROS_HOME, ROS_LOG_DIR, runtime output directories,
clip, launch, binary, lock, summary, and runtime binary paths are absolute
before any ROS process starts. The runtime-output ROS parameter must equal the
resolved per-run directory exactly and duplicated run-root fragments are
forbidden.

Committed documentation and manifests use aliases; complete local paths remain
only in ignored runtime evidence.

## Graceful shutdown and products

Rosbag must finish naturally. After a fixed five-second drain period, the
runner requests `/laserMapping` shutdown with `rosnode kill`; process-group
SIGINT is the permitted fallback request. SIGTERM and SIGKILL are allowed only
after the 30-second shutdown timeout and make the replay fail.

After shutdown, the four required products must remain size- and mtime-stable
for five consecutive 0.2-second polls. The binary validator checks header,
version, endianness, framed record lengths and checksums, trailer magic, trailer
record count, file checksum, trailing bytes, complete converter consumption,
and equality with the runtime summary count.

AUDIT_ONLY requires `tap_enabled=false` and
`observation_record_count=0`. The runner adds these explicit contract aliases
to the writer-produced tap summary after normal process exit; FAST-LIO2 source
and writer semantics remain unchanged.

## Fixed state

- `STAGE2_GATE=FAIL`
- `TRANSITION=PIVOT`
- `COHERENT_BIAS_HARMFUL_MECHANISM_SUPPORTED=true`
- `COHERENT_BIAS_STABLY_ONLINE_DETECTABLE=false`
- `STAGE3_START_AUTHORIZED=false`
- `STAGE4_START_AUTHORIZED=false`
- `PATENT2_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`
- `RISK_WARNING_AUTHORIZED=false`
- `PUBLIC_DISCLOSURE_AUTHORIZED=false`
- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY5_STARTUP_SYNC_V3`
- `DAY5_RUNTIME_EQUIVALENCE_PASS=false`
- `OFF_ON_REPLAY_EQUIVALENCE_STATUS=NOT_REEVALUATED_STARTUP_SYNC_ONLY`
- `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`

Even a complete V3 pass authorizes only the bounded Day 5 capture/export
remediation decision. It does not authorize Day 6 and does not complete formal
Degen-LIO.
