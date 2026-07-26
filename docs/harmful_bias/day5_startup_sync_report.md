# Day 5 Startup-Sync V1 report

## Outcome

The fresh matrix stopped after `avia_quick_shack/AUDIT_ONLY_R1`. That replay used the frozen two-topic clip, completed successfully, passed the bidirectional TCPROS handshake for 20 continuous polls, unpaused through `/day5_bag_player/pause_playback`, and produced 490 runtime records. Its post-run lock then detected that FAST-LIO2 had rewritten `Log/mat_pre.txt` from SHA-256 `19155c0e...37a` to `a70834b4...edc`.

The runner therefore stopped before R2 and did not reuse `multihyp_day5_startup_sync_v1`. No pairwise baseline comparison was performed. `BASELINE_REPEATABILITY_PASS=false`, `DAY5_STARTUP_SYNC_PASS=false`, `DAY5_CAPTURE_EXPORT_REMEDIATION_AUTHORIZED=false`, and `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`.

The startup contract did not define a classification branch for an independent source-lock failure, so the report uses the explicit evidence-backed classification `FASTLIO2_WORKTREE_MUTATION_DURING_REPLAY`. It is not reclassified as a connection or estimator failure.

## Previous failure and scope

The previous audit SHA-256 was `aae6b9839edb36cfdc6eeb6ef9af868104725b7d4e72fbc2e6ac353e22cbdc7c`, run-id `multihyp_day5_remediation_v1`, with `BASELINE_RUNTIME_NONDETERMINISM`. Quick was repeatable, while outdoor R3 contained one extra leading input group and diverged at scan 0, `INPUT_GROUP`.

That failure could not be attributed to the tap because every failing baseline run had the tap and observation export disabled. This task changed only Degen startup/clip/handshake tooling and tests; it did not change tap, writers, detector, comparator gates, schemas, FAST estimator state, covariance, gain, residual, correspondence or map logic.

## Frozen replay clips

Both clips were generated once using the original bag start and locked half-open duration window and then set to mode 0444. They contain only `/livox/lidar` and `/livox/imu` and are marked `ENGINEERING_REPLAY_DERIVATIVE`, `NOT_A_NEW_SCIENTIFIC_SEQUENCE`, and `NOT_INCLUDED_IN_DATA_NAMESPACE`.

- `avia_quick_shack.replay.bag`: SHA `272325265978787c838e010b1f0da963a15fb4b08ff8730fc3dd9901e32a0e20`, 227,822,121 bytes, 491 LiDAR and 9,953 IMU messages.
- `avia_outdoor_run_100hz.replay.bag`: SHA `087c552c9c62be37b42d218323383459df8791ce6514fa7b3425f7bab5021284`, 296,911,627 bytes, 6,386 LiDAR and 12,914 IMU messages.

The audit package contains their manifest, hashes and `rosbag info`, not the clip bags.

## Executed handshake and first boundary

The executed replay started `/day5_bag_player` paused. ROS master graph and both nodes' `getBusInfo` showed exactly one publisher and subscriber on each topic, all four bus directions connected, no extra topic participants, and 20/20 stable polls. The pause service type was `std_srvs/SetBool`; `data: false` returned success.

The first runtime row was scan 0, timestamp 361.19993221, checksum `13230600471073937172`, 2,282 LiDAR points and 20 IMU messages. Because R2/R3 were not run, startup-boundary repeatability and first-ten equality are not evaluated.

## Lock failure

The tracked/untracked FAST source patch SHA remained identical before and after: `3ad02ce3daed73110e828b4c9c73d532deec929a2c4ae34f35f628865e90f3fd`. The binary and both clips also remained unchanged. The byte-tree lock failed only for ignored runtime file `FAST_LIO/Log/mat_pre.txt`, which FAST opens and rewrites during execution even with nonessential publishing and runtime position logging disabled.

The pre-task bytes for that ignored file were not copied, only hashed. They therefore cannot be safely restored without inventing content or running an unauthorized replay. The changed file is retained and the failure is reported rather than silently cleaned.

## Tests and scientific boundary

- Degen targeted: 47 passed.
- Degen full: 751 passed, one existing warning.
- FAST build command passed; reported tests: 114, zero failures/errors/skips. The count includes the previously documented stale failed-V2 XML in the existing build tree; clean restore reports are kept separate.
- Formal replays: 1/6 completed; pairwise comparisons: 0/6 evaluated.
- `CAPTURE_ONLY`, `COMPACT_EXPORT`, detector, ODI, Development, Holdout and Future Test were not run.

The audit package was also restored under an isolated temporary HOME without
access to the operator's Degen or FAST worktrees. The exact startup-sync
targeted suite passed 47 tests. FAST rebuilt from the bundled source material,
then reported 106 tests with zero errors, failures or skips. The synthetic
handshake, clip and Gate fixtures and all packaged small-result hashes passed;
no rosbag replay was run. The isolated Degen full suite was attempted and
reported 652 passed, 85 failed and 14 errors because the package intentionally
excludes the historical gitignored Stage 2 result trees prohibited from the
audit archive. This is recorded as
`DAY5_STARTUP_SYNC_EXTERNAL_DEGEN_FULL_PASS=false`, not hidden as a pass.

`STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`, and `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY5_STARTUP_SYNC` remain fixed. This task only attempted to freeze the input startup boundary. It did not audit tap OFF/ON equivalence, does not authorize Day 6, and does not complete formal Degen-LIO.
