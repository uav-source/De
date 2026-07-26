# Day 5 Startup-Sync Remediation V2 Report

## Outcome

`DAY5_STARTUP_SYNC_V2_PASS=false`. The fresh run ID `multihyp_day5_startup_sync_v2` was consumed and stopped after the first planned replay. No R2-R3 or Outdoor replay was started, and this run ID was not resumed or reused.

The executed Quick Shack R1 established a successful paused start and connection handshake: LiDAR and IMU each had exactly one publisher and subscriber, both publisher and subscriber bus directions were connected, 20/20 stable polls passed, and the same Python process successfully called `/day5_bag_player/pause_playback` once. Its four monotonic timestamps were ordered and its UTC wall timestamp was timezone-qualified.

The replay nevertheless failed the V2 execution contract. The runner did not find `runtime_audit_v2.bin`, `run_summary.json`, `final_map_summary.json`, and `tap_export_summary.json` in the locked run directory. Read-only post-failure inspection found an unterminated runtime binary under a duplicated relative path below `ROS_HOME`; conversion rejected it with `missing or truncated binary trailer`. It therefore cannot be counted as a successful replay or used for pairwise baseline comparison.

The post-failure runtime inventory also found that `Log/imu.txt` changed its modification time. This path is outside the exact six-path allowlist. The final first-divergence classification is therefore `UNEXPECTED_RUNTIME_OUTPUT`, following the contract priority. The allowlisted outputs changed in this execution were `Log/dbg.txt`, `Log/mat_out.txt`, `Log/mat_pre.txt`, and `Log/pos_log.txt`. `Log/imu.txt` is the single unexpected runtime output.

## Lock result

Both Git-aware source locks passed before the replay, after the runtime-output clear, and in the post-failure audit. The FAST-LIO2 checkpoint diff SHA remained `3ad02ce3daed73110e828b4c9c73d532deec929a2c4ae34f35f628865e90f3fd`; the existing binary and both frozen clip hashes remained unchanged. FAST-LIO2 was not modified, rebuilt, or tested by this task.

The previous Startup-Sync V1 stop is retained as `SOURCE_LOCK_FALSE_POSITIVE_EXPECTED_RUNTIME_OUTPUT`: `Log/mat_pre.txt` is correctly excluded from the V2 Git source set. The present V2 failure is different: the exact runtime allowlist exposed `Log/imu.txt`, while the relative output path and forced shutdown left the runtime-audit product incomplete. No code, script, or lock was changed after the V2 run lock was created.

## Gate interpretation

Only 1 of 6 planned runs was executed and 0 of 6 was successful. No pair was evaluated. Consequently every full-matrix status is `NOT_EVALUATED`; executed-run handshake and paused-start counts are reported separately as 1. `EXPECTED_RUNTIME_OUTPUT_ALLOWLIST_PASS=false`, `STARTUP_INPUT_BOUNDARY_PASS=false`, `BASELINE_REPEATABILITY_PASS=false`, and `DAY5_CAPTURE_EXPORT_REMEDIATION_AUTHORIZED=false`.

This work ran AUDIT_ONLY only. It did not run CAPTURE_ONLY, COMPACT_EXPORT, detector evaluation, ODI, Development, Holdout-Dev, Future Test, or tap OFF/ON equivalence. It does not evaluate harmful-bias detectability and does not authorize Day 6.

## Fixed scientific state

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
- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY5_STARTUP_SYNC_V2`
- `DAY5_RUNTIME_EQUIVALENCE_PASS=false`
- `OFF_ON_REPLAY_EQUIVALENCE_STATUS=NOT_REEVALUATED_STARTUP_SYNC_ONLY`
- `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`

Current formal Degen-LIO remains incomplete.
